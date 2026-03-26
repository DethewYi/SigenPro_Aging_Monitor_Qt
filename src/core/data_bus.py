"""Global singleton event bus using PyQt6 signals.

Provides a decoupled publish/subscribe mechanism for device data,
alarms, status changes, and raw data throughout the application.
"""

from PyQt6.QtCore import QObject, pyqtSignal


class DataBus(QObject):
    """Central event bus that all modules use to communicate.

    Typical usage::

        # Publisher
        DataBus.instance().publish_device_data(data)

        # Subscriber
        DataBus.instance().device_data_received.connect(self._on_data)
    """

    _instance = None

    device_data_received = pyqtSignal(object)       # DeviceData
    alarm_triggered = pyqtSignal(object)             # AlarmRecord
    device_status_changed = pyqtSignal(int, object)  # device_id, DeviceStatus
    raw_data_received = pyqtSignal(int, bytes)       # device_id, raw_data

    def __init__(self):
        super().__init__()

    @classmethod
    def instance(cls):
        """Return the global DataBus singleton."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def publish_device_data(self, data):
        """Emit a parsed *DeviceData* payload."""
        self.device_data_received.emit(data)

    def publish_alarm(self, alarm):
        """Emit an *AlarmRecord*."""
        self.alarm_triggered.emit(alarm)

    def publish_device_status(self, device_id, status):
        """Emit a device status change."""
        self.device_status_changed.emit(device_id, status)

    def publish_raw_data(self, device_id, raw_data):
        """Emit raw bytes received from a device."""
        self.raw_data_received.emit(device_id, raw_data)
