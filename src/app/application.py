import sys
import os
import logging
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QSettings, qInstallMessageHandler

logger = logging.getLogger(__name__)


class Application(QApplication):
    """Subclass of QApplication that bootstraps all singletons, business
    logic, instrument control, communication, and the main window.

    Signal wiring summary::

        TCP  --device_data_received--> DataBus.publish_raw_data
        TCP  --device_status_changed--> DataBus.publish_device_status
        Barcode --barcode_scanned--> status bar message
        TestEngine --test_started--> ChannelManager.power_on
        TestEngine --test_completed--> ChannelManager.power_off
        DataBus --alarm_triggered--> AlarmPanelPage.add_alarm
        DataBus --alarm_triggered--> TestEngine.set_has_alarm
        DataBus --device_status_changed--> DeviceOverviewPage
        DataBus --device_data_received--> DeviceOverviewPage
        DataBus --device_data_received--> DeviceDetailPage
    """

    def __init__(self, argv):
        super().__init__(argv)
        self.setApplicationName("SigenPro Aging Monitor")
        self.setApplicationVersion("1.0.0")
        self.setOrganizationName("SigenPro")

        self._settings = QSettings("SigenPro", "SigenProAgingMonitor")

        # Keep references for signal wiring
        self._device_overview_page = None

        # ------------------------------------------------------------------
        # 1. Logger
        # ------------------------------------------------------------------
        self._initialize_logger()

        # ------------------------------------------------------------------
        # 2. Database
        # ------------------------------------------------------------------
        self._initialize_database()

        # ------------------------------------------------------------------
        # 3. Plugins
        # ------------------------------------------------------------------
        self._initialize_plugins()

        # ------------------------------------------------------------------
        # 4. Business logic (AlarmEngine, TemplateManager, TestEngine)
        # ------------------------------------------------------------------
        self._initialize_business_logic()

        # ------------------------------------------------------------------
        # 5. Instrument control (ChannelManager, BarcodeScanner)
        # ------------------------------------------------------------------
        self._initialize_instruments()

        # ------------------------------------------------------------------
        # 6. Communication (TcpConnectionManager)
        # ------------------------------------------------------------------
        self._initialize_communication()

        # ------------------------------------------------------------------
        # 7. Simulation (MVP demo mode)
        # ------------------------------------------------------------------
        self._initialize_simulation()

        # ------------------------------------------------------------------
        # 8. Main window & UI pages
        # ------------------------------------------------------------------
        self._initialize_main_window()

        # ------------------------------------------------------------------
        # 9. Wire DataBus signals to UI
        # ------------------------------------------------------------------
        self._wire_ui_connections()

        # ------------------------------------------------------------------
        # 10. Apply saved theme / language
        # ------------------------------------------------------------------
        self._initialize_theme()
        self._initialize_language()

        logger.info("Application initialized successfully")

    # ------------------------------------------------------------------
    # Initialization helpers
    # ------------------------------------------------------------------

    def _initialize_logger(self):
        from .logger import Logger

        log_instance = Logger.instance()
        log_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "logs",
        )
        log_instance.set_log_dir(log_dir)

        # Install Qt message handler so Qt logs also go to our file
        qInstallMessageHandler(Logger.qt_message_handler)

        logging.info("Application starting ...")

    def _initialize_database(self):
        from ..storage.database_manager import DatabaseManager
        DatabaseManager.instance().initialize()

    def _initialize_plugins(self):
        from ..protocol.plugin_manager import PluginManager
        plugin_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "plugins",
        )
        if not os.path.isdir(plugin_dir):
            os.makedirs(plugin_dir, exist_ok=True)
        self._plugin_manager = PluginManager()
        self._plugin_manager.load_plugins(plugin_dir)

    def _initialize_business_logic(self):
        from ..core.alarm_engine import AlarmEngine
        from ..core.template_manager import TemplateManager
        from ..core.test_engine import TestEngine

        self._alarm_engine = AlarmEngine(self)
        self._template_manager = TemplateManager(self)
        self._template_manager.load_templates()
        self._test_engine = TestEngine(self)
        self._test_engine.set_alarm_engine(self._alarm_engine)
        self._test_engine.set_template_manager(self._template_manager)

    def _initialize_instruments(self):
        from ..instrument.channel_manager import ChannelManager
        from ..instrument.barcode_scanner import BarcodeScanner

        self._channel_manager = ChannelManager(self)
        self._channel_manager.load_channels()
        self._barcode_scanner = BarcodeScanner(self)

    def _initialize_communication(self):
        from ..communication.tcp_manager import TcpConnectionManager
        from ..core.data_bus import DataBus

        self._tcp_manager = TcpConnectionManager(self)

        # Wire TCP -> DataBus
        self._tcp_manager.device_data_received.connect(
            lambda did, data: DataBus.instance().publish_raw_data(did, data))
        self._tcp_manager.device_status_changed.connect(
            lambda did, status: DataBus.instance().publish_device_status(did, status))

    def _initialize_simulation(self):
        from ..simulation.simulator import Simulator
        self._simulator = Simulator(self)
        self._simulator.start_sim()

    def _initialize_main_window(self):
        from ..ui.main_window import MainWindow
        from ..ui.device_overview import DeviceOverviewPage
        from ..core.data_bus import DataBus

        self._main_window = MainWindow()

        # Replace the Device Overview placeholder
        self._device_overview_page = DeviceOverviewPage()
        self._device_overview_page.device_clicked.connect(
            self._main_window.show_device_detail)
        self._main_window.set_page(
            MainWindow.PAGE_DEVICE_OVERVIEW, self._device_overview_page)

        # Wire barcode -> status bar
        self._barcode_scanner.barcode_scanned.connect(self._on_barcode_scanned)

        # Wire test engine -> channel manager
        self._test_engine.test_started.connect(self._channel_manager.power_on)
        self._test_engine.test_completed.connect(self._on_test_completed)

        # Wire alarm engine -> test engine (mark has_alarm)
        DataBus.instance().alarm_triggered.connect(self._on_alarm_for_test)

    def _initialize_theme(self):
        from .theme_manager import ThemeManager

        mgr = ThemeManager.instance()
        theme_id = self._settings.value("theme", ThemeManager.DARK, type=int)
        mgr.apply_theme(theme_id)

    def _initialize_language(self):
        from .language_manager import LanguageManager

        mgr = LanguageManager.instance()
        locale = self._settings.value("language", "zh_CN", type=str)
        mgr.switch_language(locale)

    # ------------------------------------------------------------------
    # Slot handlers
    # ------------------------------------------------------------------

    def _on_barcode_scanned(self, barcode):
        if self._main_window:
            self._main_window.statusBar().showMessage(
                self.tr("Barcode scanned: %1").arg(barcode), 5000)

    def _on_test_completed(self, channel_id, result):
        from ..core.common.types import TestResult
        self._channel_manager.power_off(channel_id)
        # Keep binding for now -- the operator decides when to unbind
        if result != TestResult.INTERRUPTED:
            pass

    def _on_alarm_for_test(self, alarm):
        if alarm and hasattr(alarm, 'device_id'):
            self._test_engine.set_has_alarm(alarm.device_id)

    # ------------------------------------------------------------------
    # DataBus -> UI wiring
    # ------------------------------------------------------------------

    def _wire_ui_connections(self):
        """Connect DataBus signals to UI pages."""
        from ..core.data_bus import DataBus
        from ..core.common.alarm_record import AlarmRecord

        mw = self._main_window

        # DataBus -> Overview page
        DataBus.instance().device_status_changed.connect(
            self._device_overview_page.update_device_status)
        DataBus.instance().device_data_received.connect(
            self._device_overview_page.on_device_data_updated)

        # Overview control -> Simulator
        self._device_overview_page.all_started.connect(
            lambda: self._simulator.set_all_running(True))
        self._device_overview_page.all_stopped.connect(
            lambda: self._simulator.set_all_running(False))
        self._device_overview_page.device_start_clicked.connect(
            lambda did: self._simulator.set_running(did, True))
        self._device_overview_page.device_stop_clicked.connect(
            lambda did: self._simulator.set_running(did, False))

        # DataBus -> Alarm Panel
        DataBus.instance().alarm_triggered.connect(self._on_alarm_triggered)

        # DataBus -> Detail Page
        DataBus.instance().device_data_received.connect(
            mw.device_detail_page.on_device_data_received)

    def _on_alarm_triggered(self, alarm):
        """Forward an AlarmRecord from the DataBus to the alarm panel table."""
        mw = self._main_window
        mw.alarm_panel_page.add_alarm(alarm)

    # ------------------------------------------------------------------
    # Public accessors
    # ------------------------------------------------------------------

    def main_window(self):
        return self._main_window

    def run(self):
        """Show the main window and enter the event loop."""
        self._main_window.show()
        return self.exec()
