"""Data query page for searching and exporting historical test records."""

import csv
import io
import logging
from datetime import datetime, timedelta

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QDateEdit,
    QFileDialog,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
    QMessageBox,
)
from PyQt6.QtCore import Qt, pyqtSignal, QDate

from ..core.common.types import TestResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data query page
# ---------------------------------------------------------------------------

class DataQueryPage(QWidget):
    """Historical test record query with export capabilities."""

    navigate_to_device_detail = pyqtSignal(int)  # device_id

    # Column indices
    COL_ID = 0
    COL_SN = 1
    COL_PN = 2
    COL_TEMPLATE = 3
    COL_START = 4
    COL_END = 5
    COL_DURATION = 6
    COL_RESULT = 7

    # Result filter enum mapping
    _RESULT_FILTERS = [
        TestResult.PENDING,
        TestResult.PASSED,
        TestResult.FAILED,
        TestResult.INTERRUPTED,
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._records: list[dict] = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # --- Query conditions bar ---
        query_bar = QHBoxLayout()

        # Device combo
        query_bar.addWidget(QLabel(self.tr("Device:")))
        self._device_combo = QComboBox()
        self._device_combo.setMinimumWidth(150)
        self._device_combo.addItem(self.tr("All Devices"), -1)
        query_bar.addWidget(self._device_combo)

        # Date pickers
        query_bar.addWidget(QLabel(self.tr("Start:")))
        self._start_date = QDateEdit()
        self._start_date.setCalendarPopup(True)
        self._start_date.setDate(QDate.currentDate().addDays(-30))
        self._start_date.setDisplayFormat("yyyy-MM-dd")
        query_bar.addWidget(self._start_date)

        query_bar.addWidget(QLabel(self.tr("End:")))
        self._end_date = QDateEdit()
        self._end_date.setCalendarPopup(True)
        self._end_date.setDate(QDate.currentDate())
        self._end_date.setDisplayFormat("yyyy-MM-dd")
        query_bar.addWidget(self._end_date)

        # Result filter
        query_bar.addWidget(QLabel(self.tr("Result:")))
        self._result_filter = QComboBox()
        self._result_filter.addItems([
            self.tr("All"),
            self.tr("Passed"),
            self.tr("Failed"),
            self.tr("Interrupted"),
        ])
        query_bar.addWidget(self._result_filter)

        # Query button
        self._query_btn = QPushButton(self.tr("Query"))
        self._query_btn.setFixedWidth(80)
        self._query_btn.clicked.connect(self._on_query)
        query_bar.addWidget(self._query_btn)

        query_bar.addStretch()
        layout.addLayout(query_bar)

        # --- Export buttons ---
        export_bar = QHBoxLayout()
        self._export_pdf_btn = QPushButton(self.tr("Export PDF"))
        self._export_csv_btn = QPushButton(self.tr("Export CSV"))
        self._export_pdf_btn.clicked.connect(self._export_pdf)
        self._export_csv_btn.clicked.connect(self._export_csv)
        export_bar.addWidget(self._export_pdf_btn)
        export_bar.addWidget(self._export_csv_btn)
        export_bar.addStretch()

        # Stats label
        self._stats_label = QLabel(self.tr("Records: 0"))
        export_bar.addWidget(self._stats_label)
        layout.addLayout(export_bar)

        # --- Results table ---
        self._table = QTableWidget(0, 8)
        headers = [
            self.tr("ID"),
            self.tr("SN"),
            self.tr("PN"),
            self.tr("Template"),
            self.tr("Start Time"),
            self.tr("End Time"),
            self.tr("Duration"),
            self.tr("Result"),
        ]
        self._table.setHorizontalHeaderLabels(headers)

        # Hide the ID column
        self._table.setColumnHidden(self.COL_ID, True)

        # Column sizing
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(self.COL_SN, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_PN, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_TEMPLATE, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(self.COL_START, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_END, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_DURATION, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_RESULT, QHeaderView.ResizeMode.ResizeToContents)

        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)

        # Double-click to navigate to device detail
        self._table.cellDoubleClicked.connect(self._on_cell_double_clicked)

        layout.addWidget(self._table)

    # --- Public API -------------------------------------------------------

    def set_device_list(self, devices: list[dict]):
        """Populate the device combo box.

        *devices*: list of dicts with keys ``device_id``, ``name``.
        """
        self._device_combo.clear()
        self._device_combo.addItem(self.tr("All Devices"), -1)
        for dev in devices:
            self._device_combo.addItem(
                dev.get("name", f"Device {dev['device_id']}"),
                dev["device_id"],
            )

    def load_records(self, records: list[dict]):
        """Populate the table with *records* from DatabaseManager queries.

        Each *record* dict should contain: ``record_id``, ``device_sn``,
        ``device_pn``, template ``name``, ``start_time``, ``end_time``,
        ``result`` (int matching :class:`TestResult`), and optionally
        ``device_id``.
        """
        self._records = list(records)
        self._table.setRowCount(len(records))

        for row, rec in enumerate(records):
            self._table.setItem(
                row, self.COL_ID, QTableWidgetItem(str(rec.get("record_id", "")))
            )
            self._table.setItem(
                row, self.COL_SN, QTableWidgetItem(rec.get("device_sn", ""))
            )
            self._table.setItem(
                row, self.COL_PN, QTableWidgetItem(rec.get("device_pn", ""))
            )
            self._table.setItem(
                row, self.COL_TEMPLATE, QTableWidgetItem(rec.get("template_name", ""))
            )

            start_time = rec.get("start_time", "")
            if start_time:
                try:
                    dt = datetime.fromisoformat(str(start_time))
                    start_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                except (ValueError, TypeError):
                    start_str = str(start_time)
            else:
                start_str = "--"
            self._table.setItem(row, self.COL_START, QTableWidgetItem(start_str))

            end_time = rec.get("end_time", "")
            if end_time:
                try:
                    dt = datetime.fromisoformat(str(end_time))
                    end_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                except (ValueError, TypeError):
                    end_str = str(end_time)
            else:
                end_str = "--"
            self._table.setItem(row, self.COL_END, QTableWidgetItem(end_str))

            # Duration
            duration_str = self._compute_duration(start_time, end_time)
            self._table.setItem(row, self.COL_DURATION, QTableWidgetItem(duration_str))

            # Result
            result_int = rec.get("result", 0)
            result_enum = self._int_to_result(result_int)
            result_item = QTableWidgetItem(self._result_text(result_enum))
            result_item.setForeground(QColor(self._result_color(result_enum)))
            self._table.setItem(row, self.COL_RESULT, result_item)

        self._stats_label.setText(self.tr(f"Records: {len(records)}"))

    # --- Query action -----------------------------------------------------

    def _on_query(self):
        """Emit a signal or call a hook so the application layer can query.

        The actual DB query is delegated via the ``query_requested`` signal
        pattern.  We store the filter state and call ``_do_query`` which the
        application can override, or we query the DatabaseManager directly.
        """
        try:
            from ..storage.database_manager import DatabaseManager
            db = DatabaseManager.instance()
        except Exception:
            logger.warning("DatabaseManager not initialized; cannot query records.")
            return

        if not db.is_initialized:
            QMessageBox.warning(
                self,
                self.tr("Database Not Ready"),
                self.tr("The local database has not been initialized."),
            )
            return

        device_id = self._device_combo.currentData()
        start_dt = datetime(
            self._start_date.date().year(),
            self._start_date.date().month(),
            self._start_date.date().day(),
        )
        end_dt = datetime(
            self._end_date.date().year(),
            self._end_date.date().month(),
            self._end_date.date().day(),
            23, 59, 59,
        )
        result_filter_idx = self._result_filter.currentIndex()

        # Query test_records from local DB
        try:
            records = db.local_db._query_test_records(
                device_id=device_id,
                start=start_dt,
                end=end_dt,
                result_filter=result_filter_idx,
            )
        except AttributeError:
            # Fallback: use a raw SQL approach
            records = self._raw_query_test_records(
                db, device_id, start_dt, end_dt, result_filter_idx
            )

        self.load_records(records)

    def _raw_query_test_records(
        self, db, device_id, start_dt, end_dt, result_filter_idx
    ) -> list[dict]:
        """Query test_records using raw SQL (for when the helper doesn't exist)."""
        query = (
            "SELECT tr.record_id, tr.device_sn, tr.device_pn, "
            "tr.start_time, tr.end_time, tr.result, "
            "tt.name AS template_name, tr.channel_id "
            "FROM test_records tr "
            "LEFT JOIN test_templates tt ON tr.template_id = tt.template_id "
            "WHERE 1=1"
        )
        params: list = []

        if device_id is not None and device_id > 0:
            # device_id may come from channel_id; this is a best-effort match
            pass  # device_id filter handled at a higher level if needed

        query += " AND tr.start_time >= ?"
        params.append(start_dt.isoformat())

        query += " AND tr.start_time <= ?"
        params.append(end_dt.isoformat())

        # Result filter: 0=All, 1=Passed(2), 2=Failed(3), 3=Interrupted(4)
        if result_filter_idx == 1:
            query += " AND tr.result = 2"
        elif result_filter_idx == 2:
            query += " AND tr.result = 3"
        elif result_filter_idx == 3:
            query += " AND tr.result = 4"

        query += " ORDER BY tr.record_id DESC LIMIT 500"

        try:
            rows = db.local_db._conn.execute(query, params).fetchall()
        except Exception:
            logger.exception("Failed to query test records")
            return []

        results = []
        for r in rows:
            results.append({
                "record_id": r[0],
                "device_sn": r[1] or "",
                "device_pn": r[2] or "",
                "start_time": r[3] or "",
                "end_time": r[4] or "",
                "result": r[5],
                "template_name": r[6] or "",
                "channel_id": r[7],
            })
        return results

    # --- Export actions ---------------------------------------------------

    def _export_csv(self):
        """Export visible records to a CSV file."""
        if not self._records:
            QMessageBox.information(self, self.tr("No Data"), self.tr("No records to export."))
            return

        path, _ = QFileDialog.getSaveFileName(
            self, self.tr("Export CSV"), "test_records.csv", "CSV Files (*.csv)"
        )
        if not path:
            return

        try:
            header_keys = [
                "record_id", "device_sn", "device_pn", "template_name",
                "start_time", "end_time", "duration", "result_text",
            ]
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=header_keys)
                writer.writeheader()
                for rec in self._records:
                    writer.writerow({
                        "record_id": rec.get("record_id", ""),
                        "device_sn": rec.get("device_sn", ""),
                        "device_pn": rec.get("device_pn", ""),
                        "template_name": rec.get("template_name", ""),
                        "start_time": rec.get("start_time", ""),
                        "end_time": rec.get("end_time", ""),
                        "duration": self._compute_duration(
                            rec.get("start_time", ""), rec.get("end_time", "")
                        ),
                        "result_text": self._result_text(
                            self._int_to_result(rec.get("result", 0))
                        ),
                    })
            QMessageBox.information(
                self, self.tr("Export Successful"),
                self.tr(f"Exported {len(self._records)} records to CSV."),
            )
        except Exception as e:
            QMessageBox.critical(
                self, self.tr("Export Failed"), self.tr(f"Error: {e}")
            )
            logger.exception("CSV export failed")

    def _export_pdf(self):
        """Export visible records to a PDF file.

        Uses fpdf2 which is already in requirements.txt.
        """
        if not self._records:
            QMessageBox.information(self, self.tr("No Data"), self.tr("No records to export."))
            return

        path, _ = QFileDialog.getSaveFileName(
            self, self.tr("Export PDF"), "test_records.pdf", "PDF Files (*.pdf)"
        )
        if not path:
            return

        try:
            from fpdf import FPDF

            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Helvetica", size=9)

            # Header row
            cols = [
                self.tr("SN"), self.tr("PN"), self.tr("Template"),
                self.tr("Start Time"), self.tr("End Time"),
                self.tr("Duration"), self.tr("Result"),
            ]
            col_widths = [30, 30, 40, 35, 35, 20, 20]
            for i, col in enumerate(cols):
                pdf.cell(col_widths[i], 7, col, border=1)
            pdf.ln()

            # Data rows
            for rec in self._records:
                cells = [
                    str(rec.get("device_sn", ""))[:20],
                    str(rec.get("device_pn", ""))[:20],
                    str(rec.get("template_name", ""))[:25],
                    str(rec.get("start_time", ""))[:19],
                    str(rec.get("end_time", ""))[:19],
                    self._compute_duration(
                        rec.get("start_time", ""), rec.get("end_time", "")
                    ),
                    self._result_text(self._int_to_result(rec.get("result", 0))),
                ]
                for i, cell in enumerate(cells):
                    pdf.cell(col_widths[i], 6, cell, border=1)
                pdf.ln()

            pdf.output(path)
            QMessageBox.information(
                self, self.tr("Export Successful"),
                self.tr(f"Exported {len(self._records)} records to PDF."),
            )
        except Exception as e:
            QMessageBox.critical(
                self, self.tr("Export Failed"), self.tr(f"Error: {e}")
            )
            logger.exception("PDF export failed")

    # --- Internals --------------------------------------------------------

    def _on_cell_double_clicked(self, row: int, _col: int):
        """Navigate to the device detail page for the channel in this row."""
        # Use channel_id to map to a device; the application layer handles
        # the actual mapping.  For now we emit the channel_id.
        id_item = self._table.item(row, self.COL_ID)
        if not id_item:
            return
        record_id = int(id_item.text())
        record = self._records[record_id] if record_id < len(self._records) else None
        if record and record.get("channel_id"):
            # channel_id is used as a proxy for device navigation
            self.navigate_to_device_detail.emit(record["channel_id"])

    @staticmethod
    def _int_to_result(value: int) -> TestResult:
        """Map an integer result code to a :class:`TestResult` enum member."""
        mapping = {0: TestResult.PENDING, 1: TestResult.PASSED, 2: TestResult.PASSED,
                   3: TestResult.FAILED, 4: TestResult.INTERRUPTED}
        return mapping.get(value, TestResult.PENDING)

    @staticmethod
    def _result_text(result: TestResult) -> str:
        texts = {
            TestResult.PENDING: "Pending",
            TestResult.PASSED: "Passed",
            TestResult.FAILED: "Failed",
            TestResult.INTERRUPTED: "Interrupted",
        }
        return texts.get(result, "Unknown")

    @staticmethod
    def _result_color(result: TestResult) -> str:
        colors = {
            TestResult.PENDING: "#6c7086",
            TestResult.PASSED: "#a6e3a1",
            TestResult.FAILED: "#f38ba8",
            TestResult.INTERRUPTED: "#f9e2af",
        }
        return colors.get(result, "#cdd6f4")

    @staticmethod
    def _compute_duration(start_time, end_time) -> str:
        """Return a human-readable duration string between two timestamps."""
        if not start_time or not end_time:
            return "--"
        try:
            start = datetime.fromisoformat(str(start_time))
            end = datetime.fromisoformat(str(end_time))
            delta = end - start
            if delta.total_seconds() < 0:
                return "--"
            total_seconds = int(delta.total_seconds())
            h = total_seconds // 3600
            m = (total_seconds % 3600) // 60
            s = total_seconds % 60
            if h > 0:
                return f"{h}h {m}m {s}s"
            if m > 0:
                return f"{m}m {s}s"
            return f"{s}s"
        except (ValueError, TypeError):
            return "--"
