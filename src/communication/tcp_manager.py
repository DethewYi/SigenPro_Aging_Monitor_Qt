"""TCP connection management for device communication.

Provides per-device TCP connections with heartbeat monitoring,
automatic reconnection with exponential back-off, and signal-based
event notification.
"""

from PyQt6.QtCore import QObject, pyqtSignal, QTimer, QByteArray
from PyQt6.QtNetwork import QTcpSocket, QAbstractSocket
import logging

from ..core.common.types import DeviceStatus, DeviceConfig

logger = logging.getLogger(__name__)


class TcpDeviceConnection(QObject):
    """Manages a single TCP connection to a remote device.

    Features:
    * Heartbeat keep-alive with configurable interval and timeout.
    * Automatic reconnection with exponential back-off.
    * Intentional vs. unintentional disconnect detection.
    """

    data_received = pyqtSignal(int, bytes)            # device_id, raw_data
    connection_state_changed = pyqtSignal(int, object)  # device_id, DeviceStatus
    error_occurred = pyqtSignal(int, str)              # device_id, error_msg

    HEARTBEAT_INTERVAL_MS = 30000
    HEARTBEAT_TIMEOUT_MS = 10000
    MAX_RECONNECT_ATTEMPTS = 10
    INITIAL_RECONNECT_MS = 1000
    MAX_RECONNECT_MS = 60000

    def __init__(self, device_id, parent=None):
        super().__init__(parent)
        self.device_id = device_id
        self._socket = QTcpSocket(self)
        self._host = ""
        self._port = 0
        self._reconnect_attempts = 0
        self._reconnect_timer = QTimer(self)
        self._heartbeat_timer = QTimer(self)
        self._heartbeat_timeout_timer = QTimer(self)
        self._read_buffer = bytearray()
        self._intentional_disconnect = False

        self._socket.connected.connect(self._on_connected)
        self._socket.disconnected.connect(self._on_disconnected)
        self._socket.readyRead.connect(self._on_ready_read)
        self._socket.errorOccurred.connect(self._on_error)
        self._reconnect_timer.timeout.connect(self._on_reconnect)
        self._heartbeat_timer.timeout.connect(self._send_heartbeat)
        self._heartbeat_timeout_timer.timeout.connect(
            self._on_heartbeat_timeout
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def connect_to_host(self, host, port):
        """Initiate a TCP connection to *host*:*port*."""
        self._host = host
        self._port = port
        self._reconnect_attempts = 0
        self._intentional_disconnect = False
        self._socket.connectToHost(host, port)

    def disconnect_from_host(self):
        """Gracefully disconnect (no auto-reconnect)."""
        self._intentional_disconnect = True
        self._stop_timers()
        self._socket.disconnectFromHost()

    def send_data(self, data):
        """Send raw bytes to the device. Silently drops if not connected."""
        if self._socket.state() == QAbstractSocket.SocketState.ConnectedState:
            self._socket.write(QByteArray(data))

    def is_connected(self):
        """Return True if the socket is in ConnectedState."""
        return (
            self._socket.state()
            == QAbstractSocket.SocketState.ConnectedState
        )

    # ------------------------------------------------------------------
    # Internal slots
    # ------------------------------------------------------------------

    def _on_connected(self):
        self._reconnect_attempts = 0
        self._reconnect_timer.stop()
        self._heartbeat_timer.start(self.HEARTBEAT_INTERVAL_MS)
        self.connection_state_changed.emit(self.device_id, DeviceStatus.IDLE)
        logger.info(
            "Device %d connected to %s:%d",
            self.device_id,
            self._host,
            self._port,
        )

    def _on_disconnected(self):
        self._stop_timers()
        if not self._intentional_disconnect:
            self.connection_state_changed.emit(
                self.device_id, DeviceStatus.OFFLINE
            )
            self._start_reconnect()

    def _on_ready_read(self):
        data = self._socket.readAll().data()
        self._read_buffer.extend(data)
        # Emit the full buffer contents for protocol-level parsing.
        self.data_received.emit(self.device_id, bytes(self._read_buffer))
        self._read_buffer.clear()

    def _on_error(self, error):
        logger.error(
            "Device %d socket error: %s",
            self.device_id,
            self._socket.errorString(),
        )

    # ------------------------------------------------------------------
    # Heartbeat
    # ------------------------------------------------------------------

    def _send_heartbeat(self):
        if self.is_connected():
            self._socket.write(QByteArray(b'\xAA\x55'))
            self._heartbeat_timeout_timer.start(self.HEARTBEAT_TIMEOUT_MS)

    def _on_heartbeat_timeout(self):
        self._heartbeat_timeout_timer.stop()
        logger.warning(
            "Device %d heartbeat timeout, reconnecting...", self.device_id
        )
        self._socket.abort()
        self._start_reconnect()

    # ------------------------------------------------------------------
    # Reconnection with exponential back-off
    # ------------------------------------------------------------------

    def _start_reconnect(self):
        if self._reconnect_attempts >= self.MAX_RECONNECT_ATTEMPTS:
            logger.error(
                "Device %d max reconnect attempts (%d) reached",
                self.device_id,
                self.MAX_RECONNECT_ATTEMPTS,
            )
            return
        interval = min(
            self.INITIAL_RECONNECT_MS * (2 ** self._reconnect_attempts),
            self.MAX_RECONNECT_MS,
        )
        self._reconnect_attempts += 1
        logger.info(
            "Device %d will reconnect in %d ms (attempt %d)",
            self.device_id,
            interval,
            self._reconnect_attempts,
        )
        self._reconnect_timer.start(interval)

    def _on_reconnect(self):
        self._reconnect_timer.stop()
        self._socket.connectToHost(self._host, self._port)

    def _stop_timers(self):
        self._heartbeat_timer.stop()
        self._heartbeat_timeout_timer.stop()
        self._reconnect_timer.stop()


class TcpConnectionManager(QObject):
    """Aggregates multiple :class:`TcpDeviceConnection` instances.

    Provides a single point to add/remove devices and forwards
    per-connection signals to unified manager-level signals.
    """

    device_data_received = pyqtSignal(int, bytes)
    device_status_changed = pyqtSignal(int, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._connections: dict[int, TcpDeviceConnection] = {}
        self._configs: dict[int, DeviceConfig] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_device(self, config: DeviceConfig):
        """Create a connection for *config* and start connecting."""
        device_id = config.device_id
        conn = TcpDeviceConnection(device_id, self)
        conn.data_received.connect(self._on_data_received)
        conn.connection_state_changed.connect(self._on_status_changed)
        conn.error_occurred.connect(self._on_error)
        self._connections[device_id] = conn
        self._configs[device_id] = config
        conn.connect_to_host(config.ip_address, config.port)

    def remove_device(self, device_id: int):
        """Disconnect and clean up the connection for *device_id*."""
        if device_id in self._connections:
            conn = self._connections[device_id]
            conn.disconnect_from_host()
            conn.deleteLater()
            del self._connections[device_id]
            self._configs.pop(device_id, None)

    def send_command(self, device_id: int, data: bytes):
        """Send raw bytes to a specific device."""
        if device_id in self._connections:
            self._connections[device_id].send_data(data)

    def is_device_connected(self, device_id: int) -> bool:
        """Check whether a device is currently connected."""
        return (
            device_id in self._connections
            and self._connections[device_id].is_connected()
        )

    # ------------------------------------------------------------------
    # Internal forwarding
    # ------------------------------------------------------------------

    def _on_data_received(self, device_id, data):
        self.device_data_received.emit(device_id, data)

    def _on_status_changed(self, device_id, status):
        self.device_status_changed.emit(device_id, status)

    def _on_error(self, device_id, msg):
        logger.error("Device %d error: %s", device_id, msg)
