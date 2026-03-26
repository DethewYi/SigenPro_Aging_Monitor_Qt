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
    PAGE_ALARMS = 1
    PAGE_DATA_QUERY = 2
    PAGE_TEMPLATE_MGMT = 3
    PAGE_SETTINGS = 4

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("SigenPro Aging Monitor"))
        self.resize(1400, 900)

        self._nav_buttons: dict[int, QPushButton] = {}
        self._button_group: QButtonGroup | None = None

        self._setup_ui()
        self._setup_menu_bar()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self):
        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._setup_side_nav()
        self._setup_content_area()

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
        if btn and btn.isCheckable():
            btn.setChecked(True)

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
            self.tr("Device Overview"),
            self.tr("Alarm Panel"),
            self.tr("Data Query"),
            self.tr("Template Management"),
            self.tr("Settings"),
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
