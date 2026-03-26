from enum import Enum, auto
from dataclasses import dataclass, field


class DeviceStatus(Enum):
    OFFLINE = auto()
    IDLE = auto()
    TESTING = auto()
    COMPLETED = auto()
    ALARM = auto()
    FAULT = auto()


class ChannelStatus(Enum):
    FREE = auto()
    BOUND = auto()
    TESTING = auto()
    FAULT = auto()


class TestResult(Enum):
    PENDING = auto()
    PASSED = auto()
    FAILED = auto()
    INTERRUPTED = auto()


class CommunicationType(Enum):
    TCP_SOCKET = auto()
    CAN_BUS = auto()
    RS485 = auto()


@dataclass
class DeviceConfig:
    device_id: int = -1
    name: str = ""
    model: str = ""
    comm_type: CommunicationType = CommunicationType.TCP_SOCKET
    ip_address: str = ""
    port: int = 0
    protocol_name: str = ""
    channel_id: int = -1
