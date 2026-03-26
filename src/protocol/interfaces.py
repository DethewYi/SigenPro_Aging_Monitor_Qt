from abc import ABC, abstractmethod

from ..core.common.device_data import DeviceData
from ..core.common.types import DeviceConfig


class IProtocolParser(ABC):
    """Abstract base class for communication protocol parsers."""

    @abstractmethod
    def parse(self, raw_data: bytes, output: DeviceData) -> bool:
        """Parse raw byte data and populate the DeviceData output.

        Args:
            raw_data: Raw bytes received from the device.
            output: DeviceData instance to populate with parsed values.

        Returns:
            True if parsing succeeded, False otherwise.
        """
        ...

    @abstractmethod
    def build_request(self, cmd: str) -> bytes:
        """Build a request byte frame for a given command.

        Args:
            cmd: Command identifier string.

        Returns:
            Bytes to send to the device.
        """
        ...

    @abstractmethod
    def protocol_name(self) -> str:
        """Return the unique name of this protocol."""
        ...

    def initialize(self, config: dict) -> bool:
        """Optional initialization with configuration. Override if needed.

        Args:
            config: Protocol-specific configuration dictionary.

        Returns:
            True if initialization succeeded.
        """
        return True


class IInstrumentController(ABC):
    """Abstract base class for programmable power supply / contactor controllers."""

    @abstractmethod
    def connect(self, config: DeviceConfig) -> bool:
        """Establish connection to the instrument.

        Args:
            config: Device configuration including connection parameters.

        Returns:
            True if connection succeeded.
        """
        ...

    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from the instrument."""
        ...

    @abstractmethod
    def is_connected(self) -> bool:
        """Check whether the instrument is currently connected.

        Returns:
            True if connected.
        """
        ...

    @abstractmethod
    def power_on(self, channel: int) -> bool:
        """Turn on power for the specified channel.

        Args:
            channel: Channel number (1-based).

        Returns:
            True if the command succeeded.
        """
        ...

    @abstractmethod
    def power_off(self, channel: int) -> bool:
        """Turn off power for the specified channel.

        Args:
            channel: Channel number (1-based).

        Returns:
            True if the command succeeded.
        """
        ...

    @abstractmethod
    def set_voltage(self, channel: int, voltage: float) -> bool:
        """Set the output voltage for the specified channel.

        Args:
            channel: Channel number (1-based).
            voltage: Voltage in volts.

        Returns:
            True if the command succeeded.
        """
        ...

    @abstractmethod
    def set_current(self, channel: int, current: float) -> bool:
        """Set the output current for the specified channel.

        Args:
            channel: Channel number (1-based).
            current: Current in amperes.

        Returns:
            True if the command succeeded.
        """
        ...

    @abstractmethod
    def read_status(self, channel: int) -> dict:
        """Read the current status of the specified channel.

        Args:
            channel: Channel number (1-based).

        Returns:
            Dictionary with status information (e.g., output_on, voltage, current).
        """
        ...

    @abstractmethod
    def protocol_name(self) -> str:
        """Return the unique name of this controller protocol."""
        ...
