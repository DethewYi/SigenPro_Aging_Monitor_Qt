"""Test execution engine.

Manages the lifecycle of aging tests per channel:
starting, pausing, resuming, timing, and completion.

Each channel runs independently.  A shared 1-second tick timer
is active whenever at least one test is running and emits
progress signals for the UI to consume.
"""

from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from datetime import datetime
import logging

from .common.types import TestResult
from .common.test_template import TestTemplate
from ..storage.database_manager import DatabaseManager

logger = logging.getLogger(__name__)


class TestEngine(QObject):
    """Orchestrates test execution across multiple channels.

    Signals:
        test_started:   Emitted with *channel_id* when a test begins.
        test_paused:    Emitted with *channel_id* when a test is paused.
        test_resumed:   Emitted with *channel_id* when a test resumes.
        test_completed: Emitted with *(channel_id, result)* when a test
            finishes (pass, fail, or interrupt).
        test_progress:  Emitted with *(channel_id, elapsed_s, total_s)*
            every second for running tests.
    """

    test_started = pyqtSignal(int)
    test_paused = pyqtSignal(int)
    test_resumed = pyqtSignal(int)
    test_completed = pyqtSignal(int, object)       # channel_id, TestResult
    test_progress = pyqtSignal(int, int, int)       # channel_id, elapsed, total

    class State:
        """Possible test states for a channel."""
        IDLE = "idle"
        STARTING = "starting"
        RUNNING = "running"
        PAUSED = "paused"
        COMPLETED = "completed"
        INTERRUPTED = "interrupted"

    def __init__(self, parent=None):
        super().__init__(parent)
        # channel_id -> context dict
        self._contexts: dict[int, dict] = {}
        self._tick_timer = QTimer(self)
        self._tick_timer.timeout.connect(self._on_tick)
        self._alarm_engine = None
        self._template_manager = None

    # ------------------------------------------------------------------
    # Dependencies
    # ------------------------------------------------------------------

    def set_alarm_engine(self, engine):
        """Wire in the :class:`AlarmEngine` for threshold management."""
        self._alarm_engine = engine

    def set_template_manager(self, manager):
        """Wire in the :class:`TemplateManager` for template look-ups."""
        self._template_manager = manager

    # ------------------------------------------------------------------
    # Test lifecycle
    # ------------------------------------------------------------------

    def start_test(self, channel_id: int, template_id: int) -> bool:
        """Start a new test on *channel_id* using *template_id*.

        Returns:
            True if the test was started successfully.
        """
        ctx = self._contexts.get(channel_id)
        if ctx and ctx["state"] == self.State.RUNNING:
            return False

        tmpl = (
            self._template_manager.get_template(template_id)
            if self._template_manager
            else None
        )
        if not tmpl:
            logger.error("Template %d not found", template_id)
            return False

        now = datetime.now()
        ctx = {
            "state": self.State.STARTING,
            "template_id": template_id,
            "template": tmpl,
            "start_time": now,
            "pause_time": None,
            "paused_seconds": 0,
            "has_alarm": False,
        }
        self._contexts[channel_id] = ctx

        # Arm alarm thresholds
        if self._alarm_engine:
            self._alarm_engine.set_active_thresholds(
                channel_id, tmpl.default_thresholds
            )
            if tmpl.phases:
                self._alarm_engine.set_phase_thresholds(
                    channel_id, tmpl.phases
                )
            self._alarm_engine.set_phase_start_time(channel_id, now)

        # Persist test record
        try:
            DatabaseManager.instance().local_db.save_test_record(
                template_id=template_id,
                channel_id=channel_id,
                device_sn="",
                device_pn="",
                start_time=now.isoformat(),
                end_time=None,
                result=TestResult.PENDING.value,
            )
        except Exception as e:
            logger.error("Failed to save test record: %s", e)

        ctx["state"] = self.State.RUNNING
        if not self._tick_timer.isActive():
            self._tick_timer.start(1000)
        self.test_started.emit(channel_id)
        logger.info("Test started on channel %d", channel_id)
        return True

    def pause_test(self, channel_id: int) -> bool:
        """Pause a running test."""
        ctx = self._contexts.get(channel_id)
        if not ctx or ctx["state"] != self.State.RUNNING:
            return False
        ctx["state"] = self.State.PAUSED
        ctx["pause_time"] = datetime.now()
        self.test_paused.emit(channel_id)
        return True

    def resume_test(self, channel_id: int) -> bool:
        """Resume a paused test."""
        ctx = self._contexts.get(channel_id)
        if not ctx or ctx["state"] != self.State.PAUSED:
            return False
        if ctx["pause_time"]:
            paused_duration = (
                datetime.now() - ctx["pause_time"]
            ).total_seconds()
            ctx["paused_seconds"] += paused_duration
            ctx["pause_time"] = None
        ctx["state"] = self.State.RUNNING
        self.test_resumed.emit(channel_id)
        return True

    def stop_test(self, channel_id: int, result: TestResult | None = None) -> bool:
        """Stop a running or paused test.

        Args:
            result: Override result. Defaults to INTERRUPTED.

        Returns:
            True if the test was stopped.
        """
        ctx = self._contexts.get(channel_id)
        if not ctx or ctx["state"] not in (
            self.State.RUNNING,
            self.State.PAUSED,
        ):
            return False

        result = result or TestResult.INTERRUPTED
        ctx["state"] = (
            self.State.COMPLETED
            if result == TestResult.PASSED
            else self.State.INTERRUPTED
        )

        # Disarm alarm thresholds
        if self._alarm_engine:
            self._alarm_engine.clear_thresholds(channel_id)

        # Update test record
        try:
            DatabaseManager.instance().local_db.save_test_record(
                template_id=ctx["template_id"],
                channel_id=channel_id,
                device_sn="",
                device_pn="",
                start_time=ctx["start_time"].isoformat(),
                end_time=datetime.now().isoformat(),
                result=result.value,
            )
        except Exception as e:
            logger.error("Failed to update test record: %s", e)

        self.test_completed.emit(channel_id, result)
        logger.info("Test on channel %d completed: %s", channel_id, result.name)

        # Stop tick timer if no active tests remain
        if not any(
            c["state"] == self.State.RUNNING
            for c in self._contexts.values()
        ):
            self._tick_timer.stop()
        return True

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def set_has_alarm(self, channel_id: int):
        """Mark that an alarm occurred during this test (forces FAILED)."""
        ctx = self._contexts.get(channel_id)
        if ctx:
            ctx["has_alarm"] = True

    def test_state(self, channel_id: int) -> str:
        """Return the current test state string for *channel_id*."""
        ctx = self._contexts.get(channel_id)
        return ctx["state"] if ctx else self.State.IDLE

    def elapsed_seconds(self, channel_id: int) -> int:
        """Return the effective elapsed seconds, excluding pause time."""
        ctx = self._contexts.get(channel_id)
        if not ctx:
            return 0
        elapsed = (
            (datetime.now() - ctx["start_time"]).total_seconds()
            - ctx["paused_seconds"]
        )
        if ctx["state"] == self.State.PAUSED and ctx["pause_time"]:
            elapsed -= (datetime.now() - ctx["pause_time"]).total_seconds()
        return max(0, int(elapsed))

    def remaining_seconds(self, channel_id: int) -> int:
        """Return the remaining test seconds for *channel_id*."""
        ctx = self._contexts.get(channel_id)
        if not ctx:
            return 0
        total = ctx["template"].total_duration_minutes * 60
        return max(0, total - self.elapsed_seconds(channel_id))

    # ------------------------------------------------------------------
    # Tick
    # ------------------------------------------------------------------

    def _on_tick(self):
        """Called every second while at least one test is running."""
        to_complete: list[int] = []
        for channel_id, ctx in list(self._contexts.items()):
            if ctx["state"] != self.State.RUNNING:
                continue
            elapsed = self.elapsed_seconds(channel_id)
            total = ctx["template"].total_duration_minutes * 60
            self.test_progress.emit(channel_id, elapsed, total)
            if elapsed >= total:
                to_complete.append(channel_id)
        for channel_id in to_complete:
            result = (
                TestResult.FAILED
                if self._contexts[channel_id]["has_alarm"]
                else TestResult.PASSED
            )
            self.stop_test(channel_id, result)
