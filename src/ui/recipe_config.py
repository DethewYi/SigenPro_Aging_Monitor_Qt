"""Aging recipe configuration page with list view and edit dialog.

Provides CRUD operations for multi-phase aging recipes, including
JSON import/export for cross-project reuse.
"""

import json
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
    QDoubleSpinBox,
    QCheckBox,
    QComboBox,
    QAbstractItemView,
    QMessageBox,
    QSplitter,
    QFormLayout,
    QFileDialog,
    QScrollArea,
    QSizePolicy,
)
from PyQt6.QtCore import Qt

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Recipe Config Page
# ---------------------------------------------------------------------------

class RecipeConfigPage(QWidget):
    """Recipe management page with list + detail panel and CRUD toolbar."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._recipes: list[dict] = []
        self._selected_id: int = -1
        self._setup_ui()
        self.refresh_list()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel(self.tr("Recipe Management"))
        font = title.font()
        font.setPointSize(18)
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)

        # Splitter: left list + right detail
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # --- Left panel ---
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        list_label = QLabel(self.tr("Recipes"))
        list_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        left_layout.addWidget(list_label)

        self._list_widget = QListWidget()
        self._list_widget.currentRowChanged.connect(self._on_selection_changed)
        left_layout.addWidget(self._list_widget)

        splitter.addWidget(left_widget)

        # --- Right panel ---
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(8, 0, 0, 0)

        detail_label = QLabel(self.tr("Recipe Details"))
        detail_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        right_layout.addWidget(detail_label)

        self._detail_label = QLabel(self.tr("Select a recipe to view details."))
        self._detail_label.setWordWrap(True)
        self._detail_label.setTextFormat(Qt.TextFormat.RichText)
        self._detail_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._detail_label.setMinimumHeight(400)
        self._detail_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        right_layout.addWidget(self._detail_label)

        splitter.addWidget(right_widget)
        splitter.setSizes([300, 700])
        layout.addWidget(splitter)

        # --- Bottom toolbar ---
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(0, 8, 0, 0)

        self._btn_new = QPushButton(self.tr("New"))
        self._btn_new.setProperty("style", "primary")
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
        self._btn_delete.setProperty("style", "danger")
        self._btn_delete.setEnabled(False)
        self._btn_delete.clicked.connect(self._on_delete)
        toolbar.addWidget(self._btn_delete)

        toolbar.addStretch()

        self._btn_import = QPushButton(self.tr("Import JSON"))
        self._btn_import.clicked.connect(self._on_import)
        toolbar.addWidget(self._btn_import)

        self._btn_export = QPushButton(self.tr("Export JSON"))
        self._btn_export.setEnabled(False)
        self._btn_export.clicked.connect(self._on_export)
        toolbar.addWidget(self._btn_export)

        layout.addLayout(toolbar)

    # ------------------------------------------------------------------
    # Database access
    # ------------------------------------------------------------------

    def _get_db(self):
        from ..storage.database_manager import DatabaseManager
        return DatabaseManager.instance()

    def refresh_list(self):
        self._recipes = self._get_db().local_db.load_all_recipes()
        self._list_widget.clear()
        for r in self._recipes:
            pn = r.get("product_pn", "")
            name = r.get("name", "")
            text = f"{name}  [{pn}]" if pn else name
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, r.get("recipe_id", -1))
            self._list_widget.addItem(item)

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    def _on_selection_changed(self, row: int):
        if row < 0 or row >= len(self._recipes):
            self._selected_id = -1
            self._detail_label.setText(self.tr("Select a recipe to view details."))
            self._btn_edit.setEnabled(False)
            self._btn_copy.setEnabled(False)
            self._btn_delete.setEnabled(False)
            self._btn_export.setEnabled(False)
            return

        recipe = self._recipes[row]
        self._selected_id = recipe.get("recipe_id", -1)
        self._detail_label.setText(self._format_recipe_detail(recipe))
        self._btn_edit.setEnabled(True)
        self._btn_copy.setEnabled(True)
        self._btn_delete.setEnabled(True)
        self._btn_export.setEnabled(True)

    def _format_recipe_detail(self, recipe: dict) -> str:
        name = recipe.get("name", "")
        pn = recipe.get("product_pn", "")
        max_total = recipe.get("max_total_minutes", 0)

        # Compute total duration from phases
        phases = recipe.get("phases", [])
        total = sum(
            p.get("duration_minutes", 0) if isinstance(p, dict) else 0
            for p in phases
        )
        hours = total // 60
        mins = total % 60
        dur_str = f"{hours}h {mins}m" if hours > 0 else f"{mins}m"

        html = f"<h3>{name}</h3>"
        html += "<table style='font-size: 13px;'>"
        html += f"<tr><td><b>{self.tr('Product PN')}:</b></td><td>{pn}</td></tr>"
        html += f"<tr><td><b>{self.tr('Total Duration')}:</b></td><td>{dur_str}</td></tr>"
        if max_total > 0:
            mh = max_total // 60
            mm = max_total % 60
            html += (
                f"<tr><td><b>{self.tr('Max Total Protection')}:</b></td>"
                f"<td>{mh}h {mm}m</td></tr>"
            )
        html += "</table>"

        # Phases
        if phases:
            html += f"<h4>{self.tr('Phases')}</h4>"
            html += (
                "<table cellpadding='3' style='font-size: 13px;'>"
                "<tr style='background:rgba(255,255,255,0.08);'>"
                f"<th>#</th><th>{self.tr('Name')}</th><th>{self.tr('Duration')}</th>"
                f"<th>{self.tr('Voltage (V)')}</th><th>{self.tr('Current (A)')}</th>"
                f"<th>{self.tr('Power Limit (W)')}</th>"
                "</tr>"
            )
            for i, p in enumerate(phases):
                if not isinstance(p, dict):
                    continue
                pdur = p.get("duration_minutes", 0)
                ph = pdur // 60
                pm = pdur % 60
                pds = f"{ph}h {pm}m" if ph > 0 else f"{pm}m"
                html += (
                    f"<tr><td>{i + 1}</td><td>{p.get('name', '')}</td><td>{pds}</td>"
                    f"<td>{p.get('voltage', 0)}</td><td>{p.get('current', 0)}</td>"
                    f"<td>{p.get('power_limit', 0)}</td></tr>"
                )
                # Phase actions summary
                start_acts = p.get("phase_start_actions", [])
                end_acts = p.get("phase_end_actions", [])
                if start_acts:
                    html += f"<tr><td colspan='6'><small>{self.tr('Start')}: {_format_actions_html(start_acts)}</small></td></tr>"
                if end_acts:
                    html += f"<tr><td colspan='6'><small>{self.tr('End')}: {_format_actions_html(end_acts)}</small></td></tr>"
            html += "</table>"

        # Event actions
        ea = recipe.get("event_actions", {})
        if isinstance(ea, dict):
            for event_key, label in [
                ("on_start", self.tr("On Start")),
                ("on_alarm", self.tr("On Alarm")),
                ("on_complete", self.tr("On Complete")),
            ]:
                actions = ea.get(event_key, [])
                if actions:
                    html += f"<p><b>{label}:</b> {_format_actions_html(actions)}</p>"

        return html

    # ------------------------------------------------------------------
    # CRUD actions
    # ------------------------------------------------------------------

    def _on_new(self):
        dialog = RecipeEditDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_recipe_dict()
            if not data.get("name", "").strip():
                QMessageBox.warning(self, self.tr("Warning"), self.tr("Recipe name is required."))
                return
            self._get_db().local_db.save_recipe(data)
            self.refresh_list()

    def _on_edit(self):
        if self._selected_id < 0:
            return
        recipe = self._get_db().local_db.load_recipe_by_id(self._selected_id)
        if recipe is None:
            return
        dialog = RecipeEditDialog(self)
        dialog.set_recipe(recipe)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_data = dialog.get_recipe_dict()
            new_data["recipe_id"] = self._selected_id
            if not new_data.get("name", "").strip():
                QMessageBox.warning(self, self.tr("Warning"), self.tr("Recipe name is required."))
                return
            self._get_db().local_db.save_recipe(new_data)
            self.refresh_list()

    def _on_copy(self):
        if self._selected_id < 0:
            return
        recipe = self._get_db().local_db.load_recipe_by_id(self._selected_id)
        if recipe is None:
            return
        recipe["recipe_id"] = -1
        recipe["name"] = recipe.get("name", "") + " (Copy)"
        recipe["product_pn"] = ""
        dialog = RecipeEditDialog(self)
        dialog.set_recipe(recipe)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_data = dialog.get_recipe_dict()
            new_data["recipe_id"] = -1
            self._get_db().local_db.save_recipe(new_data)
            self.refresh_list()

    def _on_delete(self):
        if self._selected_id < 0:
            return
        recipe = self._get_db().local_db.load_recipe_by_id(self._selected_id)
        name = recipe.get("name", "") if recipe else ""
        reply = QMessageBox.question(
            self, self.tr("Confirm Delete"),
            self.tr('Are you sure you want to delete recipe "%1"?').replace("%1", name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._get_db().local_db.delete_recipe(self._selected_id)
            self._selected_id = -1
            self._detail_label.setText(self.tr("Select a recipe to view details."))
            for btn in (self._btn_edit, self._btn_copy, self._btn_delete, self._btn_export):
                btn.setEnabled(False)
            self.refresh_list()

    # ------------------------------------------------------------------
    # Import / Export
    # ------------------------------------------------------------------

    def _on_export(self):
        if self._selected_id < 0:
            return
        recipe = self._get_db().local_db.load_recipe_by_id(self._selected_id)
        if not recipe:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, self.tr("Export Recipe"), f"{recipe.get('name', 'recipe')}.json",
            "JSON Files (*.json)",
        )
        if path:
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(recipe, f, ensure_ascii=False, indent=2, default=str)
                QMessageBox.information(self, self.tr("Success"), self.tr("Recipe exported successfully."))
            except Exception as e:
                QMessageBox.critical(self, self.tr("Error"), str(e))

    def _on_import(self):
        path, _ = QFileDialog.getOpenFileName(
            self, self.tr("Import Recipe"), "", "JSON Files (*.json)",
        )
        if not path:
            return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # Validate basic structure
            if not isinstance(data.get("phases"), list):
                raise ValueError("Invalid recipe format: 'phases' must be a list")
            # Clear ID so it creates a new record
            data["recipe_id"] = -1
            self._get_db().local_db.save_recipe(data)
            self.refresh_list()
            QMessageBox.information(self, self.tr("Success"), self.tr("Recipe imported successfully."))
        except Exception as e:
            QMessageBox.critical(self, self.tr("Import Error"), str(e))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_actions_html(actions: list) -> str:
    parts = []
    for a in actions:
        if not isinstance(a, dict):
            continue
        act = a.get("action", "?")
        rid = a.get("relay_id", "?")
        delay = a.get("delay_ms", 0)
        text = f"{'CLOSE' if act.upper() == 'CLOSE' else 'OPEN'} coil {rid}"
        if delay > 0:
            text += f" (d={delay}ms)"
        parts.append(text)
    return ", ".join(parts) if parts else "-"


# ---------------------------------------------------------------------------
# Relay Action Table Helper
# ---------------------------------------------------------------------------

class RelayActionTable(QTableWidget):
    """Table widget for editing relay actions (relay_id, action, delay_ms)."""

    def __init__(self, parent=None):
        super().__init__(0, 3, parent)
        self.setHorizontalHeaderLabels([
            "Relay ID", "Action", "Delay (ms)"
        ])
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

    def add_action(self, relay_id: int = 0, action: str = "CLOSE", delay_ms: int = 0):
        row = self.rowCount()
        self.insertRow(row)
        self.setItem(row, 0, QTableWidgetItem(str(relay_id)))

        combo = QComboBox()
        combo.addItems(["CLOSE", "OPEN"])
        combo.setCurrentText(action.upper())
        self.setCellWidget(row, 1, combo)

        self.setItem(row, 2, QTableWidgetItem(str(delay_ms)))

    def remove_selected(self):
        rows = set(item.row() for item in self.selectedItems())
        for row in sorted(rows, reverse=True):
            self.removeRow(row)

    def get_actions(self) -> list[dict]:
        actions = []
        for row in range(self.rowCount()):
            rid_item = self.item(row, 0)
            combo = self.cellWidget(row, 1)
            delay_item = self.item(row, 2)
            try:
                rid = int(rid_item.text()) if rid_item else 0
            except ValueError:
                rid = 0
            try:
                delay = int(delay_item.text()) if delay_item else 0
            except ValueError:
                delay = 0
            actions.append({
                "relay_id": rid,
                "action": combo.currentText() if combo else "CLOSE",
                "delay_ms": delay,
            })
        return actions

    def set_actions(self, actions: list[dict]):
        self.setRowCount(0)
        for a in actions:
            if isinstance(a, dict):
                self.add_action(
                    a.get("relay_id", 0),
                    a.get("action", "CLOSE"),
                    a.get("delay_ms", 0),
                )


# ---------------------------------------------------------------------------
# Recipe Edit Dialog
# ---------------------------------------------------------------------------

class RecipeEditDialog(QDialog):
    """Dialog for creating or editing an aging recipe with 3 tabs."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(self.tr("Edit Aging Recipe"))
        self.setMinimumSize(800, 700)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        self._tab_widget = QTabWidget()
        layout.addWidget(self._tab_widget)

        self._setup_basic_tab()
        self._setup_phases_tab()
        self._setup_events_tab()

        # OK / Cancel
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_cancel = QPushButton(self.tr("Cancel"))
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)
        btn_ok = QPushButton(self.tr("OK"))
        btn_ok.setProperty("style", "primary")
        btn_ok.setDefault(True)
        btn_ok.clicked.connect(self.accept)
        btn_layout.addWidget(btn_ok)
        layout.addLayout(btn_layout)

    # ------------------------------------------------------------------
    # Tab 1: Basic Info
    # ------------------------------------------------------------------

    def _setup_basic_tab(self):
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)

        # Basic info group
        basic_group = QGroupBox(self.tr("Basic Information"))
        basic_form = QFormLayout()

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText(self.tr("Enter recipe name"))
        basic_form.addRow(self.tr("Name:"), self._name_edit)

        self._pn_edit = QLineEdit()
        self._pn_edit.setPlaceholderText(self.tr("Product PN (unique)"))
        basic_form.addRow(self.tr("Product PN:"), self._pn_edit)

        self._max_total_spin = QSpinBox()
        self._max_total_spin.setRange(0, 999999)
        self._max_total_spin.setSuffix(self.tr(" min (0=disabled)"))
        self._max_total_spin.setValue(0)
        self._max_total_spin.setToolTip(self.tr("Total time protection; 0 means disabled"))
        basic_form.addRow(self.tr("Max Total Time:"), self._max_total_spin)

        basic_group.setLayout(basic_form)
        tab_layout.addWidget(basic_group)

        # Collection parameters group
        collect_group = QGroupBox(self.tr("Collection Parameters"))
        collect_layout = QVBoxLayout()

        self._collect_table = QTableWidget(0, 2)
        self._collect_table.setHorizontalHeaderLabels([
            self.tr("Parameter Name"), self.tr("Frequency (Hz)")
        ])
        self._collect_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._collect_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        collect_layout.addWidget(self._collect_table)

        collect_btns = QHBoxLayout()
        btn_add = QPushButton(self.tr("Add"))
        btn_add.clicked.connect(self._add_collect_row)
        collect_btns.addWidget(btn_add)
        btn_rm = QPushButton(self.tr("Remove"))
        btn_rm.clicked.connect(lambda: self._remove_rows(self._collect_table))
        collect_btns.addWidget(btn_rm)
        collect_btns.addStretch()
        collect_layout.addLayout(collect_btns)
        collect_group.setLayout(collect_layout)
        tab_layout.addWidget(collect_group)

        # Default thresholds group
        thresh_group = QGroupBox(self.tr("Default Thresholds"))
        thresh_layout = QVBoxLayout()

        self._thresh_table = QTableWidget(0, 4)
        self._thresh_table.setHorizontalHeaderLabels([
            self.tr("Parameter"), self.tr("Lower"), self.tr("Upper"), self.tr("Enabled")
        ])
        self._thresh_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._thresh_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        thresh_layout.addWidget(self._thresh_table)

        thresh_btns = QHBoxLayout()
        btn_add_t = QPushButton(self.tr("Add"))
        btn_add_t.clicked.connect(self._add_thresh_row)
        thresh_btns.addWidget(btn_add_t)
        btn_rm_t = QPushButton(self.tr("Remove"))
        btn_rm_t.clicked.connect(lambda: self._remove_rows(self._thresh_table))
        thresh_btns.addWidget(btn_rm_t)
        thresh_btns.addStretch()
        thresh_layout.addLayout(thresh_btns)
        thresh_group.setLayout(thresh_layout)
        tab_layout.addWidget(thresh_group)

        tab_layout.addStretch()
        self._tab_widget.addTab(tab, self.tr("Basic Info"))

    # ------------------------------------------------------------------
    # Tab 2: Phases
    # ------------------------------------------------------------------

    def _setup_phases_tab(self):
        tab = QWidget()
        tab_layout = QHBoxLayout(tab)

        # Left: phase list
        left_layout = QVBoxLayout()
        phase_label = QLabel(self.tr("Phases"))
        phase_label.setStyleSheet("font-weight: bold;")
        left_layout.addWidget(phase_label)

        self._phase_list = QListWidget()
        self._phase_list.currentRowChanged.connect(self._on_phase_selected)
        left_layout.addWidget(self._phase_list)

        phase_btns = QHBoxLayout()
        btn_add_p = QPushButton(self.tr("Add"))
        btn_add_p.clicked.connect(self._add_phase)
        phase_btns.addWidget(btn_add_p)
        btn_rm_p = QPushButton(self.tr("Remove"))
        btn_rm_p.clicked.connect(self._remove_phase)
        phase_btns.addWidget(btn_rm_p)
        btn_up = QPushButton("^")
        btn_up.setFixedWidth(30)
        btn_up.clicked.connect(self._move_phase_up)
        phase_btns.addWidget(btn_up)
        btn_down = QPushButton("v")
        btn_down.setFixedWidth(30)
        btn_down.clicked.connect(self._move_phase_down)
        phase_btns.addWidget(btn_down)
        left_layout.addLayout(phase_btns)

        tab_layout.addLayout(left_layout, stretch=1)

        # Right: phase detail
        right_layout = QVBoxLayout()
        self._phase_detail_widget = QWidget()
        self._phase_detail_layout = QVBoxLayout(self._phase_detail_widget)
        self._phase_detail_layout.setContentsMargins(8, 0, 0, 0)

        form = QFormLayout()
        self._phase_name_edit = QLineEdit()
        form.addRow(self.tr("Phase Name:"), self._phase_name_edit)
        self._phase_dur_spin = QSpinBox()
        self._phase_dur_spin.setRange(0, 999999)
        self._phase_dur_spin.setSuffix(self.tr(" min"))
        form.addRow(self.tr("Duration:"), self._phase_dur_spin)
        self._phase_volt_spin = QDoubleSpinBox()
        self._phase_volt_spin.setRange(0, 99999)
        self._phase_volt_spin.setSuffix(" V")
        self._phase_volt_spin.setDecimals(1)
        form.addRow(self.tr("Voltage:"), self._phase_volt_spin)
        self._phase_curr_spin = QDoubleSpinBox()
        self._phase_curr_spin.setRange(0, 99999)
        self._phase_curr_spin.setSuffix(" A")
        self._phase_curr_spin.setDecimals(1)
        form.addRow(self.tr("Current:"), self._phase_curr_spin)
        self._phase_power_spin = QDoubleSpinBox()
        self._phase_power_spin.setRange(0, 999999)
        self._phase_power_spin.setSuffix(" W")
        self._phase_power_spin.setDecimals(0)
        self._phase_power_spin.setSpecialValueText(self.tr("No limit"))
        form.addRow(self.tr("Power Limit:"), self._phase_power_spin)
        self._phase_detail_layout.addLayout(form)

        # Phase start actions
        start_group = QGroupBox(self.tr("Phase Start Actions"))
        start_layout = QVBoxLayout()
        self._phase_start_table = RelayActionTable()
        start_layout.addWidget(self._phase_start_table)
        start_btns = QHBoxLayout()
        btn_add_sa = QPushButton(self.tr("Add"))
        btn_add_sa.clicked.connect(self._phase_start_table.add_action)
        start_btns.addWidget(btn_add_sa)
        btn_rm_sa = QPushButton(self.tr("Remove"))
        btn_rm_sa.clicked.connect(self._phase_start_table.remove_selected)
        start_btns.addWidget(btn_rm_sa)
        start_btns.addStretch()
        start_layout.addLayout(start_btns)
        start_group.setLayout(start_layout)
        self._phase_detail_layout.addWidget(start_group)

        # Phase end actions
        end_group = QGroupBox(self.tr("Phase End Actions"))
        end_layout = QVBoxLayout()
        self._phase_end_table = RelayActionTable()
        end_layout.addWidget(self._phase_end_table)
        end_btns = QHBoxLayout()
        btn_add_ea = QPushButton(self.tr("Add"))
        btn_add_ea.clicked.connect(self._phase_end_table.add_action)
        end_btns.addWidget(btn_add_ea)
        btn_rm_ea = QPushButton(self.tr("Remove"))
        btn_rm_ea.clicked.connect(self._phase_end_table.remove_selected)
        end_btns.addWidget(btn_rm_ea)
        end_btns.addStretch()
        end_layout.addLayout(end_btns)
        end_group.setLayout(end_layout)
        self._phase_detail_layout.addWidget(end_group)

        self._phase_detail_layout.addStretch()
        tab_layout.addWidget(self._phase_detail_widget, stretch=2)

        self._tab_widget.addTab(tab, self.tr("Phases"))

        # Internal storage for phases
        self._phases_data: list[dict] = []

    def _add_phase(self):
        idx = len(self._phases_data)
        phase = {
            "name": self.tr("Phase %1").replace("%1", str(idx + 1)),
            "duration_minutes": 60,
            "voltage": 0.0,
            "current": 0.0,
            "power_limit": 0.0,
            "phase_start_actions": [],
            "phase_end_actions": [],
        }
        self._phases_data.append(phase)
        self._refresh_phase_list()
        self._phase_list.setCurrentRow(idx)

    def _remove_phase(self):
        row = self._phase_list.currentRow()
        if row < 0:
            return
        self._phases_data.pop(row)
        self._refresh_phase_list()
        # Clear detail
        self._clear_phase_detail()

    def _move_phase_up(self):
        row = self._phase_list.currentRow()
        if row <= 0:
            return
        self._phases_data[row - 1], self._phases_data[row] = (
            self._phases_data[row], self._phases_data[row - 1]
        )
        self._refresh_phase_list()
        self._phase_list.setCurrentRow(row - 1)

    def _move_phase_down(self):
        row = self._phase_list.currentRow()
        if row < 0 or row >= len(self._phases_data) - 1:
            return
        self._phases_data[row], self._phases_data[row + 1] = (
            self._phases_data[row + 1], self._phases_data[row]
        )
        self._refresh_phase_list()
        self._phase_list.setCurrentRow(row + 1)

    def _refresh_phase_list(self):
        self._phase_list.blockSignals(True)
        current = self._phase_list.currentRow()
        self._phase_list.clear()
        for i, p in enumerate(self._phases_data):
            dur = p.get("duration_minutes", 0)
            text = f"{i + 1}. {p.get('name', '')} ({dur}m)"
            self._phase_list.addItem(text)
        if 0 <= current < len(self._phases_data):
            self._phase_list.setCurrentRow(current)
        self._phase_list.blockSignals(False)

    def _on_phase_selected(self, row: int):
        # Save current phase detail before switching
        if not hasattr(self, '_suppress_save') or not self._suppress_save:
            self._save_current_phase_detail()
        if row < 0 or row >= len(self._phases_data):
            self._clear_phase_detail()
            return
        self._load_phase_detail(self._phases_data[row])

    def _clear_phase_detail(self):
        self._phase_name_edit.clear()
        self._phase_dur_spin.setValue(0)
        self._phase_volt_spin.setValue(0)
        self._phase_curr_spin.setValue(0)
        self._phase_power_spin.setValue(0)
        self._phase_start_table.setRowCount(0)
        self._phase_end_table.setRowCount(0)

    def _load_phase_detail(self, phase: dict):
        self._suppress_save = True
        self._phase_name_edit.setText(phase.get("name", ""))
        self._phase_dur_spin.setValue(phase.get("duration_minutes", 0))
        self._phase_volt_spin.setValue(phase.get("voltage", 0))
        self._phase_curr_spin.setValue(phase.get("current", 0))
        self._phase_power_spin.setValue(phase.get("power_limit", 0))
        self._phase_start_table.set_actions(phase.get("phase_start_actions", []))
        self._phase_end_table.set_actions(phase.get("phase_end_actions", []))
        self._suppress_save = False

    def _save_current_phase_detail(self):
        row = self._phase_list.currentRow()
        if row < 0 or row >= len(self._phases_data):
            return
        self._phases_data[row] = {
            "name": self._phase_name_edit.text().strip(),
            "duration_minutes": self._phase_dur_spin.value(),
            "voltage": self._phase_volt_spin.value(),
            "current": self._phase_curr_spin.value(),
            "power_limit": self._phase_power_spin.value(),
            "phase_start_actions": self._phase_start_table.get_actions(),
            "phase_end_actions": self._phase_end_table.get_actions(),
        }

    # ------------------------------------------------------------------
    # Tab 3: Event Actions
    # ------------------------------------------------------------------

    def _setup_events_tab(self):
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)

        for key, label in [
            ("on_start", self.tr("On Start Actions")),
            ("on_alarm", self.tr("On Alarm Actions")),
            ("on_complete", self.tr("On Complete Actions")),
        ]:
            group = QGroupBox(label)
            group_layout = QVBoxLayout()

            table = RelayActionTable()
            group_layout.addWidget(table)

            btns = QHBoxLayout()
            btn_add = QPushButton(self.tr("Add"))
            btn_add.clicked.connect(table.add_action)
            btns.addWidget(btn_add)
            btn_rm = QPushButton(self.tr("Remove"))
            btn_rm.clicked.connect(table.remove_selected)
            btns.addWidget(btn_rm)
            btns.addStretch()
            group_layout.addLayout(btns)
            group.setLayout(group_layout)
            tab_layout.addWidget(group)

            setattr(self, f"_event_{key}_table", table)

        tab_layout.addStretch()
        self._tab_widget.addTab(tab, self.tr("Event Actions"))

    # ------------------------------------------------------------------
    # Table helpers
    # ------------------------------------------------------------------

    def _add_collect_row(self, name: str = "", freq: float = 1.0):
        row = self._collect_table.rowCount()
        self._collect_table.insertRow(row)
        self._collect_table.setItem(row, 0, QTableWidgetItem(name))
        self._collect_table.setItem(row, 1, QTableWidgetItem(str(freq)))

    def _add_thresh_row(self, name: str = "", lower: float = 0.0,
                        upper: float = 0.0, enabled: bool = False):
        row = self._thresh_table.rowCount()
        self._thresh_table.insertRow(row)
        self._thresh_table.setItem(row, 0, QTableWidgetItem(name))
        self._thresh_table.setItem(row, 1, QTableWidgetItem(str(lower)))
        self._thresh_table.setItem(row, 2, QTableWidgetItem(str(upper)))
        chk = QTableWidgetItem()
        chk.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
        chk.setCheckState(Qt.CheckState.Checked if enabled else Qt.CheckState.Unchecked)
        self._thresh_table.setItem(row, 3, chk)

    @staticmethod
    def _remove_rows(table: QTableWidget):
        rows = set(item.row() for item in table.selectedItems())
        for row in sorted(rows, reverse=True):
            table.removeRow(row)

    # ------------------------------------------------------------------
    # set_recipe / get_recipe
    # ------------------------------------------------------------------

    def set_recipe(self, recipe: dict):
        """Populate dialog fields from a recipe dict."""
        self._name_edit.setText(recipe.get("name", ""))
        self._pn_edit.setText(recipe.get("product_pn", ""))
        self._max_total_spin.setValue(recipe.get("max_total_minutes", 0))

        # Collection params
        self._collect_table.setRowCount(0)
        for pname, freq in recipe.get("collect_params", {}).items():
            self._add_collect_row(str(pname), float(freq))

        # Default thresholds
        self._thresh_table.setRowCount(0)
        for pname, thresh in recipe.get("default_thresholds", {}).items():
            if isinstance(thresh, dict):
                self._add_thresh_row(
                    str(pname),
                    thresh.get("lower_limit", 0),
                    thresh.get("upper_limit", 0),
                    thresh.get("enabled", False),
                )

        # Phases
        self._phases_data = []
        for p in recipe.get("phases", []):
            if isinstance(p, dict):
                self._phases_data.append(dict(p))
        self._refresh_phase_list()
        if self._phases_data:
            self._phase_list.setCurrentRow(0)

        # Event actions
        ea = recipe.get("event_actions", {})
        if isinstance(ea, dict):
            self._event_on_start_table.set_actions(ea.get("on_start", []))
            self._event_on_alarm_table.set_actions(ea.get("on_alarm", []))
            self._event_on_complete_table.set_actions(ea.get("on_complete", []))

    def get_recipe_dict(self) -> dict:
        """Return the current dialog state as a recipe dict."""
        # Save current phase detail
        self._save_current_phase_detail()

        # Collect params
        collect: dict = {}
        for row in range(self._collect_table.rowCount()):
            ni = self._collect_table.item(row, 0)
            fi = self._collect_table.item(row, 1)
            if ni and ni.text().strip():
                try:
                    collect[ni.text().strip()] = float(fi.text()) if fi else 1.0
                except (ValueError, TypeError):
                    collect[ni.text().strip()] = 1.0

        # Thresholds
        thresholds: dict = {}
        for row in range(self._thresh_table.rowCount()):
            ni = self._thresh_table.item(row, 0)
            li = self._thresh_table.item(row, 1)
            ui = self._thresh_table.item(row, 2)
            ci = self._thresh_table.item(row, 3)
            if ni and ni.text().strip():
                try:
                    lower = float(li.text()) if li else 0.0
                except (ValueError, TypeError):
                    lower = 0.0
                try:
                    upper = float(ui.text()) if ui else 0.0
                except (ValueError, TypeError):
                    upper = 0.0
                enabled = ci.checkState() == Qt.CheckState.Checked if ci else False
                thresholds[ni.text().strip()] = {
                    "lower_limit": lower, "upper_limit": upper, "enabled": enabled,
                }

        return {
            "name": self._name_edit.text().strip(),
            "product_pn": self._pn_edit.text().strip(),
            "max_total_minutes": self._max_total_spin.value(),
            "collect_params": collect,
            "default_thresholds": thresholds,
            "phases": list(self._phases_data),
            "event_actions": {
                "on_start": self._event_on_start_table.get_actions(),
                "on_alarm": self._event_on_alarm_table.get_actions(),
                "on_complete": self._event_on_complete_table.get_actions(),
            },
        }
