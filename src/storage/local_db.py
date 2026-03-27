"""Local SQLite database for device data, channels, templates, and alarms.

Uses daily-partitioned tables (device_data_YYYYMMDD) for high-volume
measurement data and regular tables for metadata.
"""

import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class LocalDatabase:
    """Wraps an SQLite database with WAL mode and daily data partitioning."""

    def __init__(self) -> None:
        self._conn: sqlite3.Connection | None = None
        self._db_path: str = ""

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @property
    def db_path(self) -> str:
        return self._db_path

    def initialize(self, db_path: str) -> None:
        """Open (or create) the database and ensure schema exists.

        Args:
            db_path: Path to the SQLite database file.
        """
        self._db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self.create_meta_tables()

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def create_meta_tables(self) -> None:
        """Create all metadata tables if they do not already exist."""
        cur = self._conn.cursor()
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS devices (
                device_id    INTEGER PRIMARY KEY,
                name         TEXT NOT NULL,
                model        TEXT DEFAULT '',
                comm_type    INTEGER DEFAULT 0,
                ip_address   TEXT DEFAULT '',
                port         INTEGER DEFAULT 0,
                protocol_name TEXT DEFAULT '',
                channel_id   INTEGER DEFAULT -1
            );

            CREATE TABLE IF NOT EXISTS channels (
                channel_id             INTEGER PRIMARY KEY,
                status                 INTEGER DEFAULT 0,
                bound_sn               TEXT DEFAULT '',
                bound_pn               TEXT DEFAULT '',
                power_controller_id    INTEGER DEFAULT -1,
                contactor_controller_id INTEGER DEFAULT -1,
                power_channel          INTEGER DEFAULT -1,
                contactor_channel      INTEGER DEFAULT -1,
                power_protocol_name    TEXT DEFAULT '',
                contactor_protocol_name TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS test_templates (
                template_id       INTEGER PRIMARY KEY,
                name              TEXT NOT NULL,
                product_model     TEXT DEFAULT '',
                collect_params    TEXT DEFAULT '{}',
                total_duration_minutes INTEGER DEFAULT 0,
                default_thresholds TEXT DEFAULT '{}',
                phases            TEXT DEFAULT '[]'
            );

            CREATE TABLE IF NOT EXISTS aging_recipes (
                recipe_id          INTEGER PRIMARY KEY,
                name               TEXT NOT NULL,
                product_pn         TEXT NOT NULL UNIQUE,
                max_total_minutes  INTEGER DEFAULT 0,
                collect_params     TEXT DEFAULT '{}',
                default_thresholds TEXT DEFAULT '{}',
                phases             TEXT DEFAULT '[]',
                event_actions      TEXT DEFAULT '{}',
                created_at         TEXT DEFAULT '',
                updated_at         TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS test_records (
                record_id     INTEGER PRIMARY KEY AUTOINCREMENT,
                template_id   INTEGER,
                channel_id    INTEGER,
                device_sn     TEXT DEFAULT '',
                device_pn     TEXT DEFAULT '',
                start_time    TEXT,
                end_time      TEXT,
                result        INTEGER DEFAULT 0,
                remark        TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS alarms (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp       TEXT,
                device_id       INTEGER DEFAULT -1,
                device_name     TEXT DEFAULT '',
                param_name      TEXT DEFAULT '',
                current_value   REAL DEFAULT 0,
                threshold       REAL DEFAULT 0,
                is_upper_limit  INTEGER DEFAULT 1,
                acknowledged    INTEGER DEFAULT 0,
                message         TEXT DEFAULT '',
                synced          INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS db_info (
                key   TEXT PRIMARY KEY,
                value TEXT DEFAULT ''
            );
        """)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Daily partitioned data tables
    # ------------------------------------------------------------------

    def ensure_daily_table(self, date_str: str) -> None:
        """Create a device data table for *date_str* (YYYYMMDD) if missing.

        Also creates an index on (device_id, timestamp) for fast queries.
        """
        table_name = f"device_data_{date_str}"
        self._conn.execute(f"""
            CREATE TABLE IF NOT EXISTS [{table_name}] (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id   INTEGER NOT NULL,
                timestamp   TEXT NOT NULL,
                parameters  TEXT DEFAULT '{{}}',
                comm_ok     INTEGER DEFAULT 1,
                frame_errors INTEGER DEFAULT 0
            )
        """)
        self._conn.execute(
            f"CREATE INDEX IF NOT EXISTS [idx_{table_name}_dev_ts] "
            f"ON [{table_name}] (device_id, timestamp)"
        )
        self._conn.commit()

    def insert_device_data(self, data_list: list[dict]) -> int:
        """Batch-insert device data rows with a single transaction.

        Args:
            data_list: List of dicts, each containing:
                - device_id (int)
                - timestamp (str, ISO format)
                - parameters (dict, will be JSON-serialized)
                - comm_ok (bool)
                - frame_errors (int)

        Returns:
            Number of rows inserted.
        """
        if not data_list:
            return 0

        # Group by date so we can insert into the correct daily table
        grouped: dict[str, list[dict]] = {}
        for item in data_list:
            try:
                dt = datetime.fromisoformat(item["timestamp"])
            except (ValueError, TypeError):
                dt = datetime.now()
            date_str = dt.strftime("%Y%m%d")
            grouped.setdefault(date_str, []).append(item)

        total = 0
        for date_str, items in grouped.items():
            self.ensure_daily_table(date_str)
            table_name = f"device_data_{date_str}"
            rows = [
                (
                    d["device_id"],
                    d.get("timestamp", datetime.now().isoformat()),
                    json.dumps(d.get("parameters", {}), ensure_ascii=False),
                    1 if d.get("comm_ok", True) else 0,
                    d.get("frame_errors", 0),
                )
                for d in items
            ]
            self._conn.executemany(
                f"INSERT INTO [{table_name}] (device_id, timestamp, parameters, comm_ok, frame_errors) "
                f"VALUES (?, ?, ?, ?, ?)",
                rows,
            )
            total += len(rows)

        self._conn.commit()
        return total

    def query_device_data(
        self,
        device_id: int,
        start: datetime,
        end: datetime,
    ) -> list[dict]:
        """Query device data across daily tables in the given time range.

        Args:
            device_id: Device to query.
            start: Start of time range (inclusive).
            end: End of time range (inclusive).

        Returns:
            List of dicts with keys: id, device_id, timestamp, parameters,
            comm_ok, frame_errors.
        """
        # Determine which daily tables could contain data in [start, end]
        current = start
        results: list[dict] = []
        start_iso = start.isoformat()
        end_iso = end.isoformat()

        while current <= end:
            date_str = current.strftime("%Y%m%d")
            table_name = f"device_data_{date_str}"
            # Check if table exists
            count = self._conn.execute(
                "SELECT count(*) FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,),
            ).fetchone()[0]
            if count > 0:
                rows = self._conn.execute(
                    f"SELECT id, device_id, timestamp, parameters, comm_ok, frame_errors "
                    f"FROM [{table_name}] "
                    f"WHERE device_id=? AND timestamp>=? AND timestamp<=? "
                    f"ORDER BY timestamp",
                    (device_id, start_iso, end_iso),
                ).fetchall()
                for row in rows:
                    params = {}
                    try:
                        params = json.loads(row[3])
                    except (json.JSONDecodeError, TypeError):
                        pass
                    results.append({
                        "id": row[0],
                        "device_id": row[1],
                        "timestamp": row[2],
                        "parameters": params,
                        "comm_ok": bool(row[4]),
                        "frame_errors": row[5],
                    })
            current += timedelta(days=1)

        return results

    # ------------------------------------------------------------------
    # Alarms
    # ------------------------------------------------------------------

    def insert_alarm_record(self, record: dict) -> int:
        """Insert a single alarm record and return its row id."""
        cur = self._conn.execute(
            "INSERT INTO alarms (timestamp, device_id, device_name, param_name, "
            "current_value, threshold, is_upper_limit, acknowledged, message, synced) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                record.get("timestamp", datetime.now().isoformat()),
                record.get("device_id", -1),
                record.get("device_name", ""),
                record.get("param_name", ""),
                record.get("current_value", 0),
                record.get("threshold", 0),
                1 if record.get("is_upper_limit", True) else 0,
                0,
                record.get("message", ""),
                0,
            ),
        )
        self._conn.commit()
        return cur.lastrowid

    def query_alarms(self, start: datetime | None = None, limit: int = 100) -> list[dict]:
        """Query alarm records, most recent first.

        Args:
            start: Optional start time filter.
            limit: Maximum rows to return.
        """
        if start:
            rows = self._conn.execute(
                "SELECT id, timestamp, device_id, device_name, param_name, "
                "current_value, threshold, is_upper_limit, acknowledged, message "
                "FROM alarms WHERE timestamp>=? ORDER BY id DESC LIMIT ?",
                (start.isoformat(), limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT id, timestamp, device_id, device_name, param_name, "
                "current_value, threshold, is_upper_limit, acknowledged, message "
                "FROM alarms ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()

        return [
            {
                "id": r[0],
                "timestamp": r[1],
                "device_id": r[2],
                "device_name": r[3],
                "param_name": r[4],
                "current_value": r[5],
                "threshold": r[6],
                "is_upper_limit": bool(r[7]),
                "acknowledged": bool(r[8]),
                "message": r[9],
            }
            for r in rows
        ]

    def acknowledge_alarm(self, alarm_id: int) -> bool:
        """Mark an alarm as acknowledged."""
        self._conn.execute(
            "UPDATE alarms SET acknowledged=1 WHERE id=?", (alarm_id,)
        )
        self._conn.commit()
        return True

    def query_unsynced_alarms(self, limit: int = 1000) -> list[dict]:
        """Return alarms that have not been synced to the remote database."""
        rows = self._conn.execute(
            "SELECT id, timestamp, device_id, device_name, param_name, "
            "current_value, threshold, is_upper_limit, acknowledged, message "
            "FROM alarms WHERE synced=0 ORDER BY id LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            {
                "id": r[0],
                "timestamp": r[1],
                "device_id": r[2],
                "device_name": r[3],
                "param_name": r[4],
                "current_value": r[5],
                "threshold": r[6],
                "is_upper_limit": bool(r[7]),
                "acknowledged": bool(r[8]),
                "message": r[9],
            }
            for r in rows
        ]

    def mark_alarms_synced(self, alarm_ids: list[int]) -> None:
        """Mark the given alarm IDs as synced."""
        if not alarm_ids:
            return
        placeholders = ",".join("?" * len(alarm_ids))
        self._conn.execute(
            f"UPDATE alarms SET synced=1 WHERE id IN ({placeholders})",
            alarm_ids,
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Test records
    # ------------------------------------------------------------------

    def save_test_record(
        self,
        template_id: int,
        channel_id: int,
        device_sn: str,
        device_pn: str,
        start_time: str,
        end_time: str | None,
        result: int,
        remark: str = "",
    ) -> int:
        """Save a test record and return its row id."""
        cur = self._conn.execute(
            "INSERT INTO test_records (template_id, channel_id, device_sn, device_pn, "
            "start_time, end_time, result, remark) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (template_id, channel_id, device_sn, device_pn, start_time, end_time, result, remark),
        )
        self._conn.commit()
        return cur.lastrowid

    # ------------------------------------------------------------------
    # Channels
    # ------------------------------------------------------------------

    def save_channel_info(self, info: dict) -> None:
        """Insert or update a channel configuration."""
        self._conn.execute(
            "INSERT INTO channels (channel_id, status, bound_sn, bound_pn, "
            "power_controller_id, contactor_controller_id, power_channel, "
            "contactor_channel, power_protocol_name, contactor_protocol_name) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(channel_id) DO UPDATE SET "
            "status=excluded.status, bound_sn=excluded.bound_sn, "
            "bound_pn=excluded.bound_pn, "
            "power_controller_id=excluded.power_controller_id, "
            "contactor_controller_id=excluded.contactor_controller_id, "
            "power_channel=excluded.power_channel, "
            "contactor_channel=excluded.contactor_channel, "
            "power_protocol_name=excluded.power_protocol_name, "
            "contactor_protocol_name=excluded.contactor_protocol_name",
            (
                info.get("channel_id", -1),
                info.get("status", 0),
                info.get("bound_sn", ""),
                info.get("bound_pn", ""),
                info.get("power_controller_id", -1),
                info.get("contactor_controller_id", -1),
                info.get("power_channel", -1),
                info.get("contactor_channel", -1),
                info.get("power_protocol_name", ""),
                info.get("contactor_protocol_name", ""),
            ),
        )
        self._conn.commit()

    def load_all_channels(self) -> list[dict]:
        """Load all channel configurations."""
        rows = self._conn.execute(
            "SELECT channel_id, status, bound_sn, bound_pn, "
            "power_controller_id, contactor_controller_id, power_channel, "
            "contactor_channel, power_protocol_name, contactor_protocol_name "
            "FROM channels ORDER BY channel_id"
        ).fetchall()
        return [
            {
                "channel_id": r[0],
                "status": r[1],
                "bound_sn": r[2],
                "bound_pn": r[3],
                "power_controller_id": r[4],
                "contactor_controller_id": r[5],
                "power_channel": r[6],
                "contactor_channel": r[7],
                "power_protocol_name": r[8],
                "contactor_protocol_name": r[9],
            }
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Test templates
    # ------------------------------------------------------------------

    def save_template(self, tmpl: dict) -> int:
        """Save (insert or update) a test template.

        The *phases* and *default_thresholds* fields are serialized to JSON.
        """
        phases = tmpl.get("phases", [])
        phases_json = json.dumps(phases, ensure_ascii=False, default=str)
        thresholds_json = json.dumps(
            tmpl.get("default_thresholds", {}), ensure_ascii=False, default=str
        )
        collect_json = json.dumps(tmpl.get("collect_params", {}), ensure_ascii=False)

        if tmpl.get("template_id", -1) > 0:
            tid = tmpl["template_id"]
            self._conn.execute(
                "UPDATE test_templates SET name=?, product_model=?, collect_params=?, "
                "total_duration_minutes=?, default_thresholds=?, phases=? WHERE template_id=?",
                (
                    tmpl.get("name", ""),
                    tmpl.get("product_model", ""),
                    collect_json,
                    tmpl.get("total_duration_minutes", 0),
                    thresholds_json,
                    phases_json,
                    tid,
                ),
            )
            self._conn.commit()
            return tid
        else:
            cur = self._conn.execute(
                "INSERT INTO test_templates (name, product_model, collect_params, "
                "total_duration_minutes, default_thresholds, phases) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    tmpl.get("name", ""),
                    tmpl.get("product_model", ""),
                    collect_json,
                    tmpl.get("total_duration_minutes", 0),
                    thresholds_json,
                    phases_json,
                ),
            )
            self._conn.commit()
            return cur.lastrowid

    def load_all_templates(self) -> list[dict]:
        """Load all test templates, deserializing JSON fields."""
        rows = self._conn.execute(
            "SELECT template_id, name, product_model, collect_params, "
            "total_duration_minutes, default_thresholds, phases "
            "FROM test_templates ORDER BY template_id"
        ).fetchall()
        results: list[dict] = []
        for r in rows:
            phases = []
            thresholds = {}
            collect = {}
            try:
                collect = json.loads(r[3]) if r[3] else {}
            except (json.JSONDecodeError, TypeError):
                pass
            try:
                thresholds = json.loads(r[5]) if r[5] else {}
            except (json.JSONDecodeError, TypeError):
                pass
            try:
                phases = json.loads(r[6]) if r[6] else []
            except (json.JSONDecodeError, TypeError):
                pass
            results.append({
                "template_id": r[0],
                "name": r[1],
                "product_model": r[2],
                "collect_params": collect,
                "total_duration_minutes": r[4],
                "default_thresholds": thresholds,
                "phases": phases,
            })
        return results

    def load_template(self, template_id: int) -> dict | None:
        """Load a single test template by ID."""
        row = self._conn.execute(
            "SELECT template_id, name, product_model, collect_params, "
            "total_duration_minutes, default_thresholds, phases "
            "FROM test_templates WHERE template_id=?",
            (template_id,),
        ).fetchone()
        if row is None:
            return None
        phases = []
        thresholds = {}
        collect = {}
        try:
            collect = json.loads(row[3]) if row[3] else {}
        except (json.JSONDecodeError, TypeError):
            pass
        try:
            thresholds = json.loads(row[5]) if row[5] else {}
        except (json.JSONDecodeError, TypeError):
            pass
        try:
            phases = json.loads(row[6]) if row[6] else []
        except (json.JSONDecodeError, TypeError):
            pass
        return {
            "template_id": row[0],
            "name": row[1],
            "product_model": row[2],
            "collect_params": collect,
            "total_duration_minutes": row[4],
            "default_thresholds": thresholds,
            "phases": phases,
        }

    def delete_template(self, template_id: int) -> bool:
        """Delete a test template by ID."""
        self._conn.execute(
            "DELETE FROM test_templates WHERE template_id=?", (template_id,)
        )
        self._conn.commit()
        return True

    # ------------------------------------------------------------------
    # Aging recipes
    # ------------------------------------------------------------------

    def save_recipe(self, recipe: dict) -> int:
        """Save (insert or update) an aging recipe."""
        phases_json = json.dumps(recipe.get("phases", []), ensure_ascii=False, default=str)
        event_json = json.dumps(recipe.get("event_actions", {}), ensure_ascii=False, default=str)
        thresholds_json = json.dumps(
            recipe.get("default_thresholds", {}), ensure_ascii=False, default=str
        )
        collect_json = json.dumps(recipe.get("collect_params", {}), ensure_ascii=False)
        now = datetime.now().isoformat()

        if recipe.get("recipe_id", -1) > 0:
            rid = recipe["recipe_id"]
            self._conn.execute(
                "UPDATE aging_recipes SET name=?, product_pn=?, max_total_minutes=?, "
                "collect_params=?, default_thresholds=?, phases=?, event_actions=?, "
                "updated_at=? WHERE recipe_id=?",
                (
                    recipe.get("name", ""),
                    recipe.get("product_pn", ""),
                    recipe.get("max_total_minutes", 0),
                    collect_json,
                    thresholds_json,
                    phases_json,
                    event_json,
                    now,
                    rid,
                ),
            )
            self._conn.commit()
            return rid
        else:
            cur = self._conn.execute(
                "INSERT INTO aging_recipes (name, product_pn, max_total_minutes, "
                "collect_params, default_thresholds, phases, event_actions, "
                "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    recipe.get("name", ""),
                    recipe.get("product_pn", ""),
                    recipe.get("max_total_minutes", 0),
                    collect_json,
                    thresholds_json,
                    phases_json,
                    event_json,
                    now,
                    now,
                ),
            )
            self._conn.commit()
            return cur.lastrowid

    def load_all_recipes(self) -> list[dict]:
        """Load all aging recipes, deserializing JSON fields."""
        rows = self._conn.execute(
            "SELECT recipe_id, name, product_pn, max_total_minutes, collect_params, "
            "default_thresholds, phases, event_actions, created_at, updated_at "
            "FROM aging_recipes ORDER BY recipe_id"
        ).fetchall()
        results: list[dict] = []
        for r in rows:
            phases = self._parse_json(r[6], [])
            event_actions = self._parse_json(r[7], {})
            thresholds = self._parse_json(r[5], {})
            collect = self._parse_json(r[4], {})
            results.append({
                "recipe_id": r[0],
                "name": r[1],
                "product_pn": r[2],
                "max_total_minutes": r[3],
                "collect_params": collect,
                "default_thresholds": thresholds,
                "phases": phases,
                "event_actions": event_actions,
                "created_at": r[8] or "",
                "updated_at": r[9] or "",
            })
        return results

    def load_recipe_by_id(self, recipe_id: int) -> dict | None:
        """Load a single aging recipe by ID."""
        row = self._conn.execute(
            "SELECT recipe_id, name, product_pn, max_total_minutes, collect_params, "
            "default_thresholds, phases, event_actions, created_at, updated_at "
            "FROM aging_recipes WHERE recipe_id=?",
            (recipe_id,),
        ).fetchone()
        if row is None:
            return None
        return {
            "recipe_id": row[0],
            "name": row[1],
            "product_pn": row[2],
            "max_total_minutes": row[3],
            "collect_params": self._parse_json(row[4], {}),
            "default_thresholds": self._parse_json(row[5], {}),
            "phases": self._parse_json(row[6], []),
            "event_actions": self._parse_json(row[7], {}),
            "created_at": row[8] or "",
            "updated_at": row[9] or "",
        }

    def load_recipe_by_pn(self, product_pn: str) -> dict | None:
        """Load a single aging recipe by product PN."""
        row = self._conn.execute(
            "SELECT recipe_id, name, product_pn, max_total_minutes, collect_params, "
            "default_thresholds, phases, event_actions, created_at, updated_at "
            "FROM aging_recipes WHERE product_pn=?",
            (product_pn,),
        ).fetchone()
        if row is None:
            return None
        return {
            "recipe_id": row[0],
            "name": row[1],
            "product_pn": row[2],
            "max_total_minutes": row[3],
            "collect_params": self._parse_json(row[4], {}),
            "default_thresholds": self._parse_json(row[5], {}),
            "phases": self._parse_json(row[6], []),
            "event_actions": self._parse_json(row[7], {}),
            "created_at": row[8] or "",
            "updated_at": row[9] or "",
        }

    def delete_recipe(self, recipe_id: int) -> bool:
        """Delete an aging recipe by ID."""
        self._conn.execute(
            "DELETE FROM aging_recipes WHERE recipe_id=?", (recipe_id,)
        )
        self._conn.commit()
        return True

    def _parse_json(self, text: str | None, default):
        """Safely parse JSON text, returning *default* on failure."""
        if not text:
            return default
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return default

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def clean_old_data(self, retain_days: int = 90) -> int:
        """Drop daily data tables older than *retain_days*.

        Returns:
            Number of tables dropped.
        """
        cutoff = (datetime.now() - timedelta(days=retain_days)).strftime("%Y%m%d")
        rows = self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'device_data_%'"
        ).fetchall()

        dropped = 0
        for (table_name,) in rows:
            date_suffix = table_name.replace("device_data_", "")
            if date_suffix < cutoff:
                self._conn.execute(f"DROP TABLE IF EXISTS [{table_name}]")
                self._conn.execute(f"DROP INDEX IF EXISTS [idx_{table_name}_dev_ts]")
                dropped += 1
                logger.info("Dropped old data table: %s", table_name)

        if dropped:
            self._conn.commit()
        return dropped

    # ------------------------------------------------------------------
    # Sync bookkeeping
    # ------------------------------------------------------------------

    def query_unsynced_device_data(
        self, date_str: str, limit: int = 5000
    ) -> list[dict]:
        """Return rows from a daily table that have not been synced yet.

        Uses the db_info table to track the last synced row id per table.
        """
        last_id = self._get_sync_point(f"device_data_{date_str}")
        table_name = f"device_data_{date_str}"

        count = self._conn.execute(
            "SELECT count(*) FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        ).fetchone()[0]
        if count == 0:
            return []

        rows = self._conn.execute(
            f"SELECT id, device_id, timestamp, parameters, comm_ok, frame_errors "
            f"FROM [{table_name}] WHERE id>? ORDER BY id LIMIT ?",
            (last_id, limit),
        ).fetchall()

        results = []
        for row in rows:
            params = {}
            try:
                params = json.loads(row[3])
            except (json.JSONDecodeError, TypeError):
                pass
            results.append({
                "id": row[0],
                "device_id": row[1],
                "timestamp": row[2],
                "parameters": params,
                "comm_ok": bool(row[4]),
                "frame_errors": row[5],
            })
        return results

    def mark_device_data_synced(self, date_str: str, last_synced_id: int) -> None:
        """Record the last row id that has been synced for a daily table."""
        key = f"device_data_{date_str}"
        self._conn.execute(
            "INSERT INTO db_info (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, str(last_synced_id)),
        )
        self._conn.commit()

    def _get_sync_point(self, table_name: str) -> int:
        """Return the last synced row id for a given table."""
        row = self._conn.execute(
            "SELECT value FROM db_info WHERE key=?", (table_name,)
        ).fetchone()
        if row and row[0]:
            try:
                return int(row[0])
            except ValueError:
                return 0
        return 0
