"""Device detail page with real-time pyqtgraph charts, data panel, and test controls."""

import pyqtgraph as pg
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QProgressBar,
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from datetime import datetime

from ..core.common.device_data import DeviceData


# ---------------------------------------------------------------------------
# Real-time scrolling chart using pyqtgraph
# ---------------------------------------------------------------------------

class CurveChartWidget(QWidget):
    """Displays one or more scrolling time-series curves via pyqtgraph."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._curves: dict[str, pg.PlotDataItem] = {}
        self._time_data: dict[str, list] = {}
        self._value_data: dict[str, list] = {}
        self._display_window = 300  # seconds shown
        self._start_time = 0.0
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._plot = pg.PlotWidget()
        self._plot.setBackground("#1e1e2e")
        self._plot.showGrid(x=True, y=True, alpha=0.3)
        self._plot.setLabel("bottom", self.tr("Time"), units="s")
        self._plot.setLabel("left", self.tr("Value"))
        self._plot.addLegend(offset=(60, 10))
        self._plot.enableAutoRange(axis="y")

        # Style axis text/pen to match dark theme
        for axis in ("bottom", "left"):
            self._plot.getAxis(axis).setPen(pg.mkPen("#cdd6f4"))
            self._plot.getAxis(axis).setTextPen(pg.mkPen("#cdd6f4"))

        layout.addWidget(self._plot)

    # --- Public API -------------------------------------------------------

    def add_curve(self, name: str, color: str):
        pen = pg.mkPen(color=color, width=2)
        curve = self._plot.plot(pen=pen, name=name)
        self._curves[name] = curve
        self._time_data[name] = []
        self._value_data[name] = []

    def remove_curve(self, name: str):
        if name in self._curves:
            self._plot.removeItem(self._curves[name])
            del self._curves[name]
            del self._time_data[name]
            del self._value_data[name]

    def clear_all_curves(self):
        for name in list(self._curves.keys()):
            self.remove_curve(name)

    def append_data(self, name: str, timestamp: float, value: float):
        if name not in self._curves:
            return
        if self._start_time == 0:
            self._start_time = timestamp
        t = timestamp - self._start_time

        self._time_data[name].append(t)
        self._value_data[name].append(value)

        # Trim data outside the display window
        while self._time_data[name] and self._time_data[name][0] < t - self._display_window:
            self._time_data[name].pop(0)
            self._value_data[name].pop(0)

        self._curves[name].setData(self._time_data[name], self._value_data[name])

    def clear_data(self):
        for name in self._curves:
            self._time_data[name] = []
            self._value_data[name] = []
            self._curves[name].setData([], [])
        self._start_time = 0.0

    def set_display_window(self, seconds: int):
        self._display_window = seconds


# ---------------------------------------------------------------------------
# Real-time data panel (parameter table)
# ---------------------------------------------------------------------------

class RealtimeDataPanel(QWidget):
    """Shows current parameter values in a two-column table."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._param_rows: dict[str, int] = {}
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        title = QLabel(self.tr("Real-time Data"))
        font = title.font()
        font.setBold(True)
        font.setPointSize(12)
        title.setFont(font)
        layout.addWidget(title)

        self._table = QTableWidget(0, 2)
        self._table.setHorizontalHeaderLabels([self.tr("Parameter"), self.tr("Value")])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents,
        )
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._table.setAlternatingRowColors(True)
        layout.addWidget(self._table)

    # --- Public API -------------------------------------------------------

    def setup_parameters(self, param_names: list[str]):
        self._table.setRowCount(len(param_names))
        for i, name in enumerate(param_names):
            self._table.setItem(i, 0, QTableWidgetItem(name))
            self._table.setItem(i, 1, QTableWidgetItem("--"))
            self._param_rows[name] = i

    def update_parameter(self, name: str, value: float):
        if name in self._param_rows:
            item = self._table.item(self._param_rows[name], 1)
            if item:
                item.setText(f"{value:.3f}")

    def clear_all(self):
        self._table.setRowCount(0)
        self._param_rows.clear()


# ---------------------------------------------------------------------------
# Test control panel (start / pause / stop + progress)
# ---------------------------------------------------------------------------

