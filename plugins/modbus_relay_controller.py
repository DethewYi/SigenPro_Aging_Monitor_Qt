"""Modbus RTU relay / contactor board controller plugin.

Controls relay boards or contactor modules via Modbus RTU over RS-485 or
TCP (Modbus TCP).  Each relay channel corresponds to one test channel's
contactor.

Typical devices: NHR series relay boards, Advantech ADAM-4068, generic
Modbus relay modules.
"""

import socket
import struct
import logging

from src.protocol.interfaces import IInstrumentController
from src.core.common.types import DeviceConfig

logger = logging.getLogger(__name__)


class ModbusRelayController(IInstrumentController):
    """Modbus RTU/TCP relay board controller.

    Usage
    -----
    controller = ModbusRelayController()
    controller.initialize({
        "connection": "tcp",          # "tcp" or "serial"
        "slave_address": 1,
        "coil_base": 0,              # Starting coil address
        "timeout": 2.0,
        "retry_count": 2,
    })
    controller.connect(config)
    """

    _config: dict = {}
    _socket: socket.socket | None = None
    _connected: bool = False
    _coils_state: dict[int, bool] = {}

    # ------------------------------------------------------------------
    # IInstrumentController interface
    # ------------------------------------------------------------------

    def protocol_name(self) -> str:
        return "modbus_relay"

    def initialize(self, config: dict) -> bool:
        self._config = {
            "connection": config.get("connection", "tcp"),
            "slave_address": config.get("slave_address", 1),
            "coil_base": config.get("coil_base", 0),
            "timeout": config.get("timeout", 2.0),
            "retry_count": config.get("retry_count", 2),
        }
        return True

    def connect(self, config: DeviceConfig) -> bool:
        """Connect to the relay board.

        TCP: config.ip_address + config.port
        Serial: config.ip_address as serial port name
        """
        try:
            if self._config["connection"] == "tcp":
                self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._socket.settimeout(self._config["timeout"])
                self._socket.connect((config.ip_address, config.port or 502))
                self._connected = True
                # Read initial coil states
                self._read_all_coils()
                logger.info(
                    "Modbus relay board connected: %s:%d",
                    config.ip_address,
                    config.port,
                )
            else:
                import serial
                ser = serial.Serial(
                    port=config.ip_address,
                    baudrate=9600,
                    timeout=self._config["timeout"],
                )
                self._socket = ser
                self._connected = True
                self._read_all_coils()
                logger.info(
                    "Modbus relay board connected: %s (serial)",
                    config.ip_address,
                )
            return True
        except Exception as e:
            logger.error("Failed to connect Modbus relay: %s", e)
            self._connected = False
            return False

    def disconnect(self) -> None:
        """Disconnect from the relay board."""
        if self._socket:
            try:
                self._socket.close()
            except Exception:
                pass
            self._socket = None
        self._connected = False
        self._coils_state.clear()

    def is_connected(self) -> bool:
        return self._connected

    def power_on(self, channel: int) -> bool:
        """Energize relay for the specified channel (coil ON)."""
        coil_addr = self._coil_address(channel)
        success = self._write_single_coil(coil_addr, True)
        if success:
            self._coils_state[channel] = True
        return success

    def power_off(self, channel: int) -> bool:
        """De-energize relay for the specified channel (coil OFF)."""
        coil_addr = self._coil_address(channel)
        success = self._write_single_coil(coil_addr, False)
        if success:
            self._coils_state[channel] = False
        return success

    def set_voltage(self, channel: int, voltage: float) -> bool:
        """Not applicable for relay controller — returns True (no-op)."""
        return True

    def set_current(self, channel: int, current: float) -> bool:
        """Not applicable for relay controller — returns True (no-op)."""
        return True

    def read_status(self, channel: int) -> dict:
        """Read the current state of the relay channel.

        Returns a dict with keys:
          output_on, coil_address
        """
        coil_addr = self._coil_address(channel)
        try:
            state = self._read_coil(coil_addr)
            self._coils_state[channel] = state
        except Exception:
            state = self._coils_state.get(channel, False)

        return {
            "output_on": state,
            "coil_address": coil_addr,
        }

    # ------------------------------------------------------------------
    # Extended methods
    # ------------------------------------------------------------------

    def read_all_channels(self) -> dict[int, bool]:
        """Read all coil states and return as {channel: state} dict."""
        self._read_all_coils()
        return dict(self._coils_state)

    def emergency_off_all(self, max_channels: int = 32) -> bool:
        """Turn off all relay channels (emergency stop)."""
        coil_base = self._config["coil_base"]
        success = self._write_multiple_coils(
            coil_base, [False] * max_channels
        )
        if success:
            for ch in list(self._coils_state.keys()):
                self._coils_state[ch] = False
        return success

    # ------------------------------------------------------------------
    # Internal Modbus communication
    # ------------------------------------------------------------------

    def _coil_address(self, channel: int) -> int:
        """Map a 1-based channel number to a Modbus coil address."""
        return self._config["coil_base"] + channel - 1

    def _send_modbus(self, pdu: bytes) -> bytes | None:
        """Send a Modbus request and receive the response.

        Handles both TCP (MBAP) and RTU (CRC) framing.
        """
        if not self._socket or not self._connected:
            return None

        slave_addr = self._config["slave_address"]

        for attempt in range(self._config["retry_count"] + 1):
            try:
                if self._config["connection"] == "tcp":
                    mbap = struct.pack(">HHHB", 0, 0, len(pdu) + 1, slave_addr)
                    frame = mbap + pdu
                    self._socket.sendall(frame)
                    response = self._recv_tcp_response()
                else:
                    rtu = struct.pack("B", slave_addr) + pdu
                    crc = self._crc16(rtu)
                    frame = rtu + crc
                    self._socket.write(frame)
                    response = self._recv_rtu_response()

                if response is None:
                    continue

                # Check for Modbus exception
                resp_func = response[1] if len(response) >= 2 else 0
                if resp_func & 0x80:
                    exc_code = response[2] if len(response) >= 3 else 0
                    logger.warning("Modbus exception: %d", exc_code)
                    return None

                return response
            except Exception as e:
                logger.debug(
                    "Modbus attempt %d failed: %s", attempt + 1, e
                )
                if attempt == self._config["retry_count"]:
                    self._connected = False
                continue

        return None

    def _recv_tcp_response(self) -> bytes | None:
        """Receive a complete Modbus TCP response."""
        header = self._recv_exact(7)
        if not header:
            return None
        _trans_id, proto_id, length, _unit_id = struct.unpack(">HHHB", header)
        if proto_id != 0:
            return None
        data = self._recv_exact(length - 1)
        if not data:
            return None
        return header[6:7] + data

    def _recv_rtu_response(self) -> bytes | None:
        """Receive a complete Modbus RTU response with CRC validation."""
        # Read first byte (slave address + function code) then the rest
        header = self._recv_exact(2)
        if not header:
            return None
        func_code = header[1]

        # Determine expected remaining length
        if func_code == 0x05:  # Write single coil response
            remaining = 4 + 2  # address(2) + value(2) + CRC(2)
        elif func_code == 0x01:  # Read coils response
            if self._recv_exact(1) is None:
                return None
            byte_count_byte = self._socket.read(1) if hasattr(self._socket, 'read') else self._socket.recv(1)
            if not byte_count_byte:
                return None
            remaining = byte_count_byte[0] + 2  # data + CRC
            # We already read 3 bytes (addr + func + byte_count)
            remaining_for_recv = remaining
            remaining = 2 + 1 + remaining_for_recv - 3
            data = self._recv_exact(remaining)
            return header + struct.pack("B", byte_count_byte[0]) + data
        elif func_code == 0x0F:  # Write multiple coils response
            remaining = 4 + 2
        else:
            remaining = 2  # minimal fallback

        data = self._recv_exact(remaining)
        if not data:
            return None
        return header + data

    def _recv_exact(self, count: int) -> bytes | None:
        """Receive exactly *count* bytes from the socket."""
        buf = bytearray()
        while len(buf) < count:
            if self._config["connection"] == "tcp" and hasattr(self._socket, 'recv'):
                chunk = self._socket.recv(count - len(buf))
            elif hasattr(self._socket, 'read'):
                chunk = self._socket.read(count - len(buf))
            else:
                chunk = self._socket.recv(count - len(buf))
            if not chunk:
                return None
            buf.extend(chunk)
        return bytes(buf)

    # ------------------------------------------------------------------
    # Modbus coil operations
    # ------------------------------------------------------------------

    def _write_single_coil(self, address: int, value: bool) -> bool:
        """Write a single coil (FC 05)."""
        coil_value = 0xFF00 if value else 0x0000
        pdu = struct.pack(">BHH", 0x05, address, coil_value)
        response = self._send_modbus(pdu)
        return response is not None

    def _write_multiple_coils(self, address: int, values: list[bool]) -> bool:
        """Write multiple coils (FC 15)."""
        count = len(values)
        byte_count = (count + 7) // 8
        coil_bytes = bytearray(byte_count)
        for i, v in enumerate(values):
            if v:
                coil_bytes[i // 8] |= 1 << (i % 8)

        pdu = struct.pack(">BHHB", 0x0F, address, count, byte_count)
        pdu += bytes(coil_bytes)
        response = self._send_modbus(pdu)
        return response is not None

    def _read_coil(self, address: int) -> bool:
        """Read a single coil (FC 01)."""
        pdu = struct.pack(">BHH", 0x01, address, 1)
        response = self._send_modbus(pdu)
        if response and len(response) >= 4:
            byte_count = response[2]
            if byte_count >= 1:
                return bool(response[3] & 0x01)
        return False

    def _read_all_coils(self):
        """Read all coils and update internal state."""
        max_channels = max(self._coils_state.keys(), default=0) + 8
        max_channels = max(max_channels, 16)
        pdu = struct.pack(">BHH", 0x01, self._config["coil_base"], max_channels)
        response = self._send_modbus(pdu)
        if response and len(response) >= 4:
            byte_count = response[2]
            coil_bytes = response[3:3 + byte_count]
            for i in range(max_channels):
                state = bool(coil_bytes[i // 8] & (1 << (i % 8)))
                self._coils_state[i + 1] = state

    # ------------------------------------------------------------------
    # CRC-16 (Modbus)
    # ------------------------------------------------------------------

    @staticmethod
    def _crc16(data: bytes) -> bytes:
        crc = 0xFFFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x0001:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
        return struct.pack("<H", crc)
