"""Alarm panel page with table, filtering, and acknowledge actions."""

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor

from ..core.common.alarm_record import AlarmRecord


# ---------------------------------------------------------------------------
# Alarm panel page
# ---------------------------------------------------------------------------

class AlarmPanelPage(QWidget):
    """Displays alarm records in a table with filtering and acknowledge controls."""

    device_alarm_clicked = pyqtSignal(int)  # device_id

    # Column indices
    COL_ID = 0
    COL_TIME = 1
    COL_DEVICE = 2
    COL_PARAM = 3
    COL_VALUE = 4
    COL_THRESHOLD = 5
    COL_DIRECTION = 6
    COL_STATUS = 7

    def __init__(self, parent=None):
        super().__init__(parent)
        self._alarm_records: dict[int, AlarmRecord] = {}
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # --- Top bar: filter combo + buttons + stats ---
        top_bar = QHBoxLayout()

        top_bar.addWidget(QLabel(self.tr("Filter:")))
        self._filter_combo = QComboBox()
        self._filter_combo.addItems([
            self.tr("All"),
            self.tr("Unacknowledged"),
            self.tr("Acknowledged"),
        ])
        self._filter_combo.currentIndexChanged.connect(self._apply_filter)
        top_bar.addWidget(self._filter_combo)

        top_bar.addStretch()

        # Acknowledge buttons
        self._ack_selected_btn = QPushButton(self.tr("Acknowledge Selected"))
        self._ack_all_btn = QPushButton(self.tr("Acknowledge All"))
        self._ack_selected_btn.clicked.connect(self._acknowledge_selected)
        self._ack_all_btn.clicked.connect(self._acknowledge_all)
        top_bar.addWidget(self._ack_selected_btn)
        top_bar.addWidget(self._ack_all_btn)

        # Stats labels
        self._total_label = QLabel(self.tr("Total: 0"))
        self._unack_label = QLabel(self.tr("Unacknowledged: 0"))
        self._unack_label.setStyleSheet("color: #f38ba8; font-weight: bold;")
        top_bar.addWidget(self._total_label)
        top_bar.addWidget(self._unack_label)

        layout.addLayout(top_bar)

        # --- Alarm table ---
        self._table = QTableWidget(0, 8)
        headers = [
            self.tr("ID"),
            self.tr("Time"),
            self.tr("Device"),
            self.tr("Parameter"),
            self.tr("Value"),
            self.tr("Threshold"),
            self.tr("Direction"),
            self.tr("Status"),
        ]
        self._table.setHorizontalHeaderLabels(headers)

        # Hide the ID column
        self._table.setColumnHidden(self.COL_ID, True)

        # Column sizing
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(self.COL_TIME, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_DEVICE, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_PARAM, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_VALUE, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_THRESHOLD, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_DIRECTION, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_STATUS, QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)

        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.setSortingEnabled(False)

        # Double-click navigates to device detail
        self._table.cellDoubleClicked.connect(self._on_cell_double_clicked)

        layout.addWidget(self._table)

    # --- Public API -------------------------------------------------------

    def add_alarm(self, record: AlarmRecord):
        """Insert a new alarm record at the top of the table."""
        self._alarm_records[record.id] = record

        self._table.insertRow(0)
        row = 0

        self._table.setItem(row, self.COL_ID, QTableWidgetItem(str(record.id)))
        self._table.setItem(row, self.COL_TIME, QTableWidgetItem(
            record.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            if record.timestamp else "--"
        ))
        self._table.setItem(row, self.COL_DEVICE, QTableWidgetItem(
            record.device_name or str(record.device_id)
        ))
        self._table.setItem(row, self.COL_PARAM, QTableWidgetItem(record.param_name))
        self._table.setItem(row, self.COL_VALUE, QTableWidgetItem(
            f"{record.current_value:.3f}"
        ))
        self._table.setItem(row, self.COL_THRESHOLD, QTableWidgetItem(
            f"{record.threshold:.3f}"
        ))
        direction = self.tr("\u2191 High") if record.is_upper_limit else self.tr("\u2193 Low")
        dir_item = QTableWidgetItem(direction)
        if record.is_upper_limit:
            dir_item.setForeground(QColor("#f38ba8"))
        else:
            dir_item.setForeground(QColor("#89b4fa"))
        self._table.setItem(row, self.COL_DIRECTION, dir_item)

        self._update_row_status(row, record.acknowledged)

        self._update_stats()
        self._apply_filter()

    def load_alarms(self, records: list[AlarmRecord]):
        """Replace all alarms with the given list (newest first)."""
        self._table.setRowCount(0)
        self._alarm_records.clear()
        # Insert in reverse so newest ends up at row 0
        for record in reversed(records):
            self.add_alarm(record)

    # --- Internals --------------------------------------------------------

    def _update_row_status(self, row: int, acknowledged: bool):
        status_text = self.tr("Acknowledged") if acknowledged else self.tr("Unacknowledged")
        status_item = QTableWidgetItem(status_text)
        if not acknowledged:
            # Highlight unacknowledged rows with a red tint
            bg = QColor("#45262a")  # dark red-ish
            status_item.setForeground(QColor("#f38ba8"))
            for col in range(self._table.columnCount()):
                existing = self._table.item(row, col)
                if existing:
                    existing.setBackground(bg)
        status_item.setBackground(
            self._table.item(row, 0).background() if self._table.item(row, 0) else QColor()
        )
        self._table.setItem(row, self.COL_STATUS, status_item)

    def _apply_filter(self):
        """Show/hide rows based on the current filter combo selection."""
        filter_index = self._filter_combo.currentIndex()
        for row in range(self._table.rowCount()):
            id_item = self._table.item(row, self.COL_ID)
            if not id_item:
                continue
            alarm_id = int(id_item.text())
            record = self._alarm_records.get(alarm_id)
            if record is None:
                self._table.setRowHidden(row, True)
                continue

            if filter_index == 0:  # All
                self._table.setRowHidden(row, False)
            elif filter_index == 1:  # Unacknowledged
                self._table.setRowHidden(row, record.acknowledged)
            elif filter_index == 2:  # Acknowledged
                self._table.setRowHidden(row, not record.acknowledged)

    def _update_stats(self):
        total = len(self._alarm_records)
        unack = sum(1 for r in self._alarm_records.values() if not r.acknowledged)
        self._total_label.setText(self.tr(f"Total: {total}"))
        self._unack_label.setText(self.tr(f"Unacknowledged: {unack}"))

    def _acknowledge_selected(self):
        """Mark the currently selected alarm(s) as acknowledged."""
        rows = set()
        for item in self._table.selectedItems():
            rows.add(item.row())

        for row in sorted(rows, reverse=True):
            id_item = self._table.item(row, self.COL_ID)
            if not id_item:
                continue
            alarm_id = int(id_item.text())
            record = self._alarm_records.get(alarm_id)
            if record and not record.acknowledged:
                record.acknowledged = True
                self._update_row_status(row, True)

        self._update_stats()
        self._apply_filter()

    def _acknowledge_all(self):
        """Mark every alarm as acknowledged."""
        for row in range(self._table.rowCount()):
            id_item = self._table.item(row, self.COL_ID)
            if not id_item:
                continue
            alarm_id = int(id_item.text())
            record = self._alarm_records.get(alarm_id)
            if record:
                record.acknowledged = True
                self._update_row_status(row, True)

        self._update_stats()

    def _on_cell_double_clicked(self, row: int, _col: int):
        """Emit device_alarm_clicked when a row is double-clicked."""
        id_item = self._table.item(row, self.COL_ID)
        if not id_item:
            return
        alarm_id = int(id_item.text())
        record = self._alarm_records.get(alarm_id)
        if record:
            self.device_alarm_clicked.emit(record.device_id)
