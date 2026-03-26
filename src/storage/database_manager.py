"""Singleton facade for all database operations.

Provides a single entry point for local SQLite, remote MySQL/PostgreSQL,
and the periodic sync between them.
"""

import logging
from pathlib import Path

from .local_db import LocalDatabase
from .remote_db import RemoteDatabase
from .sync_manager import DataSyncManager

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Singleton that owns the local DB, remote DB, and sync manager."""

    _instance: "DatabaseManager | None" = None

    def __init__(self) -> None:
        self.local_db = LocalDatabase()
        self.remote_db = RemoteDatabase()
        self.sync_manager = DataSyncManager(
            local_db=self.local_db,
            remote_db=self.remote_db,
        )
        self._initialized = False

    # ------------------------------------------------------------------
    # Singleton
    # ------------------------------------------------------------------

    @classmethod
    def instance(cls) -> "DatabaseManager":
        """Return the global DatabaseManager singleton."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Drop the singleton (useful for testing)."""
        if cls._instance is not None:
            cls._instance.local_db.close()
            cls._instance.remote_db.disconnect()
            cls._instance.sync_manager.stop()
            cls._instance = None

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def initialize(self, db_path: str | None = None) -> None:
        """Open the local database and create the schema.

        Args:
            db_path: Path to the SQLite file. Defaults to
                     ``data/sigenpro_local.db`` relative to the working
                     directory.
        """
        if db_path is None:
            db_path = str(Path("data") / "sigenpro_local.db")
        self.local_db.initialize(db_path)
        self._initialized = True
        logger.info("Local database initialized at: %s", db_path)

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    # ------------------------------------------------------------------
    # Remote DB
    # ------------------------------------------------------------------

    def connect_remote(
        self,
        host: str,
        port: int,
        db_name: str,
        user: str,
        password: str,
        db_type: str = "mysql",
    ) -> bool:
        """Connect to the remote database and create tables if needed.

        Args:
            host, port, db_name, user, password: Connection parameters.
            db_type: ``"mysql"`` or ``"postgresql"``.

        Returns:
            True if the connection succeeded.
        """
        ok = self.remote_db.connect(host, port, db_name, user, password, db_type)
        if ok:
            try:
                self.remote_db.create_meta_tables()
                logger.info("Remote database meta tables verified/created")
            except Exception:
                logger.exception("Failed to create remote meta tables")
        return ok

    # ------------------------------------------------------------------
    # Sync
    # ------------------------------------------------------------------

    def start_sync(self, interval_minutes: int = 60) -> None:
        """Start periodic data synchronization to the remote database.

        Args:
            interval_minutes: How often to sync (default 60).
        """
        self.sync_manager.set_interval_minutes(interval_minutes)
        self.sync_manager.start()

    def stop_sync(self) -> None:
        """Stop the periodic sync timer."""
        self.sync_manager.stop()

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def cleanup(self) -> None:
        """Stop sync, close connections, reset singleton."""
        self.stop_sync()
        self.local_db.close()
        self.remote_db.disconnect()
        self._initialized = False
