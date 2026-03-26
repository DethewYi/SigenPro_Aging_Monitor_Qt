"""Dynamic protocol plugin loader.

Scans a plugins/ directory for .py files, imports them, and registers any
classes that implement IProtocolParser or IInstrumentController.
"""

import importlib.util
import inspect
import os
import logging
from pathlib import Path

from .interfaces import IProtocolParser, IInstrumentController

logger = logging.getLogger(__name__)


class PluginManager:
    """Discovers and instantiates protocol plugins."""

    def __init__(self):
        self._parsers: dict[str, type] = {}
        self._controllers: dict[str, type] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_plugins(self, plugin_dir: str) -> None:
        """Scan *plugin_dir* for .py files and register compatible classes.

        Args:
            plugin_dir: Absolute or relative path to the plugins directory.
        """
        plugin_path = Path(plugin_dir)
        if not plugin_path.is_dir():
            logger.warning("Plugin directory does not exist: %s", plugin_dir)
            return

        for py_file in sorted(plugin_path.glob("*.py")):
            if py_file.name.startswith("_"):
                continue
            self._load_plugin_file(py_file)

        logger.info(
            "Plugins loaded — parsers: %s, controllers: %s",
            list(self._parsers.keys()),
            list(self._controllers.keys()),
        )

    def create_parser(self, name: str) -> IProtocolParser | None:
        """Instantiate a parser by its registered *name*.

        Returns:
            A new IProtocolParser instance, or ``None`` if not found.
        """
        cls = self._parsers.get(name)
        if cls is None:
            logger.error("Parser plugin not found: %s", name)
            return None
        return cls()

    def create_controller(self, name: str) -> IInstrumentController | None:
        """Instantiate a controller by its registered *name*.

        Returns:
            A new IInstrumentController instance, or ``None`` if not found.
        """
        cls = self._controllers.get(name)
        if cls is None:
            logger.error("Controller plugin not found: %s", name)
            return None
        return cls()

    def available_parsers(self) -> list[str]:
        """Return a sorted list of registered parser names."""
        return sorted(self._parsers.keys())

    def available_controllers(self) -> list[str]:
        """Return a sorted list of registered controller names."""
        return sorted(self._controllers.keys())

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _load_plugin_file(self, path: Path) -> None:
        """Import a single .py file and register any compatible classes."""
        module_name = f"_plugin_{path.stem}"
        try:
            spec = importlib.util.spec_from_file_location(module_name, path)
            if spec is None or spec.loader is None:
                logger.warning("Cannot create module spec for %s", path)
                return
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        except Exception:
            logger.exception("Failed to import plugin file: %s", path)
            return

        for _name, obj in inspect.getmembers(module, inspect.isclass):
            if obj.__module__ != module_name:
                # Skip imported classes, only register those defined in the file
                continue
            if issubclass(obj, IProtocolParser) and obj is not IProtocolParser:
                # Try to get name from protocol_name() — need a temporary instance
                try:
                    name = obj().protocol_name()
                except Exception:
                    name = obj.__name__
                self._parsers[name] = obj
                logger.debug("Registered parser plugin: %s", name)

            if issubclass(obj, IInstrumentController) and obj is not IInstrumentController:
                try:
                    name = obj().protocol_name()
                except Exception:
                    name = obj.__name__
                self._controllers[name] = obj
                logger.debug("Registered controller plugin: %s", name)
