import sys
import os
import logging
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QSettings, qInstallMessageHandler


class Application(QApplication):
    """Subclass of QApplication that bootstraps all singletons and the main window."""

    def __init__(self, argv):
        super().__init__(argv)
        self.setApplicationName("SigenPro Aging Monitor")
        self.setApplicationVersion("1.0.0")
        self.setOrganizationName("SigenPro")

        self._main_window = None
        self._settings = QSettings("SigenPro", "SigenProAgingMonitor")

        self._initialize_logger()
        self._initialize_theme()
        self._initialize_language()
        self._initialize_main_window()

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def _initialize_logger(self):
        from .logger import Logger

        logger = Logger.instance()
        log_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "logs",
        )
        logger.set_log_dir(log_dir)

        # Install Qt message handler so Qt logs also go to our file
        qInstallMessageHandler(Logger.qt_message_handler)

        logging.info("Application starting ...")

    def _initialize_theme(self):
        from .theme_manager import ThemeManager

        mgr = ThemeManager.instance()

        # Restore the last-used theme, defaulting to dark
        theme_id = self._settings.value("theme", ThemeManager.DARK, type=int)
        mgr.apply_theme(theme_id)

    def _initialize_language(self):
        from .language_manager import LanguageManager

        mgr = LanguageManager.instance()

        # Restore the last-used language, defaulting to zh_CN
        locale = self._settings.value("language", "zh_CN", type=str)
        mgr.switch_language(locale)

    def _initialize_main_window(self):
        from ..ui.main_window import MainWindow
        from ..ui.device_overview import DeviceOverviewPage
        from ..ui.settings_page import SettingsPage

        self._main_window = MainWindow()

        # Replace placeholder pages with real widgets
        device_overview = DeviceOverviewPage()
        self._main_window.set_page(MainWindow.PAGE_DEVICE_OVERVIEW, device_overview)

        settings_page = SettingsPage()
        self._main_window.set_page(MainWindow.PAGE_SETTINGS, settings_page)

    # ------------------------------------------------------------------
    # Public accessors
    # ------------------------------------------------------------------

    def main_window(self):
        return self._main_window

    def run(self):
        """Show the main window and enter the event loop."""
        self._main_window.show()
        return self.exec()