class TestControlPanel(QWidget):
    """Bottom bar with test start/pause/stop controls and progress display."""

    start_clicked = pyqtSignal()
    pause_clicked = pyqtSignal()
    stop_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)

        # Template info label
        self._template_label = QLabel(self.tr("Template: --"))
        layout.addWidget(self._template_label)

        layout.addStretch()

        # Progress bar
        self._progress_bar = QProgressBar()
        self._progress_bar.setFixedWidth(200)
        self._progress_bar.setTextVisible(True)
        layout.addWidget(self._progress_bar)

        # Elapsed / total time label
        self._time_label = QLabel("00:00:00 / 00:00:00")
        layout.addWidget(self._time_label)

        layout.addStretch()

        # Control buttons
        self._start_btn = QPushButton(self.tr("\u25b6 Start"))
        self._pause_btn = QPushButton(self.tr("\u23f8 Pause"))
        self._stop_btn = QPushButton(self.tr("\u23f9 Stop"))

        for btn in (self._start_btn, self._pause_btn, self._stop_btn):
            btn.setFixedHeight(32)
            layout.addWidget(btn)

        self._start_btn.clicked.connect(self.start_clicked.emit)
        self._pause_btn.clicked.connect(self.pause_clicked.emit)
        self._stop_btn.clicked.connect(self.stop_clicked.emit)

        self._start_btn.setEnabled(True)
        self._pause_btn.setEnabled(False)
        self._stop_btn.setEnabled(False)

    # --- Public API -------------------------------------------------------

    def set_template_info(self, name: str, total_minutes: int):
        self._template_label.setText(self.tr(f"Template: {name}"))
        self._progress_bar.setMaximum(total_minutes * 60)

    def set_progress(self, elapsed: int, total: int):
        self._progress_bar.setMaximum(total)
        self._progress_bar.setValue(elapsed)
        self._time_label.setText(
            f"{self._format_time(elapsed)} / {self._format_time(total)}"
        )

    # --- Internals --------------------------------------------------------

    @staticmethod
    def _format_time(seconds: int) -> str:
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        return f"{h:02d}:{m:02d}:{s:02d}"


# ---------------------------------------------------------------------------
# Device detail page (composed of the three widgets above)
# ---------------------------------------------------------------------------

class DeviceDetailPage(QWidget):
    """Full-screen page for a single device: charts, data table, controls."""

    back_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._device_id = -1
        self._params_initialized = False
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Back button
        back_btn = QPushButton(self.tr("\u2190 Back"))
        back_btn.setFixedWidth(80)
        back_btn.clicked.connect(self.back_requested.emit)
        layout.addWidget(back_btn)

        # Splitter: data panel (left) | chart (right)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self._data_panel = RealtimeDataPanel()
        self._data_panel.setMinimumWidth(200)

        self._chart_widget = CurveChartWidget()

        splitter.addWidget(self._data_panel)
        splitter.addWidget(self._chart_widget)
        splitter.setSizes([300, 700])
        layout.addWidget(splitter, stretch=1)

        # Control panel at the bottom
        self._control_panel = TestControlPanel()
        layout.addWidget(self._control_panel)

    # --- Public API -------------------------------------------------------

    def set_device(self, device_id: int):
        """Switch the detail view to *device_id*, resetting all state."""
        self._device_id = device_id
        self._params_initialized = False
        self._chart_widget.clear_all_curves()
        self._chart_widget.clear_data()
        self._data_panel.clear_all()

    def current_device_id(self) -> int:
        return self._device_id

    @property
    def data_panel(self) -> RealtimeDataPanel:
        return self._data_panel

    @property
    def chart_widget(self) -> CurveChartWidget:
        return self._chart_widget

    @property
    def control_panel(self) -> TestControlPanel:
        return self._control_panel

    def on_device_data_received(self, data: DeviceData):
        """Feed a :class:`DeviceData` payload into the charts and data panel."""
        if data.device_id != self._device_id:
            return

        # On the first data arrival, create curves for every parameter
        if not self._params_initialized and data.parameters:
            default_colors = {
                "voltage": "#89b4fa", "v": "#89b4fa", "u": "#89b4fa",
                "current": "#f38ba8", "a": "#f38ba8", "i": "#f38ba8",
                "temperature": "#a6e3a1", "t": "#a6e3a1", "temp": "#a6e3a1",
                "power": "#f9e2af", "p": "#f9e2af", "w": "#f9e2af",
            }
            for param_name in data.parameters.keys():
                color = default_colors.get(param_name.lower(), "#cba6f7")
                self._chart_widget.add_curve(param_name, color)
            self._data_panel.setup_parameters(list(data.parameters.keys()))
            self._params_initialized = True

        # Compute a float timestamp from data.timestamp
        ts = data.timestamp or datetime.now()
        t = ts.timestamp() if hasattr(ts, "timestamp") else float(ts)

        for param_name, value in data.parameters.items():
            self._chart_widget.append_data(param_name, t, value)
            self._data_panel.update_parameter(param_name, value)
