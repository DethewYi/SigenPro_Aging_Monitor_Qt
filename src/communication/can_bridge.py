"""CAN-to-Ethernet bridge via TCP.

Connects to a CAN/Ethernet converter device and parses incoming
CAN frames into per-device payloads.  Frame format (binary)::

    device_id (2 bytes, big-endian)
    length    (1 byte)
    data      (N bytes)
    CRLF      (2 bytes, 0x0D 0x0A)
"""

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtNetwork import QTcpSocket, QAbstractSocket
import struct
import logging

logger = logging.getLogger(__name__)


class CanBridge(QObject):
    """TCP client for a CAN/Ethernet converter box.

    The converter multiplexes multiple CAN devices over a single
    TCP connection.  Each inbound frame is tagged with a 2-byte
    *device_id* so that the bridge can demultiplex them.
    """

    can_frame_received = pyqtSignal(int, bytes)    # device_id, frame_data
    connection_state_changed = pyqtSignal(object)   # DeviceStatus or None

    def __init__(self, parent=None):
        super().__init__(parent)
        self._socket = QTcpSocket(self)
        self._buffer = bytearray()

        self._socket.connected.connect(self._on_connected)
        self._socket.disconnected.connect(self._on_disconnected)
        self._socket.readyRead.connect(self._on_ready_read)
        self._socket.errorOccurred.connect(self._on_error)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def connect_to_converter(self, host: str, port: int):
        """Open a TCP connection to the CAN converter at *host*:*port*."""
        self._buffer.clear()
        self._socket.connectToHost(host, port)

    def disconnect_converter(self):
        """Close the TCP connection to the converter."""
        self._socket.disconnectFromHost()

    def is_connected(self) -> bool:
        """Return True if the socket is connected."""
        return (
            self._socket.state()
            == QAbstractSocket.SocketState.ConnectedState
        )

    # ------------------------------------------------------------------
    # Internal slots
    # ------------------------------------------------------------------

    def _on_connected(self):
        from ..core.common.types import DeviceStatus
        self.connection_state_changed.emit(DeviceStatus.IDLE)
        logger.info("CAN bridge connected")

    def _on_disconnected(self):
        from ..core.common.types import DeviceStatus
        self.connection_state_changed.emit(DeviceStatus.OFFLINE)
        logger.info("CAN bridge disconnected")

    def _on_error(self, error):
        logger.error(
            "CAN bridge socket error: %s", self._socket.errorString()
        )

    def _on_ready_read(self):
        data = self._socket.readAll().data()
        self._buffer.extend(data)
        # Frame format: device_id(2B BE) + length(1B) + data(NB) + CRLF
        while len(self._buffer) >= 5:
            device_id = struct.unpack('>H', self._buffer[0:2])[0]
            frame_len = self._buffer[2]
            total_len = 3 + frame_len + 2  # header + payload + CRLF
            if len(self._buffer) < total_len:
                break  # incomplete frame, wait for more data
            frame_data = bytes(self._buffer[3:3 + frame_len])
            self.can_frame_received.emit(device_id, frame_data)
            self._buffer = self._buffer[total_len:]
