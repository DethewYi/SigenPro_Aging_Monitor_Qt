"""Aging recipe CRUD manager.

Loads, saves, clones, and deletes :class:`AgingRecipe` objects,
serializing phases and event actions as JSON for database storage.
"""

import copy
import json
import logging

from PyQt6.QtCore import QObject, pyqtSignal

from .common.aging_recipe import AgingRecipe
from ..storage.database_manager import DatabaseManager

logger = logging.getLogger(__name__)


class RecipeManager(QObject):
    """Manages the lifecycle of aging recipes.

    Signals:
        recipe_updated: Emitted when an existing recipe is modified or deleted.
        recipe_added: Emitted with the new *recipe_id* when a new recipe is saved.
    """

    recipe_updated = pyqtSignal()
    recipe_added = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._recipes: list[AgingRecipe] = []

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load_recipes(self):
        """Load all recipes from the local database."""
        try:
            rows = DatabaseManager.instance().local_db.load_all_recipes()
            self._recipes = [self._row_to_recipe(row) for row in rows]
            logger.info("Loaded %d aging recipes", len(self._recipes))
        except Exception as e:
            logger.error("Failed to load aging recipes: %s", e)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def recipes(self) -> list[AgingRecipe]:
        """Return a shallow copy of the recipe list."""
        return list(self._recipes)

    def get_recipe(self, recipe_id: int) -> AgingRecipe | None:
        """Find a recipe by its ID."""
        for r in self._recipes:
            if r.recipe_id == recipe_id:
                return r
        return None

    def get_recipe_by_pn(self, product_pn: str) -> AgingRecipe | None:
        """Find a recipe by product PN."""
        for r in self._recipes:
            if r.product_pn == product_pn:
                return r
        return None

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def save_recipe(self, recipe: AgingRecipe):
        """Persist *recipe* to the database (insert or update)."""
        db = DatabaseManager.instance().local_db
        config = recipe.to_dict()

        if recipe.recipe_id == -1:
            del config["recipe_id"]
            recipe.recipe_id = db.save_recipe(config)
            self._recipes.append(recipe)
            self.recipe_added.emit(recipe.recipe_id)
        else:
            db.save_recipe(config)
            self.recipe_updated.emit()

    def delete_recipe(self, recipe_id: int):
        """Remove a recipe by ID."""
        DatabaseManager.instance().local_db.delete_recipe(recipe_id)
        self._recipes = [
            r for r in self._recipes if r.recipe_id != recipe_id
        ]
        self.recipe_updated.emit()

    def clone_recipe(self, recipe_id: int) -> int:
        """Deep-copy a recipe and save it with a ``- Copy`` suffix.

        Returns:
            The new recipe ID, or -1 if the source was not found.
        """
        original = self.get_recipe(recipe_id)
        if not original:
            return -1
        cloned = copy.deepcopy(original)
        cloned.recipe_id = -1
        cloned.name = f"{original.name} - Copy"
        cloned.product_pn = ""  # PN must be unique, clear for user to fill
        self.save_recipe(cloned)
        return cloned.recipe_id

    # ------------------------------------------------------------------
    # Serialization helpers
    # ------------------------------------------------------------------

    def _row_to_recipe(self, row: dict) -> AgingRecipe:
        """Convert a database row dict into an :class:`AgingRecipe`."""
        phases = row.get("phases", [])
        if isinstance(phases, str):
            try:
                phases = json.loads(phases)
            except (json.JSONDecodeError, TypeError):
                phases = []

        event_actions = row.get("event_actions", {})
        if isinstance(event_actions, str):
            try:
                event_actions = json.loads(event_actions)
            except (json.JSONDecodeError, TypeError):
                event_actions = {}

        return AgingRecipe.from_dict({
            "recipe_id": row["recipe_id"],
            "name": row["name"],
            "product_pn": row["product_pn"],
            "max_total_minutes": row["max_total_minutes"],
            "phases": phases,
            "event_actions": event_actions,
            "default_thresholds": row.get("default_thresholds", {}),
            "collect_params": row.get("collect_params", {}),
        })
