"""Periodic synchronization of local SQLite data to the remote database.

Uses a QTimer to periodically push unsynced device data and alarms from
the local database to the remote (MySQL / PostgreSQL) server.
"""

import logging
from datetime import datetime, timedelta

from PyQt6.QtCore import QObject, QTimer

from .local_db import LocalDatabase
from .remote_db import RemoteDatabase

logger = logging.getLogger(__name__)


class DataSyncManager(QObject):
    """Periodically syncs local SQLite data to a remote database."""

    DEFAULT_INTERVAL_MINUTES = 60

    def __init__(
        self,
        local_db: LocalDatabase | None = None,
        remote_db: RemoteDatabase | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._local_db = local_db
        self._remote_db = remote_db
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._do_sync)
        self._interval_ms = self.DEFAULT_INTERVAL_MINUTES * 60 * 1000
        self._running = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_local_db(self, db: LocalDatabase) -> None:
        self._local_db = db

    def set_remote_db(self, db: RemoteDatabase) -> None:
        self._remote_db = db

    def set_interval_minutes(self, minutes: int) -> None:
        """Configure the sync interval. Takes effect on next start()."""
        self._interval_ms = minutes * 60 * 1000

    def start(self) -> None:
        """Start the periodic sync timer.

        Connects to the remote database if not already connected, then
        fires the first sync immediately before starting the timer.
        """
        if self._running:
            return
        if self._remote_db is None or not self._remote_db.is_connected:
            logger.warning("Remote database is not connected — sync cannot start")
            return
        self._running = True
        self._timer.setInterval(self._interval_ms)
        self._timer.start()
        logger.info("Data sync started (interval: %d min)", self._interval_ms // 60_000)

        # Perform an immediate sync on start
        QTimer.singleShot(0, self._do_sync)

    def stop(self) -> None:
        """Stop the periodic sync timer."""
        if not self._running:
            return
        self._timer.stop()
        self._running = False
        logger.info("Data sync stopped")

    @property
    def is_running(self) -> bool:
        return self._running

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _do_sync(self) -> None:
        """Execute one sync cycle: device data then alarms."""
        if self._local_db is None or self._remote_db is None:
            return

        try:
            self._sync_device_data()
            self._sync_alarms()
        except Exception:
            logger.exception("Error during data sync cycle")

    def _sync_device_data(self) -> None:
        """Query local DB for unsynced data per daily table and push to remote."""
        # Look at the last N days for daily tables that may have data
        today = datetime.now()
        synced_total = 0

        for days_back in range(2):  # check today and yesterday
            date_str = (today - timedelta(days=days_back)).strftime("%Y%m%d")
            rows = self._local_db.query_unsynced_device_data(date_str, limit=5000)
            if not rows:
                continue

            inserted = self._remote_db.insert_device_data_batch(rows)
            synced_total += inserted

            if inserted > 0 and rows:
                last_id = rows[-1]["id"]
                self._local_db.mark_device_data_synced(date_str, last_id)
                logger.info(
                    "Synced %d device data rows for %s (last_id=%d)",
                    inserted,
                    date_str,
                    last_id,
                )

        if synced_total:
            logger.info("Device data sync complete: %d rows total", synced_total)

    def _sync_alarms(self) -> None:
        """Push unsynced alarm records to the remote database."""
        records = self._local_db.query_unsynced_alarms(limit=1000)
        if not records:
            return

        inserted = self._remote_db.insert_alarm_records(records)
        if inserted > 0:
            alarm_ids = [r["id"] for r in records[:inserted]]
            self._local_db.mark_alarms_synced(alarm_ids)
            logger.info("Synced %d alarm records to remote DB", inserted)
