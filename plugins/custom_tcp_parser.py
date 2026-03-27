"""Custom binary frame protocol parser for TCP devices.

Frame layout::

    ┌──────────┬──────────┬──────────┬──────────┬──────────┐
    │ Header   │ Length   │ Command  │ Data     │ Checksum │
    │ 0xAA 0x55│ 2B (BE)  │ 1B       │ N bytes  │ CRC16    │
    │ 2 bytes  │          │          │          │ 2B (LE)  │
    └──────────┴──────────┴──────────┴──────────┴──────────┘

Supported commands:
  0x01 - Realtime data response
  0x02 - Device status response
  0x03 - Alarm notification
  0x04 - Configuration response
  0x10 - Start test command (request only)
  0x11 - Stop test command (request only)
  0x20 - Read realtime data (request only)
  0x21 - Read device status (request only)
"""

import struct
from datetime import datetime

from src.protocol.interfaces import IProtocolParser
from src.core.common.device_data import DeviceData


# Command constants
CMD_REALTIME_DATA = 0x01
CMD_STATUS = 0x02
CMD_ALARM = 0x03
CMD_CONFIG = 0x04
CMD_START_TEST = 0x10
CMD_STOP_TEST = 0x11
CMD_READ_REALTIME = 0x20
CMD_READ_STATUS = 0x21

# Frame header magic bytes
FRAME_HEADER = b'\xAA\x55'

# Frame minimum size: header(2) + length(2) + cmd(1) + checksum(2)
FRAME_MIN_SIZE = 7


