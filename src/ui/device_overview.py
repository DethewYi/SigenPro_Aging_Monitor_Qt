from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QLineEdit,
    QScrollArea,
    QGridLayout,
    QApplication,
)
from PyQt6.QtCore import Qt, pyqtSignal

from ..core.common.types import DeviceStatus


# ---------------------------------------------------------------------------
# Stats bar — shows aggregate counts for each device status category
# ---------------------------------------------------------------------------

class StatsBarWidget(QWidget):
    """Horizontal bar of status-count cards (Online / Offline / Alarm / Testing)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self._counts: dict[str, QLabel] = {}
        configs = [
            ("Online", "#89b4fa"),
            ("Offline", "#6c7086"),
            ("Alarm", "#f38ba8"),
            ("Testing", "#a6e3a1"),
        ]
        for name, color in configs:
            card = QLabel("0")
            card.setAlignment(Qt.AlignmentFlag.AlignCenter)
            card.setProperty("label", name)
            card.setStyleSheet(
                f"""
                QLabel {{
                    background-color: #313244;
                    border-left: 4px solid {color};
                    border-radius: 6px;
                    padding: 12px;
                    font-size: 24px;
                    font-weight: bold;
                    color: {color};
                }}
                """
            )
            layout.addWidget(card)
            self._counts[name.lower()] = card

    def update_count(self, name: str, count: int):
        card = self._counts.get(name.lower())
        if card:
            card.setText(str(count))


# ---------------------------------------------------------------------------
# Individual device card
# ---------------------------------------------------------------------------

class DeviceCardWidget(QWidget):
    """Compact card representing a single device with status indicator."""

    clicked = pyqtSignal(int)

    STATUS_COLORS = {
        DeviceStatus.TESTING: "#a6e3a1",
        DeviceStatus.IDLE: "#f9e2af",
        DeviceStatus.ALARM: "#f38ba8",
        DeviceStatus.OFFLINE: "#6c7086",
        DeviceStatus.COMPLETED: "#89b4fa",
        DeviceStatus.FAULT: "#fab387",
    }

    STATUS_TEXTS = {
        DeviceStatus.TESTING: "Testing",
        DeviceStatus.IDLE: "Idle",
        DeviceStatus.ALARM: "Alarm",
        DeviceStatus.OFFLINE: "Offline",
        DeviceStatus.COMPLETED: "Completed",
        DeviceStatus.FAULT: "Fault",
    }

    def __init__(self, device_id: int, parent=None):
        super().__init__(parent)
        self.device_id = device_id
        self._status = DeviceStatus.OFFLINE
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(4)

        # Top row: device name + status badge
        top = QHBoxLayout()
        self._name_label = QLabel("--")
        name_font = self._name_label.font()
        name_font.setBold(True)
        self._name_label.setFont(name_font)
        top.addWidget(self._name_label)

        self._status_label = QLabel("Offline")
        self._status_label.setObjectName("status")
        self._status_label.setFixedWidth(64)
        top.addWidget(self._status_label)
        layout.addLayout(top)

        # Model / Serial Number
        self._info_label = QLabel("--")
        self._info_label.setStyleSheet("color: #a6adc8; font-size: 11px;")
        layout.addWidget(self._info_label)

        # Live parameters (voltage, current, etc.)
        self._params_label = QLabel("--")
        self._params_label.setStyleSheet("font-size: 11px;")
        layout.addWidget(self._params_label)

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(120)
        self._apply_style()

    # --- Public API -------------------------------------------------------

    def set_device_info(self, name: str, model: str, sn: str):
        self._name_label.setText(name or "--")
        self._info_label.setText(f"{model or ''} | {sn or ''}")

    def set_status(self, status: DeviceStatus):
        self._status = status
        self._status_label.setText(self.STATUS_TEXTS.get(status, "Unknown"))
        self._apply_style()

    def update_parameters(self, params: dict):
        """Update the parameter display.  *params* keys/values shown as
        ``key: value`` joined by ``|``, capped at 3 entries."""
        parts = [f"{k}: {v:.1f}" for k, v in params.items()]
        self._params_label.setText(" | ".join(parts[:3]) if parts else "--")

    # --- Internals --------------------------------------------------------

    def _apply_style(self):
        color = self.STATUS_COLORS.get(self._status, "#6c7086")
        self.setStyleSheet(
            f"""
            DeviceCardWidget {{
                background-color: #1e1e2e;
                border: 1px solid #45475a;
                border-radius: 8px;
            }}
            DeviceCardWidget:hover {{
                background-color: #313244;
            }}
            """
        )
        self._status_label.setStyleSheet(
            f"background-color: {color}; color: #1e1e2e; "
            f"border-radius: 4px; padding: 2px 6px; "
            f"font-size: 11px; font-weight: bold;"
        )

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.device_id)
        super().mousePressEvent(event)


# ---------------------------------------------------------------------------
# Device Overview page
# ---------------------------------------------------------------------------

class DeviceOverviewPage(QWidget):
    """Full device overview: stats bar, filter bar, and scrollable card grid."""

    device_clicked = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cards: dict[int, DeviceCardWidget] = {}
        self._device_data: dict[int, dict] = {}
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # Stats bar
        self._stats_bar = StatsBarWidget()
        layout.addWidget(self._stats_bar)

        # Filter bar
        filter_layout = QHBoxLayout()

        self._status_filter = QComboBox()
        self._status_filter.addItems(["All", "Testing", "Idle", "Offline", "Alarm"])
        self._status_filter.currentIndexChanged.connect(self._apply_filters)

        self._model_filter = QComboBox()
        self._model_filter.addItem(self.tr("All Models"))

        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText(self.tr("Search by name or SN..."))
        self._search_edit.setFixedWidth(200)
        self._search_edit.setClearButtonEnabled(True)
        self._search_edit.textChanged.connect(self._apply_filters)

        filter_layout.addWidget(QLabel(self.tr("Status:")))
        filter_layout.addWidget(self._status_filter)
        filter_layout.addWidget(QLabel(self.tr("Model:")))
        filter_layout.addWidget(self._model_filter)
        filter_layout.addWidget(self._search_edit)
        filter_layout.addStretch()
        layout.addLayout(filter_layout)

        # Scrollable card grid
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._grid_widget = QWidget()
        self._grid_layout = QGridLayout(self._grid_widget)
        self._grid_layout.setSpacing(8)
        self._scroll.setWidget(self._grid_widget)
        layout.addWidget(self._scroll)

    # --- Public API -------------------------------------------------------

    def add_or_update_device(
        self,
        device_id: int,
        name: str = "",
        model: str = "",
        sn: str = "",
        status: DeviceStatus = DeviceStatus.OFFLINE,
    ):
        if device_id not in self._cards:
            card = DeviceCardWidget(device_id)
            card.clicked.connect(self.device_clicked.emit)
            self._cards[device_id] = card

        card = self._cards[device_id]
        card.set_device_info(name, model, sn)
        card.set_status(status)
        self._device_data[device_id] = {
            "name": name,
            "model": model,
            "sn": sn,
            "status": status,
        }
        self._rebuild_grid()

    def update_device_status(self, device_id: int, status: DeviceStatus):
        if device_id not in self._cards:
            self.add_or_update_device(device_id, status=status)
        else:
            self._cards[device_id].set_status(status)
            self._device_data[device_id]["status"] = status
        self._update_stats()

    def on_device_data_updated(self, data):
        """Called when a :class:`DeviceData` payload arrives from the DataBus."""
        if data.device_id not in self._cards:
            # Auto-create card for unknown device
            name = data.parameters.pop("_name", f"Device {data.device_id}")
            self.add_or_update_device(
                data.device_id, name=name,
                status=DeviceStatus.IDLE if data.communication_ok else DeviceStatus.ALARM,
            )
        self._cards[data.device_id].update_parameters(data.parameters)

    def remove_device(self, device_id: int):
        if device_id in self._cards:
            self._grid_layout.removeWidget(self._cards[device_id])
            self._cards[device_id].deleteLater()
            del self._cards[device_id]
            del self._device_data[device_id]
        self._update_stats()
        self._rebuild_grid()

    # --- Internals --------------------------------------------------------

    def _rebuild_grid(self):
        """Clear and re-populate the grid, adapting column count to width."""
        while self._grid_layout.count():
            item = self._grid_layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

        max_cols = max(1, self._scroll.viewport().width() // 290)
        col = 0
        row = 0
        for device_id, card in sorted(self._cards.items()):
            # Apply visibility filter
            if not self._card_matches_filter(device_id):
                card.hide()
            else:
                card.show()
                self._grid_layout.addWidget(card, row, col)
                col += 1
                if col >= max_cols:
                    col = 0
                    row += 1

    def _update_stats(self):
        """Recompute status counts for the stats bar."""
        counts = {"online": 0, "offline": 0, "alarm": 0, "testing": 0}
        for info in self._device_data.values():
            status = info.get("status", DeviceStatus.OFFLINE)
            if status == DeviceStatus.OFFLINE:
                counts["offline"] += 1
            elif status == DeviceStatus.ALARM or status == DeviceStatus.FAULT:
                counts["alarm"] += 1
            elif status == DeviceStatus.TESTING:
                counts["testing"] += 1
            else:
                counts["online"] += 1
        for name, count in counts.items():
            self._stats_bar.update_count(name, count)

    def _card_matches_filter(self, device_id: int) -> bool:
        """Check if a device card should be visible given current filters."""
        info = self._device_data.get(device_id, {})
        status_filter = self._status_filter.currentText().lower()

        if status_filter != "all":
            status = info.get("status", DeviceStatus.OFFLINE)
            if status.name.lower() != status_filter:
                return False

        search_text = self._search_edit.text().strip().lower()
        if search_text:
            name = info.get("name", "").lower()
            model = info.get("model", "").lower()
            sn = info.get("sn", "").lower()
            if search_text not in name and search_text not in model and search_text not in sn:
                return False

        return True

    def _apply_filters(self):
        """Rebuild grid after filter/search change."""
        self._rebuild_grid()
