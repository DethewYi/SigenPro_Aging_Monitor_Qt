"""Multi-phase aging recipe executor.

Manages per-channel recipe execution with phase transitions,
relay action sequencing, power control, and alarm-triggered emergency stop.
"""

import logging
from datetime import datetime

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from .common.aging_recipe import AgingRecipe, RelayAction
from .common.types import TestResult

logger = logging.getLogger(__name__)


class RecipeExecutor(QObject):
    """Executes aging recipes on individual channels.

    Signals:
        recipe_started(channel_id): Recipe execution has begun.
        recipe_paused(channel_id): Recipe has been paused.
        recipe_resumed(channel_id): Recipe has been resumed.
        recipe_completed(channel_id, TestResult): Recipe finished.
        phase_changed(channel_id, phase_index, total_phases): New phase entered.
        phase_progress(channel_id, phase_index, elapsed_s, duration_s): Tick progress.
    """

    recipe_started = pyqtSignal(int)
    recipe_paused = pyqtSignal(int)
    recipe_resumed = pyqtSignal(int)
    recipe_completed = pyqtSignal(int, object)
    phase_changed = pyqtSignal(int, int, int)
    phase_progress = pyqtSignal(int, int, int, int)

    # Internal states
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    INTERRUPTED = "interrupted"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._contexts: dict[int, dict] = {}
        self._alarm_engine = None
        self._recipe_manager = None
        self._channel_manager = None

        self._tick_timer = QTimer(self)
        self._tick_timer.setInterval(1000)
        self._tick_timer.timeout.connect(self._on_tick)

    # ------------------------------------------------------------------
    # Dependencies
    # ------------------------------------------------------------------

    def set_alarm_engine(self, engine):
        self._alarm_engine = engine

    def set_recipe_manager(self, manager):
        self._recipe_manager = manager

    def set_channel_manager(self, manager):
        self._channel_manager = manager

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start_recipe(self, channel_id: int, recipe_id: int) -> bool:
        """Start executing a recipe on *channel_id*.

        Returns True if started successfully.
        """
        if channel_id in self._contexts:
            logger.warning("Channel %d already has a running recipe", channel_id)
            return False

        recipe = self._recipe_manager.get_recipe(recipe_id)
        if not recipe:
            logger.error("Recipe %d not found", recipe_id)
            return False

        if not recipe.phases:
            logger.error("Recipe %d has no phases", recipe_id)
            return False

        now = datetime.now()
        ctx = {
            "state": self.RUNNING,
            "recipe": recipe,
            "current_phase_index": 0,
            "phase_start_time": now,
            "total_start_time": now,
            "paused_seconds": 0,
            "pause_start_time": None,
            "has_alarm": False,
        }
        self._contexts[channel_id] = ctx

        # Execute on_start event actions
        self._execute_relay_actions(channel_id, recipe.event_actions.on_start)

        # Set power for phase 0
        phase = recipe.phases[0]
        if self._channel_manager:
            self._channel_manager.set_channel_output(
                channel_id, phase.voltage, phase.current
            )
            self._channel_manager.power_on(channel_id)

        # Execute phase 0 start actions
        self._execute_relay_actions(channel_id, phase.phase_start_actions)

        # Set alarm thresholds if engine available
        if self._alarm_engine and recipe.default_thresholds:
            self._alarm_engine.set_active_thresholds(channel_id, recipe.default_thresholds)

        logger.info(
            "Recipe '%s' started on channel %d (phase 0: %s)",
            recipe.name, channel_id, phase.name,
        )
        self.recipe_started.emit(channel_id)
        self.phase_changed.emit(channel_id, 0, len(recipe.phases))

        self._start_tick()
        return True

    def pause_recipe(self, channel_id: int) -> bool:
        ctx = self._contexts.get(channel_id)
        if not ctx or ctx["state"] != self.RUNNING:
            return False
        ctx["state"] = self.PAUSED
        ctx["pause_start_time"] = datetime.now()
        logger.info("Recipe paused on channel %d", channel_id)
        self.recipe_paused.emit(channel_id)
        self._check_stop_tick()
        return True

    def resume_recipe(self, channel_id: int) -> bool:
        ctx = self._contexts.get(channel_id)
        if not ctx or ctx["state"] != self.PAUSED:
            return False
        if ctx["pause_start_time"]:
            ctx["paused_seconds"] += int(
                (datetime.now() - ctx["pause_start_time"]).total_seconds()
            )
            ctx["pause_start_time"] = None
        ctx["state"] = self.RUNNING
        logger.info("Recipe resumed on channel %d", channel_id)
        self.recipe_resumed.emit(channel_id)
        self._start_tick()
        return True

    def stop_recipe(self, channel_id: int, result: TestResult = None) -> bool:
        """Stop a running recipe and clean up."""
        ctx = self._contexts.get(channel_id)
        if not ctx or ctx["state"] in (self.COMPLETED, self.INTERRUPTED):
            return False

        if result is None:
            result = TestResult.INTERRUPTED

        ctx["state"] = self.INTERRUPTED if result != TestResult.PASSED else self.COMPLETED
        recipe = ctx["recipe"]
        current_phase_idx = ctx["current_phase_index"]

        # Execute current phase end actions
        if 0 <= current_phase_idx < len(recipe.phases):
            phase = recipe.phases[current_phase_idx]
            self._execute_relay_actions(channel_id, phase.phase_end_actions)

        # Execute appropriate event actions
        if result == TestResult.PASSED:
            self._execute_relay_actions(channel_id, recipe.event_actions.on_complete)
        elif result == TestResult.FAILED:
            self._execute_relay_actions(channel_id, recipe.event_actions.on_alarm)

        # Power off
        if self._channel_manager:
            self._channel_manager.set_channel_output(channel_id, 0, 0)
            self._channel_manager.power_off(channel_id)

        # Clear alarm thresholds
        if self._alarm_engine:
            self._alarm_engine.clear_thresholds(channel_id)

        logger.info(
            "Recipe '%s' %s on channel %d",
            recipe.name,
            "completed" if result == TestResult.PASSED else "stopped",
            channel_id,
        )
        self.recipe_completed.emit(channel_id, result)
        del self._contexts[channel_id]
        self._check_stop_tick()
        return True

    def on_alarm_triggered(self, alarm) -> None:
        """Slot: handle an alarm from DataBus by emergency-stopping the channel."""
        if not alarm or not hasattr(alarm, 'device_id'):
            return
        device_id = alarm.device_id
        # device_id may map to channel_id directly
        if device_id in self._contexts:
            ctx = self._contexts[device_id]
            if ctx["state"] in (self.RUNNING, self.PAUSED):
                logger.warning(
                    "Alarm triggered on channel %d, emergency stopping recipe",
                    device_id,
                )
                ctx["has_alarm"] = True
                self.stop_recipe(device_id, TestResult.FAILED)

    def set_has_alarm(self, channel_id: int) -> None:
        """Mark a channel as having an alarm (external caller)."""
        ctx = self._contexts.get(channel_id)
        if ctx:
            ctx["has_alarm"] = True

    # ------------------------------------------------------------------
    # Tick / phase transitions
    # ------------------------------------------------------------------

    def _start_tick(self):
        if not self._tick_timer.isActive():
            self._tick_timer.start()

    def _check_stop_tick(self):
        """Stop the shared timer if no channels are actively running."""
        active = any(
            ctx["state"] == self.RUNNING for ctx in self._contexts.values()
        )
        if not active:
            self._tick_timer.stop()

    def _on_tick(self):
        now = datetime.now()
        for ch_id, ctx in list(self._contexts.items()):
            if ctx["state"] != self.RUNNING:
                continue

            recipe = ctx["recipe"]
            phase_idx = ctx["current_phase_index"]
            phase = recipe.phases[phase_idx]

            # Calculate elapsed time in current phase (excluding paused time)
            elapsed_s = int(
                (now - ctx["phase_start_time"]).total_seconds()
            ) - ctx["paused_seconds"]
            duration_s = phase.duration_minutes * 60

            self.phase_progress.emit(ch_id, phase_idx, elapsed_s, duration_s)

            # Check phase completion
            if elapsed_s >= duration_s:
                self._transition_to_next_phase(ch_id)

            # Check total time protection
            elif recipe.max_total_minutes > 0:
                total_elapsed_s = int(
                    (now - ctx["total_start_time"]).total_seconds()
                ) - ctx["paused_seconds"]
                if total_elapsed_s >= recipe.max_total_minutes * 60:
                    logger.warning(
                        "Total time protection triggered on channel %d "
                        "(%d min > %d min)",
                        ch_id, total_elapsed_s // 60, recipe.max_total_minutes,
                    )
                    self.stop_recipe(ch_id, TestResult.FAILED)

    def _transition_to_next_phase(self, channel_id: int):
        """Advance to the next phase or complete the recipe."""
        ctx = self._contexts.get(channel_id)
        if not ctx:
            return

        recipe = ctx["recipe"]
        old_idx = ctx["current_phase_index"]
        old_phase = recipe.phases[old_idx]

        # Execute current phase end actions
        self._execute_relay_actions(channel_id, old_phase.phase_end_actions)

        # Advance
        new_idx = old_idx + 1
        if new_idx >= len(recipe.phases):
            # All phases done
            logger.info("All phases completed on channel %d", channel_id)
            self.stop_recipe(channel_id, TestResult.PASSED)
            return

        # Enter new phase
        new_phase = recipe.phases[new_idx]
        ctx["current_phase_index"] = new_idx
        ctx["phase_start_time"] = datetime.now()
        ctx["paused_seconds"] = 0

        # Set power for new phase
        if self._channel_manager:
            self._channel_manager.set_channel_output(
                channel_id, new_phase.voltage, new_phase.current
            )

        # Execute new phase start actions
        self._execute_relay_actions(channel_id, new_phase.phase_start_actions)

        logger.info(
            "Channel %d transitioned: phase %d '%s' -> phase %d '%s'",
            channel_id, old_idx, old_phase.name, new_idx, new_phase.name,
        )
        self.phase_changed.emit(channel_id, new_idx, len(recipe.phases))

    # ------------------------------------------------------------------
    # Relay action execution
    # ------------------------------------------------------------------

    def _execute_relay_actions(self, channel_id: int, actions: list[RelayAction]):
        """Execute a list of relay actions sequentially, respecting delay_ms."""
        if not actions or not self._channel_manager:
            return

        cumulative_delay = 0
        for action in actions:
            if action.delay_ms > 0:
                cumulative_delay += action.delay_ms
                delay = cumulative_delay
                QTimer.singleShot(
                    delay,
                    lambda cid=channel_id, a=action: self._do_relay_action(cid, a),
                )
            else:
                self._do_relay_action(channel_id, action)

    def _do_relay_action(self, channel_id: int, action: RelayAction):
        """Execute a single relay action."""
        ok = self._channel_manager.execute_relay_action(
            channel_id, action.relay_id, action.action
        )
        logger.debug(
            "Relay action ch%d coil%d %s -> %s",
            channel_id, action.relay_id, action.action, "ok" if ok else "fail",
        )

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def is_running(self, channel_id: int) -> bool:
        ctx = self._contexts.get(channel_id)
        return ctx is not None and ctx["state"] == self.RUNNING

    def recipe_state(self, channel_id: int) -> str:
        ctx = self._contexts.get(channel_id)
        return ctx["state"] if ctx else self.IDLE

    def current_phase_index(self, channel_id: int) -> int:
        ctx = self._contexts.get(channel_id)
        return ctx["current_phase_index"] if ctx else -1

    def current_phase_name(self, channel_id: int) -> str:
        ctx = self._contexts.get(channel_id)
        if not ctx:
            return ""
        idx = ctx["current_phase_index"]
        recipe = ctx["recipe"]
        if 0 <= idx < len(recipe.phases):
            return recipe.phases[idx].name
        return ""

    def remaining_phase_seconds(self, channel_id: int) -> int:
        ctx = self._contexts.get(channel_id)
        if not ctx or ctx["state"] != self.RUNNING:
            return 0
        phase = ctx["recipe"].phases[ctx["current_phase_index"]]
        elapsed_s = int(
            (datetime.now() - ctx["phase_start_time"]).total_seconds()
        ) - ctx["paused_seconds"]
        return max(0, phase.duration_minutes * 60 - elapsed_s)

    def total_elapsed_seconds(self, channel_id: int) -> int:
        ctx = self._contexts.get(channel_id)
        if not ctx:
            return 0
        return int(
            (datetime.now() - ctx["total_start_time"]).total_seconds()
        ) - ctx["paused_seconds"]

    def active_recipe(self, channel_id: int) -> AgingRecipe | None:
        ctx = self._contexts.get(channel_id)
        return ctx["recipe"] if ctx else None

    def active_channels(self) -> list[int]:
        """Return channel IDs with running or paused recipes."""
        return [
            ch_id for ch_id, ctx in self._contexts.items()
            if ctx["state"] in (self.RUNNING, self.PAUSED)
        ]
