from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QSpinBox,
    QPushButton,
    QGroupBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QApplication,
    QCheckBox,
    QScrollArea,
)
from PyQt6.QtCore import Qt, QEvent

from ..app.theme_manager import ThemeManager
from ..app.language_manager import LanguageManager


class SettingsPage(QWidget):
    """Application settings with live theme / language switching,
    database configuration, and data-retention controls.

    Layout mirrors the C++ version: QGroupBox sections with QFormLayout
    plus Save / Reset buttons at the bottom.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._theme_mgr = ThemeManager.instance()
        self._lang_mgr = LanguageManager.instance()

        self._setup_ui()
        self._load_current_settings()
        self._sync_sim_checkbox()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(0)

        title = QLabel(self.tr("Settings"))
        self._title_label = title
        font = title.font()
        font.setPointSize(18)
        font.setBold(True)
        title.setFont(font)
        main_layout.addWidget(title)
        main_layout.addSpacing(16)

        # --- Scrollable content area ---
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(16)

        # --- Appearance group ---
        self._appearance_group = QGroupBox(self.tr("Appearance"))
        appearance_form = QFormLayout(self._appearance_group)

        self._theme_combo = QComboBox()
        for name in ThemeManager.available_themes():
            self._theme_combo.addItem(name)
        self._theme_combo.currentIndexChanged.connect(self._on_theme_changed)
        appearance_form.addRow(self.tr("Theme:"), self._theme_combo)

        self._language_combo = QComboBox()
        for lang in self._lang_mgr.available_languages():
            self._language_combo.addItem(lang["name"], lang["locale"])
        self._language_combo.currentIndexChanged.connect(self._on_language_changed)
        appearance_form.addRow(self.tr("Language:"), self._language_combo)

        scroll_layout.addWidget(self._appearance_group)

        # --- Database group ---
        self._db_group = QGroupBox(self.tr("Database"))
        db_form = QFormLayout(self._db_group)

        self._db_host_edit = QLineEdit("localhost")
        self._db_port_spin = QSpinBox()
        self._db_port_spin.setRange(1, 65535)
        self._db_port_spin.setValue(3306)
        self._db_name_edit = QLineEdit("sigenpro_aging")
        self._db_user_edit = QLineEdit("root")
        self._db_type_combo = QComboBox()
        self._db_type_combo.addItem("MySQL", "mysql")
        self._db_type_combo.addItem("PostgreSQL", "postgresql")

        self._db_pass_edit = QLineEdit()
        self._db_pass_edit.setEchoMode(QLineEdit.EchoMode.Password)

        self._db_status_label = QLabel("")

        db_form.addRow(self.tr("Type:"), self._db_type_combo)
        db_form.addRow(self.tr("Host:"), self._db_host_edit)
        db_form.addRow(self.tr("Port:"), self._db_port_spin)
        db_form.addRow(self.tr("Database:"), self._db_name_edit)
        db_form.addRow(self.tr("Username:"), self._db_user_edit)
        db_form.addRow(self.tr("Password:"), self._db_pass_edit)
        db_form.addRow(self.tr("Status:"), self._db_status_label)

        # Test connection button
        self._test_db_btn = QPushButton(self.tr("Test Connection"))
        self._test_db_btn.clicked.connect(self._on_test_db_connection)
        db_form.addRow("", self._test_db_btn)

        scroll_layout.addWidget(self._db_group)

        # --- Data Retention group ---
        self._retention_group = QGroupBox(self.tr("Data Retention"))
        retention_form = QFormLayout(self._retention_group)

        self._retention_days_spin = QSpinBox()
        self._retention_days_spin.setRange(1, 3650)
        self._retention_days_spin.setValue(90)
        self._retention_days_spin.setSuffix(self.tr(" days"))

        self._auto_cleanup_check = None  # placeholder for future QCheckBox
        # QCheckBox("Enable automatic cleanup")

        retention_form.addRow(
            self.tr("Keep data for:"), self._retention_days_spin
        )

        scroll_layout.addWidget(self._retention_group)

        # --- Communication group ---
        self._comm_group = QGroupBox(self.tr("Communication"))
        comm_form = QFormLayout(self._comm_group)

        self._comm_timeout_spin = QSpinBox()
        self._comm_timeout_spin.setRange(100, 60000)
        self._comm_timeout_spin.setValue(3000)
        self._comm_timeout_spin.setSuffix(" ms")

        self._retry_count_spin = QSpinBox()
        self._retry_count_spin.setRange(0, 10)
        self._retry_count_spin.setValue(3)

        comm_form.addRow(self.tr("Timeout:"), self._comm_timeout_spin)
        comm_form.addRow(self.tr("Retry count:"), self._retry_count_spin)

        self._sim_check = QCheckBox(self.tr("Simulation Mode"))
        self._sim_check.setToolTip(
            self.tr("Enable built-in device data simulator for demo / testing")
        )
        comm_form.addRow(self._sim_check)

        scroll_layout.addWidget(self._comm_group)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        main_layout.addWidget(scroll)

        # --- Buttons ---
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self._save_btn = QPushButton(self.tr("Save"))
        self._save_btn.setProperty("style", "primary")
        self._save_btn.clicked.connect(self._on_save)

        self._reset_btn = QPushButton(self.tr("Reset"))
        self._reset_btn.clicked.connect(self._load_current_settings)

        button_layout.addWidget(self._save_btn)
        button_layout.addWidget(self._reset_btn)
        main_layout.addLayout(button_layout)

    # ------------------------------------------------------------------
    # Load / Save
    # ------------------------------------------------------------------

    def _load_current_settings(self):
        """Populate widgets from persisted QSettings values."""
        from PyQt6.QtCore import QSettings

        settings = QSettings()

        # Theme
        theme_id = settings.value("theme", ThemeManager.DARK, type=int)
        self._theme_combo.setCurrentIndex(theme_id)

        # Language
        locale = settings.value("language", "zh_CN", type=str)
        for i in range(self._language_combo.count()):
            if self._language_combo.itemData(i) == locale:
                self._language_combo.setCurrentIndex(i)
                break

        # Database
        db_type = settings.value("db/type", "mysql", type=str)
        for i in range(self._db_type_combo.count()):
            if self._db_type_combo.itemData(i) == db_type:
                self._db_type_combo.setCurrentIndex(i)
                break
        self._db_host_edit.setText(settings.value("db/host", "localhost", type=str))
        self._db_port_spin.setValue(settings.value("db/port", 3306, type=int))
        self._db_name_edit.setText(settings.value("db/name", "sigenpro_aging", type=str))
        self._db_user_edit.setText(settings.value("db/user", "root", type=str))
        self._db_pass_edit.setText(settings.value("db/password", "", type=str))

        # Data retention
        self._retention_days_spin.setValue(
            settings.value("retention_days", 90, type=int)
        )

        # Communication
        self._comm_timeout_spin.setValue(
            settings.value("comm_timeout", 3000, type=int)
        )
        self._retry_count_spin.setValue(
            settings.value("retry_count", 3, type=int)
        )

    def _on_save(self):
        """Persist current widget values to QSettings and apply DB config."""
        from PyQt6.QtCore import QSettings
        from ..storage.database_manager import DatabaseManager

        settings = QSettings()

        # Theme & Language are applied live via their combo signals;
        # still persist them here for completeness.
        settings.setValue("theme", self._theme_combo.currentIndex())
        if self._language_combo.currentData():
            settings.setValue("language", self._language_combo.currentData())

        # Database
        db_type = self._db_type_combo.currentData() or "mysql"
        settings.setValue("db/type", db_type)
        settings.setValue("db/host", self._db_host_edit.text())
        settings.setValue("db/port", self._db_port_spin.value())
        settings.setValue("db/name", self._db_name_edit.text())
        settings.setValue("db/user", self._db_user_edit.text())
        settings.setValue("db/password", self._db_pass_edit.text())

        # Live-apply remote database configuration
        dbm = DatabaseManager.instance()
        try:
            ok = dbm.reconfigure_remote(
                host=self._db_host_edit.text(),
                port=self._db_port_spin.value(),
                db_name=self._db_name_edit.text(),
                user=self._db_user_edit.text(),
                password=self._db_pass_edit.text(),
                db_type=db_type,
            )
            self._db_status_label.setText(
                self.tr("Connected") if ok else self.tr("Connection failed")
            )
            self._db_status_label.setStyleSheet(
                "color: green;" if ok else "color: red;"
            )
        except Exception as e:
            self._db_status_label.setText(self.tr("Error: %1").arg(str(e)))
            self._db_status_label.setStyleSheet("color: red;")

        # Data retention
        settings.setValue("retention_days", self._retention_days_spin.value())

        # Communication
        settings.setValue("comm_timeout", self._comm_timeout_spin.value())
        settings.setValue("retry_count", self._retry_count_spin.value())

        QMessageBox.information(
            self,
            self.tr("Settings"),
            self.tr("Settings saved successfully."),
        )

    # ------------------------------------------------------------------
    # Live theme / language switching
    # ------------------------------------------------------------------

    def _on_theme_changed(self, index: int):
        if index >= 0:
            self._theme_mgr.apply_theme(index)

    def _on_language_changed(self, index: int):
        locale = self._language_combo.currentData()
        if locale:
            self._lang_mgr.switch_language(locale)

    def _on_test_db_connection(self):
        """Test the remote database connection without saving."""
        from ..storage.database_manager import DatabaseManager

        dbm = DatabaseManager.instance()
        try:
            ok = dbm.reconfigure_remote(
                host=self._db_host_edit.text(),
                port=self._db_port_spin.value(),
                db_name=self._db_name_edit.text(),
                user=self._db_user_edit.text(),
                password=self._db_pass_edit.text(),
                db_type=self._db_type_combo.currentData() or "mysql",
            )
            if ok:
                self._db_status_label.setText(self.tr("Connection successful"))
                self._db_status_label.setStyleSheet("color: green;")
            else:
                self._db_status_label.setText(self.tr("Connection failed"))
                self._db_status_label.setStyleSheet("color: red;")
        except Exception as e:
            self._db_status_label.setText(self.tr("Error: %1").arg(str(e)))
            self._db_status_label.setStyleSheet("color: red;")

    def _sync_sim_checkbox(self):
        """Sync the simulation checkbox with the running Simulator state."""
        self._sim_check.blockSignals(True)
        try:
            from PyQt6.QtWidgets import QApplication
            app = QApplication.instance()
            if app and hasattr(app, '_simulator'):
                self._sim_check.setChecked(app._simulator.is_running)
                app._simulator.simulation_changed.connect(self._on_sim_state_changed)
                self._sim_check.toggled.connect(self._on_sim_toggled)
        except Exception:
            pass
        finally:
            self._sim_check.blockSignals(False)

    def _on_sim_toggled(self, checked: bool):
        """Toggle simulation on/off from the checkbox."""
        try:
            from PyQt6.QtWidgets import QApplication
            app = QApplication.instance()
            if app and hasattr(app, '_simulator'):
                if checked and not app._simulator.is_running:
                    app._simulator.start_sim()
                elif not checked and app._simulator.is_running:
                    app._simulator.stop_sim()
        except Exception as e:
            self._sim_check.setChecked(not checked)

    def _on_sim_state_changed(self, running: bool):
        """Update checkbox when simulation state changes externally."""
        self._sim_check.blockSignals(True)
        self._sim_check.setChecked(running)
        self._sim_check.blockSignals(False)

    # ------------------------------------------------------------------
    # Retranslate
    # ------------------------------------------------------------------

    def changeEvent(self, event):
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslate_ui()
        super().changeEvent(event)

    def retranslate_ui(self):
        self._title_label.setText(self.tr("Settings"))
        self._appearance_group.setTitle(self.tr("Appearance"))
        self._db_group.setTitle(self.tr("Database"))
        self._retention_group.setTitle(self.tr("Data Retention"))
        self._comm_group.setTitle(self.tr("Communication"))
        self._sim_check.setText(self.tr("Simulation Mode"))
        self._sim_check.setToolTip(
            self.tr("Enable built-in device data simulator for demo / testing")
        )
        self._test_db_btn.setText(self.tr("Test Connection"))
        self._save_btn.setText(self.tr("Save"))
        self._reset_btn.setText(self.tr("Reset"))
        self._retention_days_spin.setSuffix(self.tr(" days"))
