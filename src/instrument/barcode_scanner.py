"""Barcode scanner input handler.

Supports two modes of operation:

* **serial** -- Reads from a serial port (COM/tty).  Lines terminated by
  ``\\r\\n``, ``\\r``, or ``\\n`` are emitted as barcodes.
* **usb_hid** -- Keyboard-wedge mode.  Characters typed rapidly are
  buffered and emitted as a barcode when Enter is pressed or a
  timeout elapses.
"""

from PyQt6.QtCore import QObject, pyqtSignal, QTimer, QEvent
import logging

logger = logging.getLogger(__name__)


class BarcodeScanner(QObject):
    """Dual-mode barcode scanner input handler.

    Signals:
        barcode_scanned: Emitted with the decoded barcode string.
        error_occurred: Emitted with an error message string.
    """

    barcode_scanned = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    # Maximum time between keystrokes in HID mode before auto-emitting.
    HID_TIMEOUT_MS = 100

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mode = "serial"  # serial | usb_hid
        self._serial_port = None
        self._read_buffer = bytearray()
        self._hid_buffer = ""
        self._hid_timeout = QTimer(self)
        self._hid_timeout.setSingleShot(True)
        self._hid_timeout.timeout.connect(self._on_hid_timeout)

    # ------------------------------------------------------------------
    # Serial mode
    # ------------------------------------------------------------------

    def start_serial(
        self,
        port_name: str,
        baud_rate: int = 9600,
        data_bits: int = 8,
        stop_bits: int = 1,
        parity: int = 0,
    ):
        """Open a serial port for barcode input.

        Args:
            port_name: Serial port name (e.g. ``COM3``).
            baud_rate: Baud rate (default 9600).
            data_bits: Data bits (default 8).
            stop_bits: Stop bits (default 1).
            parity: Parity (0=None, 1=Even, 2=Odd, 3=Mark, 4=Space).
        """
        from PyQt6.QtSerialPort import QSerialPort

        self.stop()
        self._mode = "serial"
        self._serial_port = QSerialPort(self)
        self._serial_port.setPortName(port_name)
        self._serial_port.setBaudRate(baud_rate)
        self._serial_port.setDataBits(data_bits)
        self._serial_port.setStopBits(stop_bits)
        self._serial_port.setParity(parity)
        if self._serial_port.open(QSerialPort.OpenModeFlag.ReadOnly):
            self._serial_port.readyRead.connect(self._on_serial_ready_read)
            logger.info("Barcode scanner connected on %s", port_name)
        else:
            self.error_occurred.emit(
                f"Failed to open serial port {port_name}"
            )

    def stop_serial(self):
        """Close the serial port if open."""
        if self._serial_port and self._serial_port.isOpen():
            self._serial_port.readyRead.disconnect(self._on_serial_ready_read)
            self._serial_port.close()
        self._serial_port = None
        self._read_buffer.clear()

    # ------------------------------------------------------------------
    # USB HID (keyboard wedge) mode
    # ------------------------------------------------------------------

    def start_usb_hid(self):
        """Enable USB HID barcode scanner mode via global event filter."""
        from PyQt6.QtWidgets import QApplication

        self.stop()
        self._mode = "usb_hid"
        QApplication.instance().installEventFilter(self)
        logger.info("USB HID barcode scanner mode enabled")

    def stop_usb_hid(self):
        """Disable USB HID mode and remove the event filter."""
        from PyQt6.QtWidgets import QApplication

        if self._mode == "usb_hid":
            QApplication.instance().removeEventFilter(self)
        self._hid_buffer = ""
        self._hid_timeout.stop()

    # ------------------------------------------------------------------
    # Common
    # ------------------------------------------------------------------

    def stop(self):
        """Stop whichever mode is currently active."""
        self.stop_serial()
        self.stop_usb_hid()

    def is_running(self) -> bool:
        """Return True if the scanner is active in any mode."""
        if self._mode == "serial":
            return self._serial_port is not None and self._serial_port.isOpen()
        return self._mode == "usb_hid"

    # ------------------------------------------------------------------
    # Event filter (HID mode)
    # ------------------------------------------------------------------

    def eventFilter(self, watched, event):
        """Intercept key events in USB HID mode."""
        if self._mode != "usb_hid":
            return super().eventFilter(watched, event)

        if event.type() == QEvent.Type.KeyPress:
            key = event.key()
            text = event.text()
            # Enter / Return => emit accumulated buffer as barcode
            if key in (16777220, 16777221):
                if self._hid_buffer:
                    self._hid_timeout.stop()
                    barcode = self._hid_buffer
                    self._hid_buffer = ""
                    self.barcode_scanned.emit(barcode)
                return True
            # Printable character => accumulate
            elif text and text.isprintable():
                self._hid_buffer += text
                self._hid_timeout.start(self.HID_TIMEOUT_MS)
                return True

        return super().eventFilter(watched, event)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _on_serial_ready_read(self):
        """Read bytes from the serial port and split into lines."""
        data = self._serial_port.readAll().data()
        self._read_buffer.extend(data)
        while self._read_buffer:
            found = False
            for sep in (b'\r\n', b'\r', b'\n'):
                if sep in self._read_buffer:
                    idx = self._read_buffer.index(sep)
                    barcode = (
                        self._read_buffer[:idx]
                        .decode("utf-8", errors="ignore")
                        .strip()
                    )
                    self._read_buffer = self._read_buffer[idx + len(sep):]
                    if barcode:
                        self.barcode_scanned.emit(barcode)
                    found = True
                    break
            if not found:
                break

    def _on_hid_timeout(self):
        """Auto-emit the HID buffer when the inter-key timeout fires."""
        if self._hid_buffer:
            barcode = self._hid_buffer
            self._hid_buffer = ""
            self.barcode_scanned.emit(barcode)
