from dataclasses import dataclass
from .types import ChannelStatus


@dataclass
class ChannelInfo:
    channel_id: int = -1
    status: ChannelStatus = ChannelStatus.FREE
    bound_sn: str = ""
    bound_pn: str = ""
    power_controller_id: int = -1
    contactor_controller_id: int = -1
    power_channel: int = -1
    contactor_channel: int = -1
    power_protocol_name: str = ""
    contactor_protocol_name: str = ""
