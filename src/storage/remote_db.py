"""Remote database support for MySQL and PostgreSQL.

Provides a unified API for inserting device data and alarm records into a
remote relational database.  Data is partitioned by month
(device_data_YYYYMM).
"""

import json
import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class RemoteDatabase:
    """Manages connection to a remote MySQL or PostgreSQL database."""

    def __init__(self) -> None:
        self._conn = None
        self._db_type: str = ""  # "mysql" or "postgresql"
        self._connected: bool = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def connect(
        self,
        host: str,
        port: int,
        db_name: str,
        user: str,
        password: str,
        db_type: str = "mysql",
    ) -> bool:
        """Connect to the remote database.

        Args:
            host: Server hostname or IP.
            port: TCP port.
            db_name: Database name.
            user: Username.
            password: Password.
            db_type: ``"mysql"`` or ``"postgresql"``.
        """
        self._db_type = db_type
        try:
            if db_type == "mysql":
                import pymysql
                self._conn = pymysql.connect(
                    host=host,
                    port=port,
                    user=user,
                    password=password,
                    database=db_name,
                    charset="utf8mb4",
                    autocommit=True,
                )
            elif db_type == "postgresql":
                import psycopg2
                self._conn = psycopg2.connect(
                    host=host,
                    port=port,
                    user=user,
                    password=password,
                    dbname=db_name,
                )
                self._conn.autocommit = True
            else:
                logger.error("Unsupported remote database type: %s", db_type)
                return False

            self._connected = True
            logger.info("Connected to remote %s database at %s:%s", db_type, host, port)
            return True

        except Exception:
            logger.exception("Failed to connect to remote %s database", db_type)
            self._connected = False
            return False

    def disconnect(self) -> None:
        """Close the remote database connection."""
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None
            self._connected = False

    # ------------------------------------------------------------------
    # Schema helpers
    # ------------------------------------------------------------------

    def _is_mysql(self) -> bool:
        return self._db_type == "mysql"

    def _is_postgresql(self) -> bool:
        return self._db_type == "postgresql"

    def create_meta_tables(self) -> None:
        """Create metadata tables on the remote database."""
        if self._is_mysql():
            sql = """
            CREATE TABLE IF NOT EXISTS devices (
                device_id    INT PRIMARY KEY,
                name         VARCHAR(128) NOT NULL,
                model        VARCHAR(64) DEFAULT '',
                comm_type    TINYINT DEFAULT 0,
                ip_address   VARCHAR(45) DEFAULT '',
                port         INT DEFAULT 0,
                protocol_name VARCHAR(64) DEFAULT '',
                channel_id   INT DEFAULT -1
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

            CREATE TABLE IF NOT EXISTS channels (
                channel_id              INT PRIMARY KEY,
                status                  TINYINT DEFAULT 0,
                bound_sn                VARCHAR(64) DEFAULT '',
                bound_pn                VARCHAR(64) DEFAULT '',
                power_controller_id     INT DEFAULT -1,
                contactor_controller_id INT DEFAULT -1,
                power_channel           INT DEFAULT -1,
                contactor_channel       INT DEFAULT -1,
                power_protocol_name     VARCHAR(64) DEFAULT '',
                contactor_protocol_name VARCHAR(64) DEFAULT ''
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

            CREATE TABLE IF NOT EXISTS test_templates (
                template_id       INT PRIMARY KEY,
                name              VARCHAR(128) NOT NULL,
                product_model     VARCHAR(64) DEFAULT '',
                collect_params    JSON DEFAULT NULL,
                total_duration_minutes INT DEFAULT 0,
                default_thresholds JSON DEFAULT NULL,
                phases            JSON DEFAULT NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

            CREATE TABLE IF NOT EXISTS alarms (
                id              BIGINT AUTO_INCREMENT PRIMARY KEY,
                timestamp       DATETIME,
                device_id       INT DEFAULT -1,
                device_name     VARCHAR(128) DEFAULT '',
                param_name      VARCHAR(64) DEFAULT '',
                current_value   DOUBLE DEFAULT 0,
                threshold       DOUBLE DEFAULT 0,
                is_upper_limit  TINYINT DEFAULT 1,
                acknowledged    TINYINT DEFAULT 0,
                message         TEXT DEFAULT ''
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

            CREATE TABLE IF NOT EXISTS test_records (
                record_id   BIGINT AUTO_INCREMENT PRIMARY KEY,
                template_id INT,
                channel_id  INT,
                device_sn   VARCHAR(64) DEFAULT '',
                device_pn   VARCHAR(64) DEFAULT '',
                start_time  DATETIME,
                end_time    DATETIME,
                result      TINYINT DEFAULT 0,
                remark      TEXT DEFAULT ''
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        else:
            # PostgreSQL
            sql = """
            CREATE TABLE IF NOT EXISTS devices (
                device_id    INT PRIMARY KEY,
                name         VARCHAR(128) NOT NULL,
                model        VARCHAR(64) DEFAULT '',
                comm_type    SMALLINT DEFAULT 0,
                ip_address   VARCHAR(45) DEFAULT '',
                port         INT DEFAULT 0,
                protocol_name VARCHAR(64) DEFAULT '',
                channel_id   INT DEFAULT -1
            );

            CREATE TABLE IF NOT EXISTS channels (
                channel_id              INT PRIMARY KEY,
                status                  SMALLINT DEFAULT 0,
                bound_sn                VARCHAR(64) DEFAULT '',
                bound_pn                VARCHAR(64) DEFAULT '',
                power_controller_id     INT DEFAULT -1,
                contactor_controller_id INT DEFAULT -1,
                power_channel           INT DEFAULT -1,
                contactor_channel       INT DEFAULT -1,
                power_protocol_name     VARCHAR(64) DEFAULT '',
                contactor_protocol_name VARCHAR(64) DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS test_templates (
                template_id       SERIAL PRIMARY KEY,
                name              VARCHAR(128) NOT NULL,
                product_model     VARCHAR(64) DEFAULT '',
                collect_params    JSONB DEFAULT '{}',
                total_duration_minutes INT DEFAULT 0,
                default_thresholds JSONB DEFAULT '{}',
                phases            JSONB DEFAULT '[]'
            );

            CREATE TABLE IF NOT EXISTS alarms (
                id              BIGSERIAL PRIMARY KEY,
                timestamp       TIMESTAMP,
                device_id       INT DEFAULT -1,
                device_name     VARCHAR(128) DEFAULT '',
                param_name      VARCHAR(64) DEFAULT '',
                current_value   DOUBLE PRECISION DEFAULT 0,
                threshold       DOUBLE PRECISION DEFAULT 0,
                is_upper_limit  SMALLINT DEFAULT 1,
                acknowledged    SMALLINT DEFAULT 0,
                message         TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS test_records (
                record_id   BIGSERIAL PRIMARY KEY,
                template_id INT,
                channel_id  INT,
                device_sn   VARCHAR(64) DEFAULT '',
                device_pn   VARCHAR(64) DEFAULT '',
                start_time  TIMESTAMP,
                end_time    TIMESTAMP,
                result      SMALLINT DEFAULT 0,
                remark      TEXT DEFAULT ''
            );
            """

        cur = self._conn.cursor()
        try:
            for statement in sql.strip().split(";"):
                statement = statement.strip()
                if statement:
                    cur.execute(statement)
        finally:
            cur.close()

    def create_monthly_table(self, month_str: str) -> None:
        """Create a monthly-partitioned data table (device_data_YYYYMM).

        Args:
            month_str: Month in YYYYMM format.
        """
        table_name = f"device_data_{month_str}"
        if self._is_mysql():
            sql = f"""
            CREATE TABLE IF NOT EXISTS [{table_name}] (
                id          BIGINT AUTO_INCREMENT PRIMARY KEY,
                device_id   INT NOT NULL,
                timestamp   DATETIME NOT NULL,
                parameters  JSON DEFAULT NULL,
                comm_ok     TINYINT DEFAULT 1,
                frame_errors INT DEFAULT 0,
                INDEX idx_{table_name}_dev_ts (device_id, timestamp)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """
        else:
            sql = f"""
            CREATE TABLE IF NOT EXISTS [{table_name}] (
                id          BIGSERIAL PRIMARY KEY,
                device_id   INT NOT NULL,
                timestamp   TIMESTAMP NOT NULL,
                parameters  JSONB DEFAULT '{{}}',
                comm_ok     SMALLINT DEFAULT 1,
                frame_errors INT DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_{table_name}_dev_ts ON [{table_name}] (device_id, timestamp);
            """

        cur = self._conn.cursor()
        try:
            cur.execute(sql)
        finally:
            cur.close()

    # ------------------------------------------------------------------
    # Data insertion
    # ------------------------------------------------------------------

    def insert_device_data_batch(self, data_list: list[dict]) -> int:
        """Batch-insert device data rows into the appropriate monthly table.

        Args:
            data_list: List of dicts with device_id, timestamp, parameters,
                       comm_ok, frame_errors.

        Returns:
            Number of rows inserted.
        """
        if not data_list:
            return 0

        # Group by month
        grouped: dict[str, list[dict]] = {}
        for item in data_list:
            try:
                dt = datetime.fromisoformat(item["timestamp"])
            except (ValueError, TypeError):
                dt = datetime.now()
            month_str = dt.strftime("%Y%m")
            grouped.setdefault(month_str, []).append(item)

        total = 0
        cur = self._conn.cursor()
        try:
            for month_str, items in grouped.items():
                self.create_monthly_table(month_str)
                table_name = f"device_data_{month_str}"
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
                cur.executemany(
                    f"INSERT INTO [{table_name}] (device_id, timestamp, parameters, comm_ok, frame_errors) "
                    f"VALUES (%s, %s, %s, %s, %s)",
                    rows,
                )
                total += len(rows)
        except Exception:
            logger.exception("Failed to batch-insert device data to remote DB")
        finally:
            cur.close()

        return total

    def insert_alarm_records(self, records: list[dict]) -> int:
        """Batch-insert alarm records into the remote alarms table.

        Args:
            records: List of alarm dicts.

        Returns:
            Number of rows inserted.
        """
        if not records:
            return 0

        rows = [
            (
                r.get("timestamp"),
                r.get("device_id", -1),
                r.get("device_name", ""),
                r.get("param_name", ""),
                r.get("current_value", 0),
                r.get("threshold", 0),
                1 if r.get("is_upper_limit", True) else 0,
                1 if r.get("acknowledged", False) else 0,
                r.get("message", ""),
            )
            for r in records
        ]

        cur = self._conn.cursor()
        try:
            cur.executemany(
                "INSERT INTO alarms (timestamp, device_id, device_name, param_name, "
                "current_value, threshold, is_upper_limit, acknowledged, message) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                rows,
            )
            return len(rows)
        except Exception:
            logger.exception("Failed to batch-insert alarms to remote DB")
            return 0
        finally:
            cur.close()
