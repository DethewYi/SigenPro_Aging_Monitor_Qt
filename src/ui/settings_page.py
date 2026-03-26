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
)
from PyQt6.QtCore import Qt

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

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(16)

        title = QLabel(self.tr("Settings"))
        font = title.font()
        font.setPointSize(18)
        font.setBold(True)
        title.setFont(font)
        main_layout.addWidget(title)

        # --- Appearance group ---
        appearance_group = QGroupBox(self.tr("Appearance"))
        appearance_form = QFormLayout(appearance_group)

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

        main_layout.addWidget(appearance_group)

        # --- Database group ---
        db_group = QGroupBox(self.tr("Database"))
        db_form = QFormLayout(db_group)

        self._db_host_edit = QLineEdit("localhost")
        self._db_port_spin = QSpinBox()
        self._db_port_spin.setRange(1, 65535)
        self._db_port_spin.setValue(3306)
        self._db_name_edit = QLineEdit("sigenpro_aging")
        self._db_user_edit = QLineEdit("root")
        self._db_pass_edit = QLineEdit()
        self._db_pass_edit.setEchoMode(QLineEdit.EchoMode.Password)

        db_form.addRow(self.tr("Host:"), self._db_host_edit)
        db_form.addRow(self.tr("Port:"), self._db_port_spin)
        db_form.addRow(self.tr("Database:"), self._db_name_edit)
        db_form.addRow(self.tr("Username:"), self._db_user_edit)
        db_form.addRow(self.tr("Password:"), self._db_pass_edit)

        main_layout.addWidget(db_group)

        # --- Data Retention group ---
        retention_group = QGroupBox(self.tr("Data Retention"))
        retention_form = QFormLayout(retention_group)

        self._retention_days_spin = QSpinBox()
        self._retention_days_spin.setRange(1, 3650)
        self._retention_days_spin.setValue(90)
        self._retention_days_spin.setSuffix(self.tr(" days"))

        self._auto_cleanup_check = None  # placeholder for future QCheckBox
        # QCheckBox("Enable automatic cleanup")

        retention_form.addRow(
            self.tr("Keep data for:"), self._retention_days_spin
        )

        main_layout.addWidget(retention_group)

        # --- Communication group ---
        comm_group = QGroupBox(self.tr("Communication"))
        comm_form = QFormLayout(comm_group)

        self._comm_timeout_spin = QSpinBox()
        self._comm_timeout_spin.setRange(100, 60000)
        self._comm_timeout_spin.setValue(3000)
        self._comm_timeout_spin.setSuffix(" ms")

        self._retry_count_spin = QSpinBox()
        self._retry_count_spin.setRange(0, 10)
        self._retry_count_spin.setValue(3)

        comm_form.addRow(self.tr("Timeout:"), self._comm_timeout_spin)
        comm_form.addRow(self.tr("Retry count:"), self._retry_count_spin)

        main_layout.addWidget(comm_group)

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

        main_layout.addStretch()

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
        """Persist current widget values to QSettings."""
        from PyQt6.QtCore import QSettings

        settings = QSettings()

        # Theme & Language are applied live via their combo signals;
        # still persist them here for completeness.
        settings.setValue("theme", self._theme_combo.currentIndex())
        if self._language_combo.currentData():
            settings.setValue("language", self._language_combo.currentData())

        # Database
        settings.setValue("db/host", self._db_host_edit.text())
        settings.setValue("db/port", self._db_port_spin.value())
        settings.setValue("db/name", self._db_name_edit.text())
        settings.setValue("db/user", self._db_user_edit.text())
        settings.setValue("db/password", self._db_pass_edit.text())

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
