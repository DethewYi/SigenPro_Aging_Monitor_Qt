from dataclasses import dataclass, field


@dataclass
class AlarmThreshold:
    upper_limit: float = 0
    lower_limit: float = 0
    enabled: bool = False


@dataclass
class TestPhase:
    name: str = ""
    duration_minutes: int = 0
    thresholds: dict = field(default_factory=dict)  # param_name -> AlarmThreshold


@dataclass
class TestTemplate:
    template_id: int = -1
    name: str = ""
    product_model: str = ""
    collect_params: dict = field(default_factory=dict)  # param_name -> frequency_hz
    total_duration_minutes: int = 0
    default_thresholds: dict = field(default_factory=dict)  # param_name -> AlarmThreshold
    phases: list = field(default_factory=list)  # list of TestPhase
