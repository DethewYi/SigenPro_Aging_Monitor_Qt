from PyQt6.QtWidgets import (
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QStatusBar,
    QMenuBar,
    QMenu,
    QButtonGroup,
    QApplication,
)
from PyQt6.QtCore import Qt


class MainWindow(QMainWindow):
    """Top-level application window with sidebar navigation and stacked pages."""

    # Page indices — used as stable constants throughout the application
    PAGE_DEVICE_OVERVIEW = 0
    PAGE_DEVICE_DETAIL = 1
    PAGE_ALARMS = 2
    PAGE_DATA_QUERY = 3
    PAGE_TEMPLATE_MGMT = 4
    PAGE_SETTINGS = 5
    PAGE_RECIPE_MGMT = 6

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("SigenPro Aging Monitor"))
        self.resize(1400, 900)

        self._nav_buttons: dict[int, QPushButton] = {}
        self._button_group: QButtonGroup | None = None
        self._device_detail_page = None
        self._alarm_panel_page = None
        self._data_query_page = None

        self._setup_ui()
        self._setup_menu_bar()
        self._setup_detail_pages()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self):
        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._setup_content_area()
        self._setup_side_nav()

        layout.addWidget(self._side_nav)
        layout.addWidget(self._content_stack)
        self.setCentralWidget(central)
        self.statusBar().showMessage(self.tr("Ready"))

    def _setup_side_nav(self):
        self._side_nav = QWidget()
        self._side_nav.setFixedWidth(200)
        layout = QVBoxLayout(self._side_nav)
        layout.setContentsMargins(8, 16, 8, 16)
        layout.setSpacing(4)

        # Logo
        logo = QLabel(self.tr("SigenPro"))
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = logo.font()
        font.setPointSize(18)
        font.setBold(True)
        logo.setFont(font)
        layout.addWidget(logo)
        layout.addSpacing(24)

        # Exclusive navigation buttons (Device Overview, Alarms, Data Query)
        self._button_group = QButtonGroup(self)
        self._button_group.setExclusive(True)

        main_pages = [
            ("Device Overview", self.PAGE_DEVICE_OVERVIEW),
            ("Alarms", self.PAGE_ALARMS),
            ("Data Query", self.PAGE_DATA_QUERY),
        ]
        for text, idx in main_pages:
            btn = self._nav_button(text, checkable=True)
            self._button_group.addButton(btn, idx)
            layout.addWidget(btn)
            self._nav_buttons[idx] = btn

        # Check the first button by default
        if self._nav_buttons:
            self._nav_buttons[self.PAGE_DEVICE_OVERVIEW].setChecked(True)

        self._button_group.idClicked.connect(self._content_stack.setCurrentIndex)

        layout.addStretch()

        # Bottom navigation (Template Mgmt, Settings) — non-exclusive
        bottom_pages = [
            ("Template Mgmt", self.PAGE_TEMPLATE_MGMT),
            ("Recipe Mgmt", self.PAGE_RECIPE_MGMT),
            ("Settings", self.PAGE_SETTINGS),
        ]
        for text, idx in bottom_pages:
            btn = self._nav_button(text, checkable=False)
            btn.clicked.connect(lambda checked, i=idx: self._content_stack.setCurrentIndex(i))
            layout.addWidget(btn)
            self._nav_buttons[idx] = btn

        # Keep nav highlighting in sync with stack changes
        self._content_stack.currentChanged.connect(self._on_page_changed)

    def _nav_button(self, text: str, checkable: bool = False) -> QPushButton:
        btn = QPushButton(self.tr(text))
        btn.setCheckable(checkable)
        btn.setFixedHeight(44)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setProperty("class", "nav-button")
        return btn

    def _on_page_changed(self, index: int):
        """Highlight the correct nav button when the stacked page changes."""
        btn = self._nav_buttons.get(index)
        if not btn:
            return
        if btn.isCheckable():
            btn.setChecked(True)
        else:
            # For non-exclusive buttons, highlight briefly then reset
            for other_btn in self._nav_buttons.values():
                if other_btn.isCheckable():
                    other_btn.setChecked(False)
            btn.setProperty("active", True)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
            # Use a single-shot timer to clear highlight
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(300, lambda b=btn: (
                b.setProperty("active", False),
                b.style().unpolish(b),
                b.style().polish(b),
            ))

    def _setup_menu_bar(self):
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu(self.tr("&File"))
        file_menu.addAction(
            self.tr("&Settings"),
            lambda: self._content_stack.setCurrentIndex(self.PAGE_SETTINGS),
        )
        file_menu.addSeparator()
        file_menu.addAction(self.tr("E&xit"), self.close)

        view_menu = menu_bar.addMenu(self.tr("&View"))
        view_menu.addAction(
            self.tr("Device &Overview"),
            lambda: self._content_stack.setCurrentIndex(self.PAGE_DEVICE_OVERVIEW),
        )
        view_menu.addAction(
            self.tr("&Alarms"),
            lambda: self._content_stack.setCurrentIndex(self.PAGE_ALARMS),
        )
        view_menu.addAction(
            self.tr("&Data Query"),
            lambda: self._content_stack.setCurrentIndex(self.PAGE_DATA_QUERY),
        )
        view_menu.addAction(
            self.tr("&Template Management"),
            lambda: self._content_stack.setCurrentIndex(self.PAGE_TEMPLATE_MGMT),
        )

    def _setup_content_area(self):
        self._content_stack = QStackedWidget(self)

        # Placeholder pages — each will be replaced with a real widget later
        placeholder_labels = [
            self.tr("Device Overview"),   # PAGE_DEVICE_OVERVIEW
            self.tr("Device Detail"),     # PAGE_DEVICE_DETAIL
            self.tr("Alarm Panel"),       # PAGE_ALARMS
            self.tr("Data Query"),        # PAGE_DATA_QUERY
            self.tr("Template Management"),  # PAGE_TEMPLATE_MGMT
            self.tr("Settings"),          # PAGE_SETTINGS
            self.tr("Recipe Management"),  # PAGE_RECIPE_MGMT
        ]
        for text in placeholder_labels:
            label = QLabel(text)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            font = label.font()
            font.setPointSize(16)
            label.setFont(font)
            self._content_stack.addWidget(label)

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def set_page(self, index: int, widget: QWidget):
        """Replace a placeholder page at *index* with a real *widget*."""
        old = self._content_stack.widget(index)
        self._content_stack.removeWidget(old)
        if old:
            old.deleteLater()
        self._content_stack.insertWidget(index, widget)

    def content_stack(self) -> QStackedWidget:
        return self._content_stack

    def navigate_to(self, page_index: int):
        """Programmatically navigate to a given page."""
        self._content_stack.setCurrentIndex(page_index)

    # ------------------------------------------------------------------
    # Detail page wiring
    # ------------------------------------------------------------------

    @property
    def device_detail_page(self):
        """Return the DeviceDetailPage instance (created in _setup_detail_pages)."""
        return self._device_detail_page

    @property
    def alarm_panel_page(self):
        """Return the AlarmPanelPage instance (created in _setup_detail_pages)."""
        return self._alarm_panel_page

    @property
    def data_query_page(self):
        """Return the DataQueryPage instance (created in _setup_detail_pages)."""
        return self._data_query_page

    def _setup_detail_pages(self):
        """Instantiate and wire the device detail, alarm, data query, and template pages."""
        from .device_detail import DeviceDetailPage
        from .alarm_panel import AlarmPanelPage
        from .data_query import DataQueryPage
        from .template_config import TemplateConfigPage

        # --- Device Detail page (PAGE_DEVICE_DETAIL = 1) ---
        self._device_detail_page = DeviceDetailPage()
        self.set_page(self.PAGE_DEVICE_DETAIL, self._device_detail_page)

        # --- Alarm Panel page (PAGE_ALARMS = 2) ---
        self._alarm_panel_page = AlarmPanelPage()
        self.set_page(self.PAGE_ALARMS, self._alarm_panel_page)

        # --- Data Query page (PAGE_DATA_QUERY = 3) ---
        self._data_query_page = DataQueryPage()
        self.set_page(self.PAGE_DATA_QUERY, self._data_query_page)

        # --- Template Management page (PAGE_TEMPLATE_MGMT = 4) ---
        self._template_config_page = TemplateConfigPage()
        self.set_page(self.PAGE_TEMPLATE_MGMT, self._template_config_page)

        # --- Settings page (PAGE_SETTINGS = 5) ---
        from .settings_page import SettingsPage
        self._settings_page = SettingsPage()
        self.set_page(self.PAGE_SETTINGS, self._settings_page)

        # --- Recipe Management page (PAGE_RECIPE_MGMT = 6) ---
        from .recipe_config import RecipeConfigPage
        self._recipe_config_page = RecipeConfigPage()
        self.set_page(self.PAGE_RECIPE_MGMT, self._recipe_config_page)

        # --- Wire cross-page navigation ---

        # Device Overview -> Device Detail
        # This signal is emitted by DeviceOverviewPage; we connect it here
        # so that when application.py replaces the overview placeholder,
        # it can re-connect device_clicked -> _show_device_detail.
        # The handler is a method so it can be called by the app layer too.
        self._device_detail_page.back_requested.connect(
            lambda: self.navigate_to(self.PAGE_DEVICE_OVERVIEW)
        )

        # Alarm panel -> Device Detail (double-click on alarm row)
        self._alarm_panel_page.device_alarm_clicked.connect(self._show_device_detail)

        # Data Query -> Device Detail (double-click on record row)
        self._data_query_page.navigate_to_device_detail.connect(self._show_device_detail)

    def show_device_detail(self, device_id: int):
        """Public helper: navigate to the device detail page for *device_id*."""
        self._show_device_detail(device_id)

    def _show_device_detail(self, device_id: int):
        """Activate the device detail page and set the device context."""
        if self._device_detail_page is None:
            return
        self._device_detail_page.set_device(device_id)
        self.navigate_to(self.PAGE_DEVICE_DETAIL)
