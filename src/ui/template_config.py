"""Template configuration page with list view and edit dialog."""

import logging

from PyQt6.QtWidgets import (
    QWidget,
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QGroupBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QTabWidget,
    QSpinBox,
    QCheckBox,
    QAbstractItemView,
    QMessageBox,
    QSplitter,
    QFormLayout,
    QScrollArea,
    QSizePolicy,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIntValidator

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Template Config Page
# ---------------------------------------------------------------------------

class TemplateConfigPage(QWidget):
    """Template management page with list + detail panel and CRUD toolbar."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._templates: list[dict] = []
        self._selected_id: int = -1
        self._setup_ui()
        self.refresh_list()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # Splitter: left list + right detail
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # --- Left panel: template list ---
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        list_label = QLabel(self.tr("Templates"))
        list_label.setStyleSheet("font-weight: bold;")
        left_layout.addWidget(list_label)

        self._list_widget = QListWidget()
        self._list_widget.currentRowChanged.connect(self._on_selection_changed)
        left_layout.addWidget(self._list_widget)

        splitter.addWidget(left_widget)

        # --- Right panel: detail view ---
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        detail_label = QLabel(self.tr("Template Details"))
        detail_label.setStyleSheet("font-weight: bold;")
        right_layout.addWidget(detail_label)

        self._detail_label = QLabel(self.tr("Select a template to view details."))
        self._detail_label.setWordWrap(True)
        self._detail_label.setTextFormat(Qt.TextFormat.RichText)
        self._detail_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._detail_label.setStyleSheet(
            "padding: 8px; border: 1px solid palette(mid); "
            "background-color: transparent; "
            "border-radius: 4px; font-size: 13px;"
        )
        right_layout.addWidget(self._detail_label)

        splitter.addWidget(right_widget)
        splitter.setSizes([300, 700])
        layout.addWidget(splitter)

        # --- Bottom toolbar ---
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(0, 8, 0, 0)

        self._btn_new = QPushButton(self.tr("New"))
        self._btn_new.clicked.connect(self._on_new)
        toolbar.addWidget(self._btn_new)

        self._btn_edit = QPushButton(self.tr("Edit"))
        self._btn_edit.setEnabled(False)
        self._btn_edit.clicked.connect(self._on_edit)
        toolbar.addWidget(self._btn_edit)

        self._btn_copy = QPushButton(self.tr("Copy"))
        self._btn_copy.setEnabled(False)
        self._btn_copy.clicked.connect(self._on_copy)
        toolbar.addWidget(self._btn_copy)

        self._btn_delete = QPushButton(self.tr("Delete"))
        self._btn_delete.setEnabled(False)
        self._btn_delete.clicked.connect(self._on_delete)
        toolbar.addWidget(self._btn_delete)

        toolbar.addStretch()
        layout.addLayout(toolbar)

    # ------------------------------------------------------------------
    # Database access
    # ------------------------------------------------------------------

    def _get_db(self):
        """Lazily import and return the DatabaseManager singleton."""
        from ..storage.database_manager import DatabaseManager
        return DatabaseManager.instance()

    def refresh_list(self):
        """Reload templates from database and refresh the list widget."""
        self._templates = self._get_db().local_db.load_all_templates()
        self._list_widget.clear()
        for tmpl in self._templates:
            item = QListWidgetItem(tmpl.get("name", ""))
            item.setData(Qt.ItemDataRole.UserRole, tmpl.get("template_id", -1))
            self._list_widget.addItem(item)

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    def _on_selection_changed(self, row: int):
        if row < 0 or row >= len(self._templates):
            self._selected_id = -1
            self._detail_label.setText(self.tr("Select a template to view details."))
            self._btn_edit.setEnabled(False)
            self._btn_copy.setEnabled(False)
            self._btn_delete.setEnabled(False)
            return

        tmpl = self._templates[row]
        self._selected_id = tmpl.get("template_id", -1)
        self._detail_label.setText(self._format_template_detail(tmpl))
        self._btn_edit.setEnabled(True)
        self._btn_copy.setEnabled(True)
        self._btn_delete.setEnabled(True)

    def _format_template_detail(self, tmpl: dict) -> str:
        """Return rich-text HTML representation of a template."""
        name = tmpl.get("name", "")
        model = tmpl.get("product_model", "")
        duration = tmpl.get("total_duration_minutes", 0)
        hours = duration // 60
        mins = duration % 60
        duration_str = f"{hours}h {mins}m" if hours > 0 else f"{mins}m"

        html = f"""
        <h3>{name}</h3>
        <table style="font-size: 13px;">
        <tr><td><b>{self.tr("Product Model")}:</b></td><td>{model}</td></tr>
        <tr><td><b>{self.tr("Duration")}:</b></td><td>{duration_str}</td></tr>
        </table>
        """

        # Collection parameters
        collect = tmpl.get("collect_params", {})
        if collect:
            html += f"<h4>{self.tr('Collection Parameters')}</h4>"
            html += "<table cellpadding='3' style='font-size: 13px;'>"
            html += f"<tr style='background:rgba(255,255,255,0.08);'><th>{self.tr('Parameter')}</th><th>{self.tr('Frequency (Hz)')}</th></tr>"
            for pname, freq in collect.items():
                html += f"<tr><td>{pname}</td><td>{freq}</td></tr>"
            html += "</table>"

        # Default thresholds
        thresholds = tmpl.get("default_thresholds", {})
        if thresholds:
            html += f"<h4>{self.tr('Default Thresholds')}</h4>"
            html += "<table cellpadding='3' style='font-size: 13px;'>"
            html += (
                f"<tr style='background:rgba(255,255,255,0.08);'>"
                f"<th>{self.tr('Parameter')}</th>"
                f"<th>{self.tr('Lower')}</th>"
                f"<th>{self.tr('Upper')}</th>"
                f"<th>{self.tr('Enabled')}</th>"
                f"</tr>"
            )
            for pname, thresh in thresholds.items():
                if isinstance(thresh, dict):
                    lower = thresh.get("lower_limit", 0)
                    upper = thresh.get("upper_limit", 0)
                    enabled = thresh.get("enabled", False)
                else:
                    lower, upper, enabled = 0, 0, False
                html += (
                    f"<tr><td>{pname}</td><td>{lower}</td>"
                    f"<td>{upper}</td><td>{self.tr('Yes') if enabled else self.tr('No')}</td></tr>"
                )
            html += "</table>"

        # Phases
        phases = tmpl.get("phases", [])
        if phases:
            html += f"<h4>{self.tr('Test Phases')}</h4>"
            for phase in phases:
                pname = phase.get("name", "") if isinstance(phase, dict) else str(phase)
                pdur = phase.get("duration_minutes", 0) if isinstance(phase, dict) else 0
                pthresh = phase.get("thresholds", {}) if isinstance(phase, dict) else {}
                ph = pdur // 60
                pm = pdur % 60
                dur_str = f"{ph}h {pm}m" if ph > 0 else f"{pm}m"
                html += f"<p><b>{pname}</b> ({dur_str})"
                if pthresh:
                    html += "<br><small>"
                    for k, v in pthresh.items():
                        if isinstance(v, dict):
                            html += f"&nbsp;&nbsp;{k}: [{v.get('lower_limit', '')}, {v.get('upper_limit', '')}]"
                    html += "</small>"
                html += "</p>"

        return html

    # ------------------------------------------------------------------
    # CRUD actions
    # ------------------------------------------------------------------

    def _on_new(self):
        dialog = TemplateEditDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            tmpl = dialog.get_template()
            if not tmpl.get("name", "").strip():
                QMessageBox.warning(self, self.tr("Warning"), self.tr("Template name is required."))
                return
            self._get_db().local_db.save_template(tmpl)
            self.refresh_list()

    def _on_edit(self):
        if self._selected_id < 0:
            return
        tmpl = self._get_db().local_db.load_template(self._selected_id)
        if tmpl is None:
            return
        dialog = TemplateEditDialog(self)
        dialog.set_template(tmpl)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_tmpl = dialog.get_template()
            new_tmpl["template_id"] = self._selected_id
            if not new_tmpl.get("name", "").strip():
                QMessageBox.warning(self, self.tr("Warning"), self.tr("Template name is required."))
                return
            self._get_db().local_db.save_template(new_tmpl)
            self.refresh_list()

    def _on_copy(self):
        if self._selected_id < 0:
            return
        tmpl = self._get_db().local_db.load_template(self._selected_id)
        if tmpl is None:
            return
        tmpl["template_id"] = -1
        tmpl["name"] = tmpl.get("name", "") + " (Copy)"
        dialog = TemplateEditDialog(self)
        dialog.set_template(tmpl)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_tmpl = dialog.get_template()
            new_tmpl["template_id"] = -1
            if not new_tmpl.get("name", "").strip():
                QMessageBox.warning(self, self.tr("Warning"), self.tr("Template name is required."))
                return
            self._get_db().local_db.save_template(new_tmpl)
            self.refresh_list()

    def _on_delete(self):
        if self._selected_id < 0:
            return
        tmpl = self._get_db().local_db.load_template(self._selected_id)
        name = tmpl.get("name", "") if tmpl else ""
        reply = QMessageBox.question(
            self,
            self.tr("Confirm Delete"),
            self.tr("Are you sure you want to delete template \"%1\"?").replace("%1", name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._get_db().local_db.delete_template(self._selected_id)
            self._selected_id = -1
            self._detail_label.setText(self.tr("Select a template to view details."))
            self._btn_edit.setEnabled(False)
            self._btn_copy.setEnabled(False)
            self._btn_delete.setEnabled(False)
            self.refresh_list()


# ---------------------------------------------------------------------------
# Template Edit Dialog
# ---------------------------------------------------------------------------

class TemplateEditDialog(QDialog):
    """Dialog for creating or editing a test template."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Edit Template"))
        self.setMinimumSize(700, 600)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # --- Basic info group ---
        basic_group = QGroupBox(self.tr("Basic Information"))
        basic_form = QFormLayout()

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText(self.tr("Enter template name"))
        basic_form.addRow(self.tr("Name:"), self._name_edit)

        self._model_edit = QLineEdit()
        self._model_edit.setPlaceholderText(self.tr("Enter product model"))
        basic_form.addRow(self.tr("Product Model:"), self._model_edit)

        self._duration_spin = QSpinBox()
        self._duration_spin.setRange(1, 999999)
        self._duration_spin.setSuffix(self.tr(" minutes"))
        self._duration_spin.setValue(60)
        basic_form.addRow(self.tr("Duration:"), self._duration_spin)

        basic_group.setLayout(basic_form)
        layout.addWidget(basic_group)

        # --- Collection parameters group ---
        collect_group = QGroupBox(self.tr("Collection Parameters"))
        collect_layout = QVBoxLayout()

        self._collect_table = QTableWidget(0, 2)
        self._collect_table.setHorizontalHeaderLabels([
            self.tr("Parameter Name"),
            self.tr("Frequency (Hz)"),
        ])
        self._collect_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._collect_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        collect_layout.addWidget(self._collect_table)

        collect_btns = QHBoxLayout()
        btn_add_collect = QPushButton(self.tr("Add"))
        btn_add_collect.clicked.connect(self._add_collect_row)
        collect_btns.addWidget(btn_add_collect)

        btn_remove_collect = QPushButton(self.tr("Remove"))
        btn_remove_collect.clicked.connect(self._remove_collect_row)
        collect_btns.addWidget(btn_remove_collect)

        collect_btns.addStretch()
        collect_layout.addLayout(collect_btns)

        collect_group.setLayout(collect_layout)
        layout.addWidget(collect_group)

        # --- Default thresholds group ---
        thresh_group = QGroupBox(self.tr("Default Thresholds"))
        thresh_layout = QVBoxLayout()

        self._thresh_table = QTableWidget(0, 4)
        self._thresh_table.setHorizontalHeaderLabels([
            self.tr("Parameter Name"),
            self.tr("Lower Limit"),
            self.tr("Upper Limit"),
            self.tr("Enabled"),
        ])
        self._thresh_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._thresh_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        thresh_layout.addWidget(self._thresh_table)

        thresh_btns = QHBoxLayout()
        btn_add_thresh = QPushButton(self.tr("Add"))
        btn_add_thresh.clicked.connect(self._add_thresh_row)
        thresh_btns.addWidget(btn_add_thresh)

        btn_remove_thresh = QPushButton(self.tr("Remove"))
        btn_remove_thresh.clicked.connect(self._remove_thresh_row)
        thresh_btns.addWidget(btn_remove_thresh)

        thresh_btns.addStretch()
        thresh_layout.addLayout(thresh_btns)

        thresh_group.setLayout(thresh_layout)
        layout.addWidget(thresh_group)

        # --- Test phases group ---
        phases_group = QGroupBox(self.tr("Test Phases"))
        phases_layout = QVBoxLayout()

        phase_btns = QHBoxLayout()
        btn_add_phase = QPushButton(self.tr("Add Phase"))
        btn_add_phase.clicked.connect(self._add_phase_tab)
        phase_btns.addWidget(btn_add_phase)

        btn_remove_phase = QPushButton(self.tr("Remove Phase"))
        btn_remove_phase.clicked.connect(self._remove_phase_tab)
        phase_btns.addWidget(btn_remove_phase)

        phase_btns.addStretch()
        phases_layout.addLayout(phase_btns)

        self._phase_tabs = QTabWidget()
        phases_layout.addWidget(self._phase_tabs)

        phases_group.setLayout(phases_layout)
        layout.addWidget(phases_group)

        # --- OK / Cancel ---
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        btn_cancel = QPushButton(self.tr("Cancel"))
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        btn_ok = QPushButton(self.tr("OK"))
        btn_ok.setDefault(True)
        btn_ok.clicked.connect(self.accept)
        btn_layout.addWidget(btn_ok)

        layout.addLayout(btn_layout)

    # ------------------------------------------------------------------
    # Collection parameter rows
    # ------------------------------------------------------------------

    def _add_collect_row(self, name: str = "", freq: float = 1.0):
        row = self._collect_table.rowCount()
        self._collect_table.insertRow(row)
        self._collect_table.setItem(row, 0, QTableWidgetItem(name))
        self._collect_table.setItem(row, 1, QTableWidgetItem(str(freq)))

    def _remove_collect_row(self):
        rows = set()
        for item in self._collect_table.selectedItems():
            rows.add(item.row())
        for row in sorted(rows, reverse=True):
            self._collect_table.removeRow(row)

    # ------------------------------------------------------------------
    # Threshold rows
    # ------------------------------------------------------------------

    def _add_thresh_row(self, name: str = "", lower: float = 0.0,
                        upper: float = 0.0, enabled: bool = False):
        row = self._thresh_table.rowCount()
        self._thresh_table.insertRow(row)
        self._thresh_table.setItem(row, 0, QTableWidgetItem(name))
        self._thresh_table.setItem(row, 1, QTableWidgetItem(str(lower)))
        self._thresh_table.setItem(row, 2, QTableWidgetItem(str(upper)))

        chk_item = QTableWidgetItem()
        chk_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
        chk_item.setCheckState(
            Qt.CheckState.Checked if enabled else Qt.CheckState.Unchecked
        )
        self._thresh_table.setItem(row, 3, chk_item)

    def _remove_thresh_row(self):
        rows = set()
        for item in self._thresh_table.selectedItems():
            rows.add(item.row())
        for row in sorted(rows, reverse=True):
            self._thresh_table.removeRow(row)

    # ------------------------------------------------------------------
    # Phase tabs
    # ------------------------------------------------------------------

    def _add_phase_tab(self, name: str = "", duration: int = 0,
                       thresholds: dict | None = None):
        if thresholds is None:
            thresholds = {}

        tab_widget = QWidget()
        tab_layout = QVBoxLayout(tab_widget)

        phase_form = QHBoxLayout()
        phase_form.addWidget(QLabel(self.tr("Phase Name:")))
        name_edit = QLineEdit(name)
        phase_form.addWidget(name_edit)
        phase_form.addWidget(QLabel(self.tr("Duration (min):")))
        dur_spin = QSpinBox()
        dur_spin.setRange(1, 999999)
        dur_spin.setValue(duration)
        phase_form.addWidget(dur_spin)
        tab_layout.addLayout(phase_form)

        thresh_label = QLabel(self.tr("Phase Thresholds:"))
        thresh_label.setStyleSheet("font-weight: bold;")
        tab_layout.addWidget(thresh_label)

        phase_table = QTableWidget(0, 4)
        phase_table.setHorizontalHeaderLabels([
            self.tr("Parameter Name"),
            self.tr("Lower Limit"),
            self.tr("Upper Limit"),
            self.tr("Enabled"),
        ])
        phase_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        phase_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

        for pname, thresh in thresholds.items():
            row = phase_table.rowCount()
            phase_table.insertRow(row)
            phase_table.setItem(row, 0, QTableWidgetItem(pname))
            if isinstance(thresh, dict):
                phase_table.setItem(row, 1, QTableWidgetItem(str(thresh.get("lower_limit", 0))))
                phase_table.setItem(row, 2, QTableWidgetItem(str(thresh.get("upper_limit", 0))))
                enabled = thresh.get("enabled", False)
            else:
                phase_table.setItem(row, 1, QTableWidgetItem("0"))
                phase_table.setItem(row, 2, QTableWidgetItem("0"))
                enabled = False
            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            chk.setCheckState(Qt.CheckState.Checked if enabled else Qt.CheckState.Unchecked)
            phase_table.setItem(row, 3, chk)

        phase_btns = QHBoxLayout()
        btn_add = QPushButton(self.tr("Add"))
        btn_add.clicked.connect(lambda: self._add_phase_thresh_row(phase_table))
        phase_btns.addWidget(btn_add)
        btn_rm = QPushButton(self.tr("Remove"))
        btn_rm.clicked.connect(lambda: self._remove_table_rows(phase_table))
        phase_btns.addWidget(btn_rm)
        phase_btns.addStretch()
        tab_layout.addLayout(phase_btns)

        tab_layout.addWidget(phase_table)

        tab_title = name if name else self.tr("Phase %1").replace(
            "%1", str(self._phase_tabs.count() + 1)
        )
        idx = self._phase_tabs.addTab(tab_widget, tab_title)

        # Store references on the widget for retrieval
        tab_widget.setProperty("_name_edit", name_edit)
        tab_widget.setProperty("_dur_spin", dur_spin)
        tab_widget.setProperty("_thresh_table", phase_table)

    def _remove_phase_tab(self):
        idx = self._phase_tabs.currentIndex()
        if idx >= 0:
            self._phase_tabs.removeTab(idx)

    def _add_phase_thresh_row(self, table: QTableWidget):
        row = table.rowCount()
        table.insertRow(row)
        table.setItem(row, 0, QTableWidgetItem(""))
        table.setItem(row, 1, QTableWidgetItem("0"))
        table.setItem(row, 2, QTableWidgetItem("0"))
        chk = QTableWidgetItem()
        chk.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
        chk.setCheckState(Qt.CheckState.Unchecked)
        table.setItem(row, 3, chk)

    @staticmethod
    def _remove_table_rows(table: QTableWidget):
        rows = set()
        for item in table.selectedItems():
            rows.add(item.row())
        for row in sorted(rows, reverse=True):
            table.removeRow(row)

    # ------------------------------------------------------------------
    # set_template / get_template
    # ------------------------------------------------------------------

    def set_template(self, tmpl: dict):
        """Populate the dialog fields from a template dict."""
        self._name_edit.setText(tmpl.get("name", ""))
        self._model_edit.setText(tmpl.get("product_model", ""))
        self._duration_spin.setValue(tmpl.get("total_duration_minutes", 60))

        # Collection parameters
        self._collect_table.setRowCount(0)
        for pname, freq in tmpl.get("collect_params", {}).items():
            self._add_collect_row(pname, freq)

        # Default thresholds
        self._thresh_table.setRowCount(0)
        for pname, thresh in tmpl.get("default_thresholds", {}).items():
            if isinstance(thresh, dict):
                self._add_thresh_row(
                    pname,
                    thresh.get("lower_limit", 0),
                    thresh.get("upper_limit", 0),
                    thresh.get("enabled", False),
                )
            else:
                self._add_thresh_row(pname)

        # Phases
        self._phase_tabs.clear()
        for phase in tmpl.get("phases", []):
            if isinstance(phase, dict):
                self._add_phase_tab(
                    phase.get("name", ""),
                    phase.get("duration_minutes", 0),
                    phase.get("thresholds", {}),
                )

    def get_template(self) -> dict:
        """Return the current dialog state as a template dict."""
        # Collection parameters
        collect_params: dict[str, float] = {}
        for row in range(self._collect_table.rowCount()):
            name_item = self._collect_table.item(row, 0)
            freq_item = self._collect_table.item(row, 1)
            if name_item and name_item.text().strip():
                try:
                    freq = float(freq_item.text()) if freq_item else 1.0
                except (ValueError, TypeError):
                    freq = 1.0
                collect_params[name_item.text().strip()] = freq

        # Default thresholds
        default_thresholds: dict[str, dict] = {}
        for row in range(self._thresh_table.rowCount()):
            name_item = self._thresh_table.item(row, 0)
            lower_item = self._thresh_table.item(row, 1)
            upper_item = self._thresh_table.item(row, 2)
            chk_item = self._thresh_table.item(row, 3)
            if name_item and name_item.text().strip():
                try:
                    lower = float(lower_item.text()) if lower_item else 0.0
                except (ValueError, TypeError):
                    lower = 0.0
                try:
                    upper = float(upper_item.text()) if upper_item else 0.0
                except (ValueError, TypeError):
                    upper = 0.0
                enabled = (
                    chk_item.checkState() == Qt.CheckState.Checked
                    if chk_item else False
                )
                default_thresholds[name_item.text().strip()] = {
                    "lower_limit": lower,
                    "upper_limit": upper,
                    "enabled": enabled,
                }

        # Phases
        phases: list[dict] = []
        for i in range(self._phase_tabs.count()):
            tab = self._phase_tabs.widget(i)
            name_edit = tab.property("_name_edit")
            dur_spin = tab.property("_dur_spin")
            thresh_table = tab.property("_thresh_table")

            phase_thresh: dict[str, dict] = {}
            for row in range(thresh_table.rowCount()):
                tn_item = thresh_table.item(row, 0)
                tl_item = thresh_table.item(row, 1)
                tu_item = thresh_table.item(row, 2)
                tc_item = thresh_table.item(row, 3)
                if tn_item and tn_item.text().strip():
                    try:
                        tl = float(tl_item.text()) if tl_item else 0.0
                    except (ValueError, TypeError):
                        tl = 0.0
                    try:
                        tu = float(tu_item.text()) if tu_item else 0.0
                    except (ValueError, TypeError):
                        tu = 0.0
                    te = tc_item.checkState() == Qt.CheckState.Checked if tc_item else False
                    phase_thresh[tn_item.text().strip()] = {
                        "lower_limit": tl,
                        "upper_limit": tu,
                        "enabled": te,
                    }

            phases.append({
                "name": name_edit.text() if name_edit else "",
                "duration_minutes": dur_spin.value() if dur_spin else 0,
                "thresholds": phase_thresh,
            })

        return {
            "name": self._name_edit.text().strip(),
            "product_model": self._model_edit.text().strip(),
            "collect_params": collect_params,
            "total_duration_minutes": self._duration_spin.value(),
            "default_thresholds": default_thresholds,
            "phases": phases,
        }
