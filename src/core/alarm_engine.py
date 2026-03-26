"""Alarm threshold evaluation engine.

Listens to :class:`DataBus` for incoming :class:`DeviceData` payloads,
checks each parameter against configured alarm thresholds (including
phase-based thresholds), and emits/records alarms when violations
are detected.
"""

from PyQt6.QtCore import QObject, pyqtSlot
import logging

from .data_bus import DataBus
from .common.alarm_record import AlarmRecord
from .common.device_data import DeviceData
from .common.test_template import TestPhase

logger = logging.getLogger(__name__)


class AlarmEngine(QObject):
    """Evaluates device parameters against alarm thresholds.

    Thresholds can be:

    * **Default thresholds** -- applied throughout the entire test.
    * **Phase thresholds** -- applied only during specific time windows,
      overriding default thresholds for the same parameter.

    The engine tracks *active alarms* per device to avoid emitting
    duplicate alarm records while a parameter remains in violation.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        # device_id -> context dict
        self._device_contexts: dict[int, dict] = {}
        # device_id -> set of param names currently in alarm
        self._active_alarms: dict[int, set[str]] = {}
        DataBus.instance().device_data_received.connect(self._on_device_data)

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def set_active_thresholds(self, device_id: int, thresholds: dict):
        """Set default thresholds for *device_id*.

        Args:
            thresholds: Mapping of ``param_name -> AlarmThreshold``.
        """
        ctx = self._device_contexts.setdefault(
            device_id,
            {"default_thresholds": {}, "phases": [], "phase_start": None},
        )
        ctx["default_thresholds"] = thresholds

    def set_phase_thresholds(self, device_id: int, phases: list):
        """Set phase-specific thresholds for *device_id*.

        Args:
            phases: List of :class:`TestPhase` objects.
        """
        ctx = self._device_contexts.setdefault(
            device_id,
            {"default_thresholds": {}, "phases": [], "phase_start": None},
        )
        ctx["phases"] = phases

    def set_phase_start_time(self, device_id: int, start_time):
        """Set the test start time for *device_id*.

        This also resets the active-alarm tracking so that alarms
        from a previous test run are cleared.
        """
        ctx = self._device_contexts.setdefault(
            device_id,
            {"default_thresholds": {}, "phases": [], "phase_start": None},
        )
        ctx["phase_start"] = start_time
        self._active_alarms.pop(device_id, None)

    def clear_thresholds(self, device_id: int):
        """Remove all threshold configuration for *device_id*."""
        self._device_contexts.pop(device_id, None)
        self._active_alarms.pop(device_id, None)

    # ------------------------------------------------------------------
    # Alarm acknowledgement
    # ------------------------------------------------------------------

    def acknowledge_alarm(self, alarm_id: int):
        """Mark an alarm record as acknowledged in the database."""
        from ..storage.database_manager import DatabaseManager
        DatabaseManager.instance().local_db.acknowledge_alarm(alarm_id)

    # ------------------------------------------------------------------
    # Threshold evaluation
    # ------------------------------------------------------------------

    @pyqtSlot(object)
    def _on_device_data(self, data: DeviceData):
        """Slot called when new device data arrives on the DataBus."""
        self._check_thresholds(data)

    def _get_current_thresholds(self, device_id: int) -> dict:
        """Return the effective thresholds for *device_id* at this moment.

        If phase-based thresholds are configured and the test is within
        a phase window, those thresholds are returned; otherwise the
        default thresholds are used.
        """
        ctx = self._device_contexts.get(device_id)
        if not ctx:
            return {}
        phases: list[TestPhase] = ctx.get("phases", [])
        phase_start = ctx.get("phase_start")
        if phases and phase_start:
            from datetime import datetime
            elapsed = (datetime.now() - phase_start).total_seconds()
            accumulated = 0.0
            for phase in phases:
                phase_seconds = phase.duration_minutes * 60
                if elapsed < accumulated + phase_seconds:
                    return phase.thresholds
                accumulated += phase_seconds
        return ctx.get("default_thresholds", {})

    def _check_thresholds(self, data: DeviceData):
        """Evaluate all parameters in *data* against active thresholds."""
        from ..storage.database_manager import DatabaseManager

        device_id = data.device_id
        thresholds = self._get_current_thresholds(device_id)
        active = self._active_alarms.setdefault(device_id, set())

        for param_name, value in data.parameters.items():
            threshold = thresholds.get(param_name)
            if not threshold or not threshold.enabled:
                # No threshold (or disabled) -- clear alarm if was active
                active.discard(param_name)
                continue

            violated = False
            is_upper = True

            if threshold.upper_limit > 0 and value > threshold.upper_limit:
                violated = True
                is_upper = True
            elif threshold.lower_limit > 0 and value < threshold.lower_limit:
                violated = True
                is_upper = False

            if violated and param_name not in active:
                # New violation -- record and emit
                active.add(param_name)
                label = "Upper" if is_upper else "Lower"
                message = f"{label} limit alarm: {param_name}={value}"
                alarm = AlarmRecord(
                    timestamp=data.timestamp,
                    device_id=device_id,
                    param_name=param_name,
                    current_value=value,
                    threshold=(
                        threshold.upper_limit if is_upper
                        else threshold.lower_limit
                    ),
                    is_upper_limit=is_upper,
                    message=message,
                )
                DataBus.instance().publish_alarm(alarm)
                # Persist to database
                try:
                    alarm_dict = {
                        "timestamp": (
                            alarm.timestamp.isoformat()
                            if alarm.timestamp
                            else ""
                        ),
                        "device_id": alarm.device_id,
                        "device_name": alarm.device_name,
                        "param_name": alarm.param_name,
                        "current_value": alarm.current_value,
                        "threshold": alarm.threshold,
                        "is_upper_limit": alarm.is_upper_limit,
                        "acknowledged": alarm.acknowledged,
                        "message": alarm.message,
                    }
                    DatabaseManager.instance().local_db.insert_alarm_record(
                        alarm_dict
                    )
                except Exception as e:
                    logger.error("Failed to save alarm: %s", e)
            elif not violated:
                active.discard(param_name)
