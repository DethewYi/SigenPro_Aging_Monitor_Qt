"""Channel management and power control.

Manages the lifecycle of test channels: loading from the database,
binding/unbinding products, and controlling power supply and contactor
instruments through the plugin system.
"""

import logging

from PyQt6.QtCore import QObject, pyqtSignal

from ..core.common.types import ChannelStatus
from ..core.common.channel_info import ChannelInfo

logger = logging.getLogger(__name__)


class ChannelManager(QObject):
    """Manages test channels and their associated power/contactor controllers.

    Signals:
        channel_status_changed: Emitted when a channel's status changes.
        binding_changed: Emitted when a channel is bound or unbound.
        power_state_changed: Emitted when power is turned on or off.
    """

    channel_status_changed = pyqtSignal(int, object)   # channel_id, ChannelStatus
    binding_changed = pyqtSignal(int, str, str)          # channel_id, sn, pn
    power_state_changed = pyqtSignal(int, bool)          # channel_id, powered

    def __init__(self, parent=None):
        super().__init__(parent)
        # channel_id -> ChannelInfo
        self._channels: dict[int, ChannelInfo] = {}
        # channel_id -> IInstrumentController (power supply)
        self._power_controllers: dict[int, object] = {}
        # channel_id -> IInstrumentController (contactor)
        self._contactor_controllers: dict[int, object] = {}
        # PluginManager reference (injected)
        self._plugin_manager = None

    # ------------------------------------------------------------------
    # Dependencies
    # ------------------------------------------------------------------

    def set_plugin_manager(self, plugin_manager):
        """Set the :class:`PluginManager` used to create controllers."""
        self._plugin_manager = plugin_manager

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load_channels(self):
        """Load all channel configurations from the database."""
        from ..storage.database_manager import DatabaseManager

        try:
            rows = DatabaseManager.instance().local_db.load_all_channels()
            for row in rows:
                status_val = row.get("status", 0)
                # Map stored integer to ChannelStatus enum
                try:
                    status = list(ChannelStatus)[status_val]
                except (IndexError, TypeError):
                    status = ChannelStatus.FREE
                ch = ChannelInfo(
                    channel_id=row["channel_id"],
                    status=status,
                    bound_sn=row.get("bound_sn", ""),
                    bound_pn=row.get("bound_pn", ""),
                    power_controller_id=row.get("power_controller_id", -1),
                    contactor_controller_id=row.get(
                        "contactor_controller_id", -1
                    ),
                    power_channel=row.get("power_channel", -1),
                    contactor_channel=row.get("contactor_channel", -1),
                    power_protocol_name=row.get("power_protocol_name", ""),
                    contactor_protocol_name=row.get(
                        "contactor_protocol_name", ""
                    ),
                )
                self._channels[ch.channel_id] = ch
            logger.info("Loaded %d channels", len(self._channels))
        except Exception as e:
            logger.error("Failed to load channels: %s", e)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def all_channels(self) -> list[ChannelInfo]:
        """Return a copy of all channel info objects."""
        return list(self._channels.values())

    def channel_info(self, channel_id: int) -> ChannelInfo | None:
        """Return the :class:`ChannelInfo` for *channel_id*, or None."""
        return self._channels.get(channel_id)

    # ------------------------------------------------------------------
    # Binding
    # ------------------------------------------------------------------

    def bind_product(self, channel_id: int, sn: str, pn: str) -> bool:
        """Bind a product (serial number / part number) to a channel."""
        from ..storage.database_manager import DatabaseManager

        ch = self._channels.get(channel_id)
        if not ch:
            return False
        ch.bound_sn = sn
        ch.bound_pn = pn
        ch.status = ChannelStatus.BOUND
        try:
            self._persist_channel(ch)
        except Exception as e:
            logger.error("Failed to save channel: %s", e)
        self.channel_status_changed.emit(channel_id, ch.status)
        self.binding_changed.emit(channel_id, sn, pn)
        return True

    def unbind_product(self, channel_id: int) -> bool:
        """Unbind a product from a channel (powers off if testing)."""
        from ..storage.database_manager import DatabaseManager

        ch = self._channels.get(channel_id)
        if not ch:
            return False
        if ch.status == ChannelStatus.TESTING:
            self.power_off(channel_id)
        ch.bound_sn = ""
        ch.bound_pn = ""
        ch.status = ChannelStatus.FREE
        try:
            self._persist_channel(ch)
        except Exception as e:
            logger.error("Failed to save channel: %s", e)
        self.channel_status_changed.emit(channel_id, ch.status)
        self.binding_changed.emit(channel_id, "", "")
        return True

    # ------------------------------------------------------------------
    # Power control
    # ------------------------------------------------------------------

    def power_on(self, channel_id: int) -> bool:
        """Turn on power for a channel (contactor first, then supply)."""
        ch = self._channels.get(channel_id)
        if not ch:
            return False
        try:
            # Turn on contactor first
            if ch.contactor_protocol_name:
                ctrl = self._contactor_controllers.get(channel_id)
                if not ctrl:
                    ctrl = self._init_controller(ch, "contactor")
                    if ctrl:
                        self._contactor_controllers[channel_id] = ctrl
                if ctrl:
                    ctrl.power_on(ch.contactor_channel)
            # Then power supply
            if ch.power_protocol_name:
                ctrl = self._power_controllers.get(channel_id)
                if not ctrl:
                    ctrl = self._init_controller(ch, "power")
                    if ctrl:
                        self._power_controllers[channel_id] = ctrl
                if ctrl:
                    ctrl.power_on(ch.power_channel)
            ch.status = ChannelStatus.TESTING
            self._persist_channel(ch)
            self.channel_status_changed.emit(channel_id, ch.status)
            self.power_state_changed.emit(channel_id, True)
            return True
        except Exception as e:
            logger.error("Power on failed for channel %d: %s", channel_id, e)
            return False

    def power_off(self, channel_id: int) -> bool:
        """Turn off power for a channel (supply first, then contactor)."""
        ch = self._channels.get(channel_id)
        if not ch:
            return False
        try:
            # Turn off power supply first
            ctrl = self._power_controllers.get(channel_id)
            if ctrl:
                try:
                    ctrl.power_off(ch.power_channel)
                except Exception:
                    pass
            # Then contactor
            ctrl = self._contactor_controllers.get(channel_id)
            if ctrl:
                try:
                    ctrl.power_off(ch.contactor_channel)
                except Exception:
                    pass
            ch.status = (
                ChannelStatus.BOUND
                if ch.bound_sn
                else ChannelStatus.FREE
            )
            self._persist_channel(ch)
            self.channel_status_changed.emit(channel_id, ch.status)
            self.power_state_changed.emit(channel_id, False)
            return True
        except Exception as e:
            logger.error("Power off failed for channel %d: %s", channel_id, e)
            return False

    def emergency_stop_all(self):
        """Power off all channels that are currently testing."""
        for ch_id, ch in list(self._channels.items()):
            if ch.status == ChannelStatus.TESTING:
                self.power_off(ch_id)
        logger.warning("Emergency stop all channels")

    # ------------------------------------------------------------------
    # Controller access (for RecipeExecutor)
    # ------------------------------------------------------------------

    def get_power_controller(self, channel_id: int):
        """Return the power supply controller for *channel_id*, or None."""
        return self._power_controllers.get(channel_id)

    def get_contactor_controller(self, channel_id: int):
        """Return the contactor controller for *channel_id*, or None."""
        return self._contactor_controllers.get(channel_id)

    def execute_relay_action(self, channel_id: int, relay_id: int, action: str) -> bool:
        """Execute a single relay action on the channel's contactor controller.

        Args:
            channel_id: Channel identifier.
            relay_id: Coil number on the contactor controller.
            action: ``"CLOSE"`` or ``"OPEN"``.
        """
        ch = self._channels.get(channel_id)
        if not ch:
            return False
        ctrl = self._contactor_controllers.get(channel_id)
        if not ctrl:
            ctrl = self._init_controller(ch, "contactor")
            if ctrl:
                self._contactor_controllers[channel_id] = ctrl
        if not ctrl:
            logger.warning(
                "No contactor controller for channel %d, relay action skipped",
                channel_id,
            )
            return False
        try:
            if action.upper() == "CLOSE":
                ctrl.power_on(relay_id)
            else:
                ctrl.power_off(relay_id)
            return True
        except Exception as e:
            logger.error("Relay action failed ch%d relay%d: %s", channel_id, relay_id, e)
            return False

    def set_channel_output(self, channel_id: int, voltage: float, current: float) -> bool:
        """Set voltage and current on the channel's power supply controller."""
        ch = self._channels.get(channel_id)
        if not ch:
            return False
        ctrl = self._power_controllers.get(channel_id)
        if not ctrl:
            ctrl = self._init_controller(ch, "power")
            if ctrl:
                self._power_controllers[channel_id] = ctrl
        if not ctrl:
            logger.warning("No power controller for channel %d", channel_id)
            return False
        try:
            ctrl.set_voltage(ch.power_channel, voltage)
            ctrl.set_current(ch.power_channel, current)
            return True
        except Exception as e:
            logger.error("Set output failed ch%d: %s", channel_id, e)
            return False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _init_controller(self, ch: ChannelInfo, controller_type: str):
        """Create and connect a power or contactor controller for *ch*."""
        if not self._plugin_manager:
            logger.error("PluginManager not set; cannot create controller")
            return None
        from ..core.common.types import DeviceConfig

        protocol_name = (
            ch.power_protocol_name
            if controller_type == "power"
            else ch.contactor_protocol_name
        )
        if not protocol_name:
            return None

        config = DeviceConfig(
            device_id=(
                ch.power_controller_id
                if controller_type == "power"
                else ch.contactor_controller_id
            ),
            protocol_name=protocol_name,
        )
        controller = self._plugin_manager.create_controller(protocol_name)
        if controller:
            try:
                controller.connect(config)
            except Exception as e:
                logger.error(
                    "Failed to connect %s controller: %s",
                    controller_type,
                    e,
                )
                return None
        return controller

    def _persist_channel(self, ch: ChannelInfo):
        """Write channel info to the database as a dict."""
        from ..storage.database_manager import DatabaseManager

        DatabaseManager.instance().local_db.save_channel_info({
            "channel_id": ch.channel_id,
            "status": ch.status.value if isinstance(ch.status, ChannelStatus) else ch.status,
            "bound_sn": ch.bound_sn,
            "bound_pn": ch.bound_pn,
            "power_controller_id": ch.power_controller_id,
            "contactor_controller_id": ch.contactor_controller_id,
            "power_channel": ch.power_channel,
            "contactor_channel": ch.contactor_channel,
            "power_protocol_name": ch.power_protocol_name,
            "contactor_protocol_name": ch.contactor_protocol_name,
        })
