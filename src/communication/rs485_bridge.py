"""Dual-mode RS-485 bridge (TCP-to-serial-server or local serial port).

Supports two transport modes:

* **network** -- TCP connection to an RS-485-to-Ethernet serial server.
* **serial**  -- Direct local serial port (COM/ttyUSB/ttyACM, etc.).

Inbound data is split on CRLF delimiters and each line is emitted
via the :pyqtSignal:`data_received` signal.
"""

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtNetwork import QTcpSocket, QAbstractSocket
import logging

logger = logging.getLogger(__name__)


class Rs485Bridge(QObject):
    """Dual-mode RS-485 communication bridge.

    Use :meth:`connect_network` for a TCP serial-server, or
    :meth:`connect_serial` for a local COM/tty port.
    """

    data_received = pyqtSignal(bytes)              # complete line (no CRLF)
    connection_state_changed = pyqtSignal(object)   # DeviceStatus or None

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mode = "network"
        self._tcp_socket: QTcpSocket | None = None
        self._serial_port = None
        self._buffer = bytearray()

    # ------------------------------------------------------------------
    # Network mode (TCP serial server)
    # ------------------------------------------------------------------

    def connect_network(self, host: str, port: int):
        """Connect to an RS-485 serial server over TCP."""
        self.disconnect_all()
        self._mode = "network"
        self._tcp_socket = QTcpSocket(self)
        self._tcp_socket.readyRead.connect(self._on_tcp_ready_read)
        self._tcp_socket.connected.connect(self._emit_connected)
        self._tcp_socket.disconnected.connect(self._emit_disconnected)
        self._tcp_socket.errorOccurred.connect(self._on_tcp_error)
        self._tcp_socket.connectToHost(host, port)

    # ------------------------------------------------------------------
    # Serial mode (local COM/tty port)
    # ------------------------------------------------------------------

    def connect_serial(
        self,
        port_name: str,
        baud_rate: int = 9600,
        data_bits: int = 8,
        stop_bits: int = 1,
        parity: int = 0,
    ):
        """Open a local serial port for RS-485 communication.

        Args:
            port_name: Serial port name (e.g. ``COM3`` or ``/dev/ttyUSB0``).
            baud_rate: Baud rate (default 9600).
            data_bits: Data bits (default 8).
            stop_bits: Stop bits (default 1).
            parity: Parity (0=None, 1=Even, 2=Odd, 3=Mark, 4=Space).
        """
        from PyQt6.QtSerialPort import QSerialPort

        self.disconnect_all()
        self._mode = "serial"
        self._serial_port = QSerialPort(self)
        self._serial_port.setPortName(port_name)
        self._serial_port.setBaudRate(baud_rate)
        self._serial_port.setDataBits(data_bits)
        self._serial_port.setStopBits(stop_bits)
        self._serial_port.setParity(parity)
        self._serial_port.readyRead.connect(self._on_serial_ready_read)
        if not self._serial_port.open(QSerialPort.OpenModeFlag.ReadOnly):
            logger.error("Failed to open serial port %s", port_name)
            self._emit_disconnected()
        else:
            logger.info("RS-485 serial opened on %s @ %d", port_name, baud_rate)
            self._emit_connected()

    # ------------------------------------------------------------------
    # Common
    # ------------------------------------------------------------------

    def disconnect_all(self):
        """Close any open connection and clear buffers."""
        if self._tcp_socket:
            self._tcp_socket.disconnectFromHost()
            self._tcp_socket.deleteLater()
            self._tcp_socket = None
        if self._serial_port and self._serial_port.isOpen():
            self._serial_port.close()
            self._serial_port.deleteLater()
            self._serial_port = None
        self._buffer.clear()

    def send_data(self, data: bytes):
        """Send raw bytes to the RS-485 bus."""
        if self._mode == "network" and self._tcp_socket:
            self._tcp_socket.write(data)
        elif self._mode == "serial" and self._serial_port:
            self._serial_port.write(data)

    def is_connected(self) -> bool:
        """Return True if the current transport is open/connected."""
        if self._mode == "network" and self._tcp_socket:
            return (
                self._tcp_socket.state()
                == QAbstractSocket.SocketState.ConnectedState
            )
        if self._mode == "serial" and self._serial_port:
            return self._serial_port.isOpen()
        return False

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _emit_connected(self):
        from ..core.common.types import DeviceStatus
        self.connection_state_changed.emit(DeviceStatus.IDLE)

    def _emit_disconnected(self):
        from ..core.common.types import DeviceStatus
        self.connection_state_changed.emit(DeviceStatus.OFFLINE)

    def _on_tcp_error(self, error):
        logger.error(
            "RS-485 TCP error: %s", self._tcp_socket.errorString()
        )

    def _on_tcp_ready_read(self):
        data = self._tcp_socket.readAll().data()
        self._process_data(data)

    def _on_serial_ready_read(self):
        data = self._serial_port.readAll().data()
        self._process_data(data)

    def _process_data(self, data: bytes):
        """Split incoming data on CRLF boundaries and emit lines."""
        self._buffer.extend(data)
        while b'\r\n' in self._buffer:
            idx = self._buffer.index(b'\r\n')
            frame = bytes(self._buffer[:idx])
            self._buffer = self._buffer[idx + 2:]
            if frame:
                self.data_received.emit(frame)
