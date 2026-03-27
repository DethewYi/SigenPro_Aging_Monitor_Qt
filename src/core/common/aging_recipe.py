"""Data models for the aging recipe system.

AgingRecipe defines a multi-phase aging strategy keyed by product PN.
Each phase specifies power settings and relay actions for phase transitions.
Event-level actions handle lifecycle events (start, alarm, complete).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RelayAction:
    """A single relay/coil action with optional sequencing delay."""
    relay_id: int = 0
    action: str = "CLOSE"       # "OPEN" or "CLOSE"
    delay_ms: int = 0           # milliseconds to wait before this action

    def to_dict(self) -> dict:
        return {
            "relay_id": self.relay_id,
            "action": self.action,
            "delay_ms": self.delay_ms,
        }

    @classmethod
    def from_dict(cls, d: dict) -> RelayAction:
        return cls(
            relay_id=d.get("relay_id", 0),
            action=d.get("action", "CLOSE"),
            delay_ms=d.get("delay_ms", 0),
        )


@dataclass
class EventActions:
    """Container for relay actions triggered by lifecycle events."""
    on_start: list[RelayAction] = field(default_factory=list)
    on_alarm: list[RelayAction] = field(default_factory=list)
    on_complete: list[RelayAction] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "on_start": [a.to_dict() for a in self.on_start],
            "on_alarm": [a.to_dict() for a in self.on_alarm],
            "on_complete": [a.to_dict() for a in self.on_complete],
        }

    @classmethod
    def from_dict(cls, d: dict) -> EventActions:
        return cls(
            on_start=[RelayAction.from_dict(a) for a in d.get("on_start", [])],
            on_alarm=[RelayAction.from_dict(a) for a in d.get("on_alarm", [])],
            on_complete=[RelayAction.from_dict(a) for a in d.get("on_complete", [])],
        )


@dataclass
class AgingPhase:
    """One phase within an aging recipe."""
    name: str = ""
    duration_minutes: int = 0
    voltage: float = 0.0
    current: float = 0.0
    power_limit: float = 0.0       # 0 = no limit
    phase_start_actions: list[RelayAction] = field(default_factory=list)
    phase_end_actions: list[RelayAction] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "duration_minutes": self.duration_minutes,
            "voltage": self.voltage,
            "current": self.current,
            "power_limit": self.power_limit,
            "phase_start_actions": [a.to_dict() for a in self.phase_start_actions],
            "phase_end_actions": [a.to_dict() for a in self.phase_end_actions],
        }

    @classmethod
    def from_dict(cls, d: dict) -> AgingPhase:
        return cls(
            name=d.get("name", ""),
            duration_minutes=d.get("duration_minutes", 0),
            voltage=d.get("voltage", 0.0),
            current=d.get("current", 0.0),
            power_limit=d.get("power_limit", 0.0),
            phase_start_actions=[RelayAction.from_dict(a) for a in d.get("phase_start_actions", [])],
            phase_end_actions=[RelayAction.from_dict(a) for a in d.get("phase_end_actions", [])],
        )


@dataclass
class AgingRecipe:
    """A complete aging recipe, keyed by product PN (one recipe per PN)."""
    recipe_id: int = -1
    name: str = ""
    product_pn: str = ""
    max_total_minutes: int = 0     # 0 = disabled
    phases: list[AgingPhase] = field(default_factory=list)
    event_actions: EventActions = field(default_factory=EventActions)
    default_thresholds: dict = field(default_factory=dict)
    collect_params: dict = field(default_factory=dict)

    @property
    def total_duration_minutes(self) -> int:
        return sum(p.duration_minutes for p in self.phases)

    def to_dict(self) -> dict:
        return {
            "recipe_id": self.recipe_id,
            "name": self.name,
            "product_pn": self.product_pn,
            "max_total_minutes": self.max_total_minutes,
            "phases": [p.to_dict() for p in self.phases],
            "event_actions": self.event_actions.to_dict(),
            "default_thresholds": self.default_thresholds,
            "collect_params": self.collect_params,
        }

    @classmethod
    def from_dict(cls, d: dict) -> AgingRecipe:
        return cls(
            recipe_id=d.get("recipe_id", -1),
            name=d.get("name", ""),
            product_pn=d.get("product_pn", ""),
            max_total_minutes=d.get("max_total_minutes", 0),
            phases=[AgingPhase.from_dict(p) for p in d.get("phases", [])],
            event_actions=EventActions.from_dict(d.get("event_actions", {})),
            default_thresholds=d.get("default_thresholds", {}),
            collect_params=d.get("collect_params", {}),
        )
