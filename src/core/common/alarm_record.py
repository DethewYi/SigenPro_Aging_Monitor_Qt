from dataclasses import dataclass
from datetime import datetime


@dataclass
class AlarmRecord:
    id: int = -1
    timestamp: datetime = None
    device_id: int = -1
    device_name: str = ""
    param_name: str = ""
    current_value: float = 0
    threshold: float = 0
    is_upper_limit: bool = True
    acknowledged: bool = False
    message: str = ""
