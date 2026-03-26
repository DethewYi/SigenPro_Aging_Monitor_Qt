from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class DeviceData:
    device_id: int = -1
    timestamp: datetime = None
    parameters: dict = field(default_factory=dict)  # {"voltage": 48.5, "current": 10.2}
    communication_ok: bool = True
    frame_error_count: int = 0
