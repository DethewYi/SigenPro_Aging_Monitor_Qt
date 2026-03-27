"""CANopen protocol parser plugin for CAN bus devices.

Supports common CANopen communication objects:
  TPDO (Transmit Process Data Object) — periodic device data
  SDO (Service Data Object) — configuration read/write
  EMCY (Emergency) — alarm/notification
  NMT (Network Management) — node state control

COB-ID mapping (default):
  TPDO1: 0x180 + node_id
  TPDO2: 0x280 + node_id
  TPDO3: 0x380 + node_id
  TPDO4: 0x480 + node_id
  RPDO1: 0x200 + node_id
  SDO_Rx/Tx: 0x600 + node_id / 0x580 + node_id
  EMCY:  0x080 + node_id
  NMT:   0x000
"""

import struct
from datetime import datetime

from src.protocol.interfaces import IProtocolParser
from src.core.common.device_data import DeviceData


# CANopen COB-ID bases
COB_TPDO1 = 0x180
COB_TPDO2 = 0x280
COB_TPDO3 = 0x380
COB_TPDO4 = 0x480
COB_RPDO1 = 0x200
COB_SDO_TX = 0x580
COB_SDO_RX = 0x600
COB_EMCY = 0x080
COB_NMT = 0x000


class CanopenParser(IProtocolParser):
    """CANopen protocol parser with configurable TPDO mapping.

    Usage
    -----
    parser = CanopenParser()
    parser.initialize({
        "node_id": 1,
        "tpdo_map": {
            "voltage":     {"tpdo": 1, "offset": 0, "bits": 16, "scale": 0.01},
            "current":     {"tpdo": 1, "offset": 2, "bits": 16, "scale": 0.01},
            "temperature": {"tpdo": 2, "offset": 0, "bits": 8,  "scale": 1.0},
            "soc":         {"tpdo": 2, "offset": 1, "bits": 8,  "scale": 0.5},
            "status":      {"tpdo": 3, "offset": 0, "bits": 16},
        },
    })

    The parser receives CAN frames as (cob_id: int, data: bytes) tuples.
    Since CAN frames arrive via CanBridge as raw bytes, the first 4 bytes
    are interpreted as the COB-ID and the remaining bytes as the payload.
    """

    _node_id: int = 1
    _tpdo_map: dict = {}
    _sdo_expedited: dict = {}
    _pending_sdo: dict = {}

    # ------------------------------------------------------------------
    # IProtocolParser interface
    # ------------------------------------------------------------------

    def protocol_name(self) -> str:
        return "canopen"

    def initialize(self, config: dict) -> bool:
        self._node_id = config.get("node_id", 1)
        self._tpdo_map = config.get("tpdo_map", {})
        self._sdo_expedited = config.get("sdo_expedited", {})
        self._pending_sdo = {}
        return True

    def parse(self, raw_data: bytes, output: DeviceData) -> bool:
        """Parse a CAN frame.

        Expected raw_data layout from CanBridge::

            cob_id (4 bytes, big-endian) + CAN payload (up to 8 bytes)

        Alternatively, if raw_data starts with a valid COB-ID range
        within the first 2 bytes, it can also work with::

            cob_id (2 bytes) + CAN payload

        The parser auto-detects the format.
        """
        if len(raw_data) < 6:
            return False

        # Auto-detect COB-ID format
        if len(raw_data) >= 10:
            # 4-byte COB-ID + payload
            cob_id = struct.unpack(">I", raw_data[:4])[0]
            payload = raw_data[4:4 + 8]
        else:
            # 2-byte COB-ID + payload
            cob_id = struct.unpack(">H", raw_data[:2])[0]
            payload = raw_data[2:2 + 8]

        node_id = cob_id & 0x7F

        # Route by COB-ID
        if cob_id & 0x780 == COB_TPDO1:
            return self._parse_tpdo(cob_id, payload, output)
        elif cob_id == COB_EMCY + node_id:
            return self._parse_emcy(payload, output)
        elif cob_id == COB_SDO_TX + node_id:
            return self._parse_sdo_response(payload, output)
        elif cob_id == COB_NMT:
            return self._parse_nmt(payload, output)

        return False

    def build_request(self, cmd: str) -> bytes:
        """Build a CAN frame request.

        Accepted *cmd* strings:

        * ``"nmt:start"``   — NMT Start Remote Node
        * ``"nmt:stop"``    — NMT Stop Remote Node
        * ``"nmt:reset"``   — NMT Reset Node
        * ``"sdo_read:<index>:<subindex>"`` — SDO expedited read
        * ``"sdo_write:<index>:<subindex>:<value>"`` — SDO expedited write
        * ``"sync"``        — SYNC object
        """
        parts = cmd.split(":")

        if parts[0] == "nmt" and len(parts) == 2:
            return self._build_nmt(parts[1])

        if parts[0] == "sdo_read" and len(parts) == 3:
            return self._build_sdo_read(int(parts[1], 0), int(parts[2], 0))

        if parts[0] == "sdo_write" and len(parts) == 4:
            return self._build_sdo_write(
                int(parts[1], 0), int(parts[2], 0), parts[3]
            )

        if parts[0] == "sync":
            # SYNC frame: COB-ID 0x80, empty payload
            return struct.pack(">I", COB_NMT + 0x80)

        return b""

    # ------------------------------------------------------------------
    # TPDO parsing
    # ------------------------------------------------------------------

    def _parse_tpdo(self, cob_id: int, payload: bytes, output: DeviceData) -> bool:
        """Decode a TPDO frame into named parameters."""
        tpdo_num = (cob_id >> 8) - 0x100 + 1  # 0x180→1, 0x280→2, etc.

        for param_name, field_info in self._tpdo_map.items():
            if field_info["tpdo"] != tpdo_num:
                continue

            offset = field_info["offset"]
            bits = field_info.get("bits", 16)
            scale = field_info.get("scale", 1.0)
            signed = field_info.get("signed", False)

            byte_len = bits // 8
            if offset + byte_len > len(payload):
                continue

            raw = payload[offset:offset + byte_len]
            value = self._unpack_can_value(raw, bits, signed)
            if value is not None:
                output.parameters[param_name] = value * scale

        output.timestamp = datetime.now()
        output.communication_ok = True
        return True

    # ------------------------------------------------------------------
    # EMCY (Emergency) parsing
    # ------------------------------------------------------------------

    def _parse_emcy(self, payload: bytes, output: DeviceData) -> bool:
        """Parse emergency object.

        Layout: error_code(2B) + error_register(1B) + manufacturer_field(5B)
        """
        if len(payload) < 3:
            return False

        error_code = struct.unpack(">H", payload[:2])[0]
        error_reg = payload[2]

        output.parameters["emcy_code"] = error_code
        output.parameters["emcy_register"] = error_reg
        output.timestamp = datetime.now()
        output.communication_ok = True
        return True

    # ------------------------------------------------------------------
    # SDO response parsing
    # ------------------------------------------------------------------

    def _parse_sdo_response(self, payload: bytes, output: DeviceData) -> bool:
        """Parse SDO (Service Data Object) response.

        Expedited transfer: cmd(1B) + index(2B) + subindex(1B) + data(4B)
        """
        if len(payload) < 4:
            return False

        cmd = payload[0]
        index = struct.unpack(">HB", payload[1:4])[0]
        subindex = payload[3]

        sdo_cmd = cmd & 0xF0

        if sdo_cmd in (0x40, 0x60):
            # Expedited upload / download response
            if cmd & 0x02:
                # Data length specified
                data_len = 4 - ((cmd >> 2) & 0x03)
                data = payload[4:4 + data_len]
            else:
                data = payload[4:8]

            value = self._unpack_can_value(data, len(data) * 8, signed=False)
            if value is not None:
                key = f"sdo_{index:04X}_{subindex:02X}"
                output.parameters[key] = value

            output.timestamp = datetime.now()
            output.communication_ok = True
            return True

        if sdo_cmd == 0x80:
            # SDO abort
            abort_code = struct.unpack(">I", payload[4:8])[0] if len(payload) >= 8 else 0
            output.parameters["sdo_abort_code"] = abort_code
            output.communication_ok = False
            return False

        return False

    # ------------------------------------------------------------------
    # NMT parsing
    # ------------------------------------------------------------------

    def _parse_nmt(self, payload: bytes, output: DeviceData) -> bool:
        """Parse NMT message.

        Layout: cmd(1B) + node_id(1B), or cmd(1B) + 0x00 for broadcast.
        """
        if len(payload) < 2:
            return False

        nmt_cmd = payload[0]
        nmt_node = payload[1]

        output.parameters["nmt_command"] = nmt_cmd
        output.parameters["nmt_node"] = nmt_node
        output.timestamp = datetime.now()
        output.communication_ok = True
        return True

    # ------------------------------------------------------------------
    # Request builders
    # ------------------------------------------------------------------

    def _build_nmt(self, action: str) -> bytes:
        nmt_commands = {
            "start":  0x01,
            "stop":   0x02,
            "reset":  0x81,  # Reset Node
            "comm":   0x82,  # Reset Communication
        }
        cmd = nmt_commands.get(action, 0x01)
        # NMT frame: cob_id(4B) + cmd(1B) + node_id(1B)
        return struct.pack(">IBB", COB_NMT, cmd, self._node_id)

    def _build_sdo_read(self, index: int, subindex: int) -> bytes:
        """Build SDO expedited read request."""
        cob_id = COB_SDO_RX + self._node_id
        cmd = 0x40  # Initiate SDO upload
        payload = bytes([cmd]) + struct.pack(">HB", index, subindex) + bytes(4)
        return struct.pack(">I", cob_id) + payload

    def _build_sdo_write(self, index: int, subindex: int, value_str: str) -> bytes:
        """Build SDO expedited write request."""
        cob_id = COB_SDO_RX + self._node_id

        try:
            value = int(value_str, 0)
        except ValueError:
            try:
                value = int(float(value_str))
            except ValueError:
                return b""

        # Expedited transfer, 4 bytes data
        cmd = 0x23  # Initiate SDO download, expedited, 4 bytes
        payload = (
            bytes([cmd])
            + struct.pack(">HB", index, subindex)
            + struct.pack(">I", value & 0xFFFFFFFF)
        )
        return struct.pack(">I", cob_id) + payload

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _unpack_can_value(raw: bytes, bits: int, signed: bool):
        try:
            if bits == 8:
                return struct.unpack("b" if signed else "B", raw)[0]
            if bits == 16:
                return struct.unpack(">h" if signed else ">H", raw)[0]
            if bits == 32:
                return struct.unpack(">i" if signed else ">I", raw)[0]
        except struct.error:
            return None
        return None
