"""Test template CRUD manager.

Loads, saves, clones, and deletes :class:`TestTemplate` objects,
serializing phases and thresholds as JSON for database storage.
"""

import copy
import json
import logging

from PyQt6.QtCore import QObject, pyqtSignal

from .common.test_template import TestTemplate, TestPhase, AlarmThreshold
from ..storage.database_manager import DatabaseManager

logger = logging.getLogger(__name__)


class TemplateManager(QObject):
    """Manages the lifecycle of test templates.

    Signals:
        template_updated: Emitted when an existing template is modified
            or deleted.
        template_added: Emitted with the new *template_id* when a new
            template is saved.
    """

    template_updated = pyqtSignal()
    template_added = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._templates: list[TestTemplate] = []

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load_templates(self):
        """Load all templates from the local database."""
        try:
            rows = DatabaseManager.instance().local_db.load_all_templates()
            self._templates = [self._row_to_template(row) for row in rows]
            logger.info("Loaded %d templates", len(self._templates))
        except Exception as e:
            logger.error("Failed to load templates: %s", e)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def templates(self) -> list[TestTemplate]:
        """Return a shallow copy of the template list."""
        return list(self._templates)

    def get_template(self, template_id: int) -> TestTemplate | None:
        """Find a template by its ID."""
        for t in self._templates:
            if t.template_id == template_id:
                return t
        return None

    def get_templates_by_model(self, product_model: str) -> list[TestTemplate]:
        """Return templates matching *product_model*."""
        return [
            t for t in self._templates if t.product_model == product_model
        ]

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def save_template(self, tmpl: TestTemplate):
        """Persist *tmpl* to the database (insert or update)."""
        db = DatabaseManager.instance().local_db
        config = self._template_to_config(tmpl)

        if tmpl.template_id == -1:
            # Insert new template
            tmpl_dict = {
                "name": tmpl.name,
                "product_model": tmpl.product_model,
                "total_duration_minutes": tmpl.total_duration_minutes,
                "collect_params": config["collect_params"],
                "default_thresholds": config["default_thresholds"],
                "phases": config["phases"],
            }
            tmpl.template_id = db.save_template(tmpl_dict)
            self._templates.append(tmpl)
            self.template_added.emit(tmpl.template_id)
        else:
            # Update existing
            tmpl_dict = {
                "template_id": tmpl.template_id,
                "name": tmpl.name,
                "product_model": tmpl.product_model,
                "total_duration_minutes": tmpl.total_duration_minutes,
                "collect_params": config["collect_params"],
                "default_thresholds": config["default_thresholds"],
                "phases": config["phases"],
            }
            db.save_template(tmpl_dict)
            self.template_updated.emit()

    def delete_template(self, template_id: int):
        """Remove a template by ID."""
        DatabaseManager.instance().local_db.delete_template(template_id)
        self._templates = [
            t for t in self._templates if t.template_id != template_id
        ]
        self.template_updated.emit()

    def clone_template(self, template_id: int) -> int:
        """Deep-copy a template and save it with a ``- Copy`` suffix.

        Returns:
            The new template ID, or -1 if the source was not found.
        """
        original = self.get_template(template_id)
        if not original:
            return -1
        cloned = copy.deepcopy(original)
        cloned.template_id = -1
        cloned.name = f"{original.name} - Copy"
        self.save_template(cloned)
        return cloned.template_id

    # ------------------------------------------------------------------
    # Serialization helpers
    # ------------------------------------------------------------------

    def _template_to_config(self, tmpl: TestTemplate) -> dict:
        """Convert a :class:`TestTemplate` into a JSON-serializable dict."""

        def threshold_to_dict(t: AlarmThreshold) -> dict:
            return {
                "upper_limit": t.upper_limit,
                "lower_limit": t.lower_limit,
                "enabled": t.enabled,
            }

        def phase_to_dict(p: TestPhase) -> dict:
            return {
                "name": p.name,
                "duration_minutes": p.duration_minutes,
                "thresholds": {
                    k: threshold_to_dict(v)
                    for k, v in p.thresholds.items()
                },
            }

        return {
            "collect_params": tmpl.collect_params,
            "default_thresholds": {
                k: threshold_to_dict(v)
                for k, v in tmpl.default_thresholds.items()
            },
            "phases": [phase_to_dict(p) for p in tmpl.phases],
        }

    def _row_to_template(self, row: dict) -> TestTemplate:
        """Convert a database row dict into a :class:`TestTemplate`."""

        def dict_to_threshold(d: dict) -> AlarmThreshold:
            return AlarmThreshold(
                upper_limit=d.get("upper_limit", 0),
                lower_limit=d.get("lower_limit", 0),
                enabled=d.get("enabled", False),
            )

        phases = row.get("phases", [])
        if isinstance(phases, str):
            try:
                phases = json.loads(phases)
            except (json.JSONDecodeError, TypeError):
                phases = []

        thresholds = row.get("default_thresholds", {})
        if isinstance(thresholds, str):
            try:
                thresholds = json.loads(thresholds)
            except (json.JSONDecodeError, TypeError):
                thresholds = {}

        collect = row.get("collect_params", {})
        if isinstance(collect, str):
            try:
                collect = json.loads(collect)
            except (json.JSONDecodeError, TypeError):
                collect = {}

        return TestTemplate(
            template_id=row["template_id"],
            name=row["name"],
            product_model=row["product_model"],
            total_duration_minutes=row["total_duration_minutes"],
            collect_params=collect,
            default_thresholds={
                k: dict_to_threshold(v) for k, v in thresholds.items()
            },
            phases=[
                TestPhase(
                    name=p.get("name", ""),
                    duration_minutes=p.get("duration_minutes", 0),
                    thresholds={
                        k: dict_to_threshold(v)
                        for k, v in p.get("thresholds", {}).items()
                    },
                )
                for p in phases
            ],
        )
