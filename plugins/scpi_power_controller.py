"""SCPI programmable DC power supply controller plugin.

Controls standard SCPI-compatible programmable power supplies via TCP or
serial (RS-232/RS-485).  Supports common commands for voltage/current
programming, output on/off, and status reading.

Typical devices: Chroma 62000P, Keysight N5700, Kikusui PWR series, etc.
"""

import socket
import time
import logging

from src.protocol.interfaces import IInstrumentController
from src.core.common.types import DeviceConfig

logger = logging.getLogger(__name__)


class ScpiPowerController(IInstrumentController):
    """SCPI-based programmable DC power supply controller.

    Usage
    -----
    controller = ScpiPowerController()
    controller.initialize({
        "connection": "tcp",          # "tcp" or "serial"
        "timeout": 3.0,
        "read_termination": "\\n",
        "write_termination": "\\n",
        "channel_prefix": "",         # e.g. "INST:NSEL " for multi-channel
        "max_voltage": 60.0,
        "max_current": 50.0,
    })
    controller.connect(config)
    """

    _config: dict = {}
    _socket: socket.socket | None = None
    _connected: bool = False
    _channel_voltages: dict[int, float] = {}
    _channel_currents: dict[int, float] = {}

    # ------------------------------------------------------------------
    # IInstrumentController interface
    # ------------------------------------------------------------------

    def protocol_name(self) -> str:
        return "scpi_power"

    def initialize(self, config: dict) -> bool:
        self._config = {
            "connection": config.get("connection", "tcp"),
            "timeout": config.get("timeout", 3.0),
            "read_termination": config.get("read_termination", "\n"),
            "write_termination": config.get("write_termination", "\n"),
            "channel_prefix": config.get("channel_prefix", ""),
            "max_voltage": config.get("max_voltage", 60.0),
            "max_current": config.get("max_current", 50.0),
        }
        return True

    def connect(self, config: DeviceConfig) -> bool:
        """Connect to the power supply.

        Uses config.ip_address and config.port for TCP, or
        config.ip_address as serial port name for serial mode.
        """
        try:
            if self._config["connection"] == "tcp":
                self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._socket.settimeout(self._config["timeout"])
                self._socket.connect((config.ip_address, config.port or 5025))
                self._connected = True
                # Verify connection with *IDN?
                idn = self._query("*IDN?")
                logger.info("SCPI power supply connected: %s", idn)
            else:
                # Serial connection via pyserial
                import serial
                ser = serial.Serial(
                    port=config.ip_address,
                    baudrate=9600,
                    timeout=self._config["timeout"],
                )
                self._socket = ser
                self._connected = True
                idn = self._query("*IDN?")
                logger.info("SCPI power supply connected: %s", idn)

            # Disable front panel lock for safety
            self._write("SYST:LOCK:DIS")
            return True
        except Exception as e:
            logger.error("Failed to connect SCPI power supply: %s", e)
            self._connected = False
            return False

    def disconnect(self) -> None:
        """Disconnect from the power supply."""
        if self._socket:
            try:
                self._write("SYST:LOC")  # Return to local mode
            except Exception:
                pass
            try:
                self._socket.close()
            except Exception:
                pass
            self._socket = None
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def power_on(self, channel: int) -> bool:
        """Turn on output for the specified channel."""
        prefix = self._channel_prefix(channel)
        return self._write(f"{prefix}OUTP:STAT ON") is not None

    def power_off(self, channel: int) -> bool:
        """Turn off output for the specified channel."""
        prefix = self._channel_prefix(channel)
        return self._write(f"{prefix}OUTP:STAT OFF") is not None

    def set_voltage(self, channel: int, voltage: float) -> bool:
        """Set the output voltage with safety clamping."""
        max_v = self._config["max_voltage"]
        voltage = max(0.0, min(voltage, max_v))
        prefix = self._channel_prefix(channel)
        result = self._write(f"{prefix}VOLT {voltage:.3f}")
        if result is not None:
            self._channel_voltages[channel] = voltage
            return True
        return False

    def set_current(self, channel: int, current: float) -> bool:
        """Set the output current limit with safety clamping."""
        max_i = self._config["max_current"]
        current = max(0.0, min(current, max_i))
        prefix = self._channel_prefix(channel)
        result = self._write(f"{prefix}CURR {current:.3f}")
        if result is not None:
            self._channel_currents[channel] = current
            return True
        return True

    def read_status(self, channel: int) -> dict:
        """Read the current status of the specified channel.

        Returns a dict with keys:
          output_on, voltage_set, current_set, voltage_actual, current_actual
        """
        prefix = self._channel_prefix(channel)
        result = {}

        try:
            result["output_on"] = self._query(f"{prefix}OUTP:STAT?") == "1"
        except Exception:
            result["output_on"] = False

        try:
            result["voltage_set"] = float(
                self._query(f"{prefix}VOLT?")
            )
        except Exception:
            result["voltage_set"] = self._channel_voltages.get(channel, 0.0)

        try:
            result["current_set"] = float(
                self._query(f"{prefix}CURR?")
            )
        except Exception:
            result["current_set"] = self._channel_currents.get(channel, 0.0)

        try:
            result["voltage_actual"] = float(
                self._query("MEAS:VOLT?")
            )
        except Exception:
            result["voltage_actual"] = 0.0

        try:
            result["current_actual"] = float(
                self._query("MEAS:CURR?")
            )
        except Exception:
            result["current_actual"] = 0.0

        return result

    # ------------------------------------------------------------------
    # Extended SCPI commands (beyond IInstrumentController interface)
    # ------------------------------------------------------------------

    def trigger_protection_check(self, channel: int) -> str:
        """Query protection status (OVP, OCP, OPP, OTP)."""
        prefix = self._channel_prefix(channel)
        return self._query(f"{prefix}STAT:QUES:COND?") or "0"

    def clear_protection(self, channel: int) -> bool:
        """Clear all protection faults."""
        prefix = self._channel_prefix(channel)
        return self._write(f"{prefix}STAT:PROT:CLE") is not None

    def get_error_queue(self) -> str:
        """Read the next error from the error queue."""
        return self._query("SYST:ERR?") or "No error"

    # ------------------------------------------------------------------
    # Internal communication
    # ------------------------------------------------------------------

    def _channel_prefix(self, channel: int) -> str:
        """Return the SCPI command prefix for a given channel."""
        prefix = self._config["channel_prefix"]
        if prefix:
            return prefix.format(ch=channel)
        return ""

    def _write(self, command: str) -> str | None:
        """Send a SCPI command."""
        if not self._socket or not self._connected:
            return None
        try:
            term = self._config["write_termination"]
            full_cmd = command + term
            if self._config["connection"] == "tcp":
                self._socket.sendall(full_cmd.encode("ascii"))
            else:
                self._socket.write(full_cmd.encode("ascii"))
            return ""
        except Exception as e:
            logger.error("SCPI write failed: %s", e)
            self._connected = False
            return None

    def _query(self, command: str) -> str | None:
        """Send a SCPI command and read the response."""
        if self._write(command) is None:
            return None
        try:
            read_term = self._config["read_termination"]
            if self._config["connection"] == "tcp":
                response = b""
                while read_term.encode("ascii") not in response:
                    chunk = self._socket.recv(256)
                    if not chunk:
                        break
                    response += chunk
            else:
                response = self._socket.readline()
            result = response.decode("ascii").strip()
            return result
        except Exception as e:
            logger.error("SCPI query failed: %s", e)
            self._connected = False
            return None
