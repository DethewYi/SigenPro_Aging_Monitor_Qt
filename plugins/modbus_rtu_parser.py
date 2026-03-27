"""Modbus RTU / Modbus TCP protocol parser plugin.

Supports standard Modbus function codes:
  03 - Read Holding Registers
  04 - Read Input Registers
  06 - Write Single Register
  10 (0x10) - Write Multiple Registers

Frame layout (RTU):
  [slave_addr(1B)] [func_code(1B)] [data...] [CRC16(2B LE)]

Frame layout (TCP):
  [MBAP header 7B] [func_code(1B)] [data...]
  MBAP = transaction_id(2B) + protocol_id(2B) + length(2B) + unit_id(1B)
"""

import struct
from datetime import datetime

from src.protocol.interfaces import IProtocolParser
from src.core.common.device_data import DeviceData


class ModbusRtuParser(IProtocolParser):
    """Modbus RTU/TCP protocol parser with register mapping.

    Usage
    -----
    parser = ModbusRtuParser()
    parser.initialize({
        "mode": "rtu",                          # "rtu" or "tcp"
        "slave_address": 1,                      # for RTU mode
        "register_map": {
            "voltage":       {"func": 4, "addr": 0x0000, "type": "float32", "scale": 0.1},
            "current":       {"func": 4, "addr": 0x0002, "type": "float32", "scale": 0.01},
            "power":         {"func": 4, "addr": 0x0004, "type": "uint32"},
            "temperature":   {"func": 4, "addr": 0x0008, "type": "int16",  "scale": 0.1},
            "soc":           {"func": 3, "addr": 0x0010, "type": "uint16", "scale": 0.01},
            "status":        {"func": 3, "addr": 0x0020, "type": "uint16"},
            "alarm_code":    {"func": 3, "addr": 0x0022, "type": "uint16"},
        },
    })
    """

    # ---- Configurable defaults ----
    _mode: str = "rtu"
    _slave_address: int = 1
    _register_map: dict = {}

    # ------------------------------------------------------------------
    # IProtocolParser interface
    # ------------------------------------------------------------------

    def protocol_name(self) -> str:
        return "modbus_rtu"

    def initialize(self, config: dict) -> bool:
        self._mode = config.get("mode", "rtu").lower()
        self._slave_address = config.get("slave_address", 1)
        self._register_map = config.get("register_map", {})
        return True

    def parse(self, raw_data: bytes, output: DeviceData) -> bool:
        """Parse a Modbus response frame and fill *output*.

        Returns True on success, False on frame error.
        """
        if self._mode == "rtu":
            return self._parse_rtu(raw_data, output)
        else:
            return self._parse_tcp(raw_data, output)

    def build_request(self, cmd: str) -> bytes:
        """Build a Modbus request frame.

        Accepted *cmd* strings:

        * ``"read:<param>"``  — read registers for the named parameter
        * ``"read_all"``      — batch-read all mapped registers
        * ``"write:<param>:<value>"`` — write a single register
        """
        if cmd == "read_all":
            return self._build_batch_read()

        parts = cmd.split(":", 2)
        action = parts[0]

        if action == "read" and len(parts) == 2:
            return self._build_read(parts[1])
        if action == "write" and len(parts) == 3:
            return self._build_write(parts[1], parts[2])

        return b""

    # ------------------------------------------------------------------
    # RTU parsing
    # ------------------------------------------------------------------

    def _parse_rtu(self, data: bytes, output: DeviceData) -> bool:
        if len(data) < 5:
            return False

        # Validate CRC
        if not self._check_crc(data):
            output.communication_ok = False
            output.frame_error_count += 1
            return False

        slave_addr = data[0]
        func_code = data[1]
        payload = data[2:-2]

        if slave_addr != self._slave_address:
            return False

        # Check Modbus exception
        if func_code & 0x80:
            output.parameters["modbus_exception"] = payload[0]
            output.communication_ok = False
            return False

        return self._parse_response_data(func_code, payload, output)

    # ------------------------------------------------------------------
    # TCP parsing
    # ------------------------------------------------------------------

    def _parse_tcp(self, data: bytes, output: DeviceData) -> bool:
        """Parse Modbus TCP (MBAP + PDU)."""
        if len(data) < 8:
            return False

        _trans_id, proto_id, length, unit_id = struct.unpack(">HHHB", data[:7])
        if proto_id != 0:
            return False
        if unit_id != self._slave_address:
            return False

        func_code = data[7]
        payload = data[8:]

        if func_code & 0x80:
            output.parameters["modbus_exception"] = payload[0] if payload else 0
            output.communication_ok = False
            return False

        return self._parse_response_data(func_code, payload, output)

    # ------------------------------------------------------------------
    # Response data extraction
    # ------------------------------------------------------------------

    def _parse_response_data(
        self, func_code: int, payload: bytes, output: DeviceData
    ) -> bool:
        """Interpret the function-code-specific payload."""
        if func_code in (0x03, 0x04) and len(payload) >= 1:
            byte_count = payload[0]
            register_data = payload[1:1 + byte_count]
            self._decode_registers(register_data, output)
            output.timestamp = datetime.now()
            output.communication_ok = True
            return True

        if func_code == 0x06 and len(payload) >= 4:
            addr = struct.unpack(">H", payload[:2])[0]
            val = struct.unpack(">H", payload[2:4])[0]
            output.parameters[f"register_{addr:04X}"] = val
            output.timestamp = datetime.now()
            return True

        if func_code == 0x10 and len(payload) >= 4:
            addr = struct.unpack(">H", payload[:2])[0]
            count = struct.unpack(">H", payload[2:4])[0]
            output.parameters["write_ack"] = (addr, count)
            output.timestamp = datetime.now()
            return True

        return False

    def _decode_registers(self, data: bytes, output: DeviceData):
        """Decode register bytes into named parameters using the register map.

        Iterates over the map in definition order; each entry consumes
        the appropriate number of bytes from *data*.
        """
        offset = 0
        for param_name, reg_info in self._register_map.items():
            dtype = reg_info.get("type", "uint16")
            scale = reg_info.get("scale", 1.0)
            size = self._type_size(dtype)

            if offset + size > len(data):
                break

            raw = data[offset:offset + size]
            value = self._unpack_value(raw, dtype)
            if value is not None:
                output.parameters[param_name] = value * scale
            offset += size

    # ------------------------------------------------------------------
    # Request builders
    # ------------------------------------------------------------------

    def _build_batch_read(self) -> bytes:
        """Build optimised batch read request.

        Groups consecutive registers with the same function code into
        a single read request.  Falls back to individual reads when
        registers are scattered.
        """
        if not self._register_map:
            return self._build_read_frame(0x04, 0, 1)

        # Group by function code
        groups: dict[int, list] = {}
        for name, info in self._register_map.items():
            func = info.get("func", 0x04)
            addr = info["addr"]
            size = self._type_size(info.get("type", "uint16"))
            groups.setdefault(func, []).append((addr, size, name))

        requests = []
        for func, entries in groups.items():
            # Sort by address
            entries.sort(key=lambda e: e[0])
            # Merge consecutive ranges
            start_addr = entries[0][0]
            end_addr = entries[0][0] + entries[0][1] // 2 - 1
            reg_count = entries[0][1] // 2

            for addr, size, name in entries[1:]:
                # Account for gaps between registers
                reg_count_for_param = size // 2
                # If gap is small (<4 registers), read through; otherwise split
                if addr <= end_addr + 4:
                    new_end = addr + reg_count_for_param - 1
                    reg_count = new_end - start_addr + 1
                    end_addr = new_end
                else:
                    requests.append(self._build_read_frame(func, start_addr, reg_count))
                    start_addr = addr
                    end_addr = addr + reg_count_for_param - 1
                    reg_count = reg_count_for_param

            requests.append(self._build_read_frame(func, start_addr, reg_count))

        return b"".join(requests)

    def _build_read(self, param_name: str) -> bytes:
        """Build a read request for a single named parameter."""
        info = self._register_map.get(param_name)
        if not info:
            return b""
        func = info.get("func", 0x04)
        addr = info["addr"]
        count = self._type_size(info.get("type", "uint16")) // 2
        return self._build_read_frame(func, addr, count)

    def _build_write(self, param_name: str, value_str: str) -> bytes:
        """Build a write single register request."""
        info = self._register_map.get(param_name)
        if not info:
            return b""

        try:
            value = float(value_str)
        except ValueError:
            try:
                value = int(value_str, 0)
            except ValueError:
                return b""

        scale = info.get("scale", 1.0)
        raw_value = int(value / scale)
        addr = info["addr"]

        pdu = struct.pack(">BHB", 0x06, addr, raw_value & 0xFFFF)
        if self._mode == "rtu":
            crc = self._crc16(pdu)
            return struct.pack("B", self._slave_address) + pdu + crc
        else:
            length = 2 + len(pdu)
            mbap = struct.pack(">HHHB", 0, 0, length, self._slave_address)
            return mbap + pdu

    def _build_read_frame(self, func_code: int, start_addr: int, reg_count: int) -> bytes:
        pdu = struct.pack(">BHH", func_code, start_addr, reg_count)
        if self._mode == "rtu":
            crc = self._crc16(pdu)
            return struct.pack("B", self._slave_address) + pdu + crc
        else:
            length = 2 + len(pdu)
            mbap = struct.pack(">HHHB", 0, 0, length, self._slave_address)
            return mbap + pdu

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

    @staticmethod
    def _check_crc(data: bytes) -> bool:
        if len(data) < 3:
            return False
        payload = data[:-2]
        received_crc = data[-2:]
        return ModbusRtuParser._crc16(payload) == received_crc

    # ------------------------------------------------------------------
    # Type helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _type_size(dtype: str) -> int:
        """Return byte size for a register data type."""
        sizes = {
            "int16": 2, "uint16": 2,
            "int32": 4, "uint32": 4,
            "float32": 4,
        }
        return sizes.get(dtype, 2)

    @staticmethod
    def _unpack_value(raw: bytes, dtype: str):
        """Unpack *raw* bytes according to *dtype* (big-endian)."""
        try:
            if dtype == "int16":
                return struct.unpack(">h", raw)[0]
            if dtype == "uint16":
                return struct.unpack(">H", raw)[0]
            if dtype == "int32":
                return struct.unpack(">i", raw)[0]
            if dtype == "uint32":
                return struct.unpack(">I", raw)[0]
            if dtype == "float32":
                return struct.unpack(">f", raw)[0]
        except struct.error:
            return None
        return None