class CustomTcpParser(IProtocolParser):
    """Binary frame protocol parser for proprietary TCP devices.

    Usage
    -----
    parser = CustomTcpParser()
    parser.initialize({
        "device_id": 1,
        "data_map": {
            "voltage":     {"offset": 0, "type": "float32", "scale": 0.1},
            "current":     {"offset": 4, "type": "float32", "scale": 0.01},
            "power":       {"offset": 8, "type": "int32"},
            "temperature": {"offset": 12, "type": "int16", "scale": 0.1},
        },
    })
    """

    _device_id: int = 0
    _data_map: dict = {}
    _status_map: dict = {}

    # ------------------------------------------------------------------
    # IProtocolParser interface
    # ------------------------------------------------------------------

    def protocol_name(self) -> str:
        return "custom_tcp"

    def initialize(self, config: dict) -> bool:
        self._device_id = config.get("device_id", 0)
        self._data_map = config.get("data_map", {})
        self._status_map = config.get("status_map", {
            "run_time":   {"offset": 0, "type": "uint32"},
            "error_code": {"offset": 4, "type": "uint16"},
            "status_byte":{"offset": 6, "type": "uint8"},
        })
        return True

    def parse(self, raw_data: bytes, output: DeviceData) -> bool:
        """Parse a complete custom frame and populate *output*.

        The raw_data should be a single complete frame.
        """
        if len(raw_data) < FRAME_MIN_SIZE:
            return False

        # Validate header
        if raw_data[:2] != FRAME_HEADER:
            output.communication_ok = False
            output.frame_error_count += 1
            return False

        # Validate checksum
        payload = raw_data[:-2]
        received_checksum = raw_data[-2:]
        calculated_checksum = self._crc16(payload)
        if received_checksum != calculated_checksum:
            output.communication_ok = False
            output.frame_error_count += 1
            return False

        # Parse length and command
        length = struct.unpack(">H", raw_data[2:4])[0]
        cmd = raw_data[4]
        data = raw_data[5:5 + length - 1]  # length includes cmd byte

        # Route to specific handler
        if cmd == CMD_REALTIME_DATA:
            self._parse_realtime_data(data, output)
        elif cmd == CMD_STATUS:
            self._parse_status(data, output)
        elif cmd == CMD_ALARM:
            self._parse_alarm(data, output)
        elif cmd == CMD_CONFIG:
            self._parse_config(data, output)
        else:
            output.communication_ok = False
            return False

        output.timestamp = datetime.now()
        output.communication_ok = True
        return True

    def build_request(self, cmd: str) -> bytes:
        """Build a request frame.

        Accepted *cmd* strings:

        * ``"read_realtime"`` — request realtime data
        * ``"read_status"``   — request device status
        * ``"start_test"``    — start test command
        * ``"stop_test"``     — stop test command
        """
        cmd_map = {
            "read_realtime": CMD_READ_REALTIME,
            "read_status":   CMD_READ_STATUS,
            "start_test":    CMD_START_TEST,
            "stop_test":     CMD_STOP_TEST,
        }
        cmd_byte = cmd_map.get(cmd)
        if cmd_byte is None:
            return b""

        # Build frame: header + length(2) + cmd(1) + data(0) + checksum(2)
        length = 1  # cmd byte only, no extra data
        frame = FRAME_HEADER + struct.pack(">HB", length, cmd_byte)
        checksum = self._crc16(frame)
        return frame + checksum

    # ------------------------------------------------------------------
    # Response parsers
    # ------------------------------------------------------------------

    def _parse_realtime_data(self, data: bytes, output: DeviceData):
        """Decode realtime measurement data using the data map."""
        for param_name, field_info in self._data_map.items():
            offset = field_info["offset"]
            dtype = field_info.get("type", "float32")
            scale = field_info.get("scale", 1.0)
            size = self._type_size(dtype)

            if offset + size > len(data):
                continue

            raw = data[offset:offset + size]
            value = self._unpack_value(raw, dtype)
            if value is not None:
                output.parameters[param_name] = value * scale

    def _parse_status(self, data: bytes, output: DeviceData):
        """Decode device status information."""
        for param_name, field_info in self._status_map.items():
            offset = field_info["offset"]
            dtype = field_info.get("type", "uint16")
            size = self._type_size(dtype)

            if offset + size > len(data):
                continue

            raw = data[offset:offset + size]
            value = self._unpack_value(raw, dtype)
            if value is not None:
                output.parameters[f"status_{param_name}"] = value

    def _parse_alarm(self, data: bytes, output: DeviceData):
        """Decode alarm notification.

        Layout: alarm_code(1B) + alarm_level(1B) + message_len(1B) + message(NB)
        """
        if len(data) < 3:
            return
        alarm_code = data[0]
        alarm_level = data[1]
        msg_len = data[2]
        message = data[3:3 + msg_len].decode("utf-8", errors="replace")

        output.parameters["alarm_code"] = alarm_code
        output.parameters["alarm_level"] = alarm_level
        output.parameters["alarm_message"] = message

    def _parse_config(self, data: bytes, output: DeviceData):
        """Decode configuration response data.

        Layout: param_count(2B) + entries...
        Each entry: param_id(1B) + value(4B float32)
        """
        if len(data) < 2:
            return
        count = struct.unpack(">H", data[:2])[0]
        offset = 2
        for i in range(count):
            if offset + 5 > len(data):
                break
            param_id = data[offset]
            value = struct.unpack(">f", data[offset + 1:offset + 5])[0]
            output.parameters[f"config_param_{param_id}"] = value
            offset += 5

    # ------------------------------------------------------------------
    # CRC-16 (CCITT-FALSE: x^16 + x^12 + x^5 + 1)
    # ------------------------------------------------------------------

    @staticmethod
    def _crc16(data: bytes) -> bytes:
        crc = 0xFFFF
        for byte in data:
            crc ^= byte << 8
            for _ in range(8):
                if crc & 0x8000:
                    crc = (crc << 1) ^ 0x1021
                else:
                    crc <<= 1
                crc &= 0xFFFF
        return struct.pack(">H", crc)

    # ------------------------------------------------------------------
    # Type helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _type_size(dtype: str) -> int:
        sizes = {
            "uint8": 1, "int8": 1,
            "uint16": 2, "int16": 2,
            "uint32": 4, "int32": 4,
            "float32": 4,
        }
        return sizes.get(dtype, 4)

    @staticmethod
    def _unpack_value(raw: bytes, dtype: str):
        try:
            if dtype == "uint8":
                return raw[0]
            if dtype == "int8":
                return struct.unpack("b", raw)[0]
            if dtype == "uint16":
                return struct.unpack(">H", raw)[0]
            if dtype == "int16":
                return struct.unpack(">h", raw)[0]
            if dtype == "uint32":
                return struct.unpack(">I", raw)[0]
            if dtype == "int32":
                return struct.unpack(">i", raw)[0]
            if dtype == "float32":
                return struct.unpack(">f", raw)[0]
        except (struct.error, IndexError):
            return None
        return None
