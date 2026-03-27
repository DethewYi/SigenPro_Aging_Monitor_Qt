"""Device data simulator for MVP demo.

Generates realistic DeviceData with per-product-type parameter ranges
and Gaussian noise.  Publishes directly to DataBus.device_data_received,
bypassing the TCP / parser layer.
"""

import random
import math
from datetime import datetime

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from ..core.common.device_data import DeviceData
from ..core.common.types import DeviceStatus
from ..core.data_bus import DataBus

import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Product profiles — realistic parameter ranges for energy storage devices
# ---------------------------------------------------------------------------

_PRODUCT_PROFILES = {
    "PCS": {
        "name": "PCS-{id:03d}",
        "model": "SPCS-50K",
        "params": {
            "voltage": {"base": 380.0, "noise": 5.0, "unit": "V"},
            "current": {"base": 20.0, "noise": 3.0, "unit": "A"},
            "power": {"base": 7500.0, "noise": 500.0, "unit": "W"},
            "temperature": {"base": 45.0, "noise": 8.0, "unit": "C"},
            "frequency": {"base": 50.0, "noise": 0.2, "unit": "Hz"},
        },
    },
    "PACK": {
        "name": "PACK-{id:03d}",
        "model": "SPACK-100Ah",
        "params": {
            "voltage": {"base": 48.0, "noise": 2.0, "unit": "V"},
            "current": {"base": 50.0, "noise": 5.0, "unit": "A"},
            "soc": {"base": 80.0, "noise": 15.0, "unit": "%"},
            "temperature": {"base": 35.0, "noise": 5.0, "unit": "C"},
        },
    },
    "DCDC": {
        "name": "DCDC-{id:03d}",
        "model": "SDC-3K",
        "params": {
            "voltage_in": {"base": 380.0, "noise": 10.0, "unit": "V"},
            "voltage_out": {"base": 48.0, "noise": 1.0, "unit": "V"},
            "current": {"base": 10.0, "noise": 2.0, "unit": "A"},
            "power": {"base": 3800.0, "noise": 300.0, "unit": "W"},
            "efficiency": {"base": 96.0, "noise": 1.0, "unit": "%"},
            "temperature": {"base": 42.0, "noise": 6.0, "unit": "C"},
        },
    },
    "BMU": {
        "name": "BMU-{id:03d}",
        "model": "SBMU-16S",
        "params": {
            "total_voltage": {"base": 52.8, "noise": 0.5, "unit": "V"},
            "current": {"base": 0.0, "noise": 1.0, "unit": "A"},
            "soc": {"base": 90.0, "noise": 10.0, "unit": "%"},
            "max_cell_voltage": {"base": 3.55, "noise": 0.08, "unit": "V"},
            "min_cell_voltage": {"base": 3.35, "noise": 0.06, "unit": "V"},
            "temperature": {"base": 30.0, "noise": 4.0, "unit": "C"},
        },
    },
}

# Default simulated devices
_DEFAULT_DEVICES = [
    {"device_id": 1, "type": "PCS",   "status": DeviceStatus.TESTING},
    {"device_id": 2, "type": "PCS",   "status": DeviceStatus.TESTING},
    {"device_id": 3, "type": "PACK",  "status": DeviceStatus.TESTING},
    {"device_id": 4, "type": "PACK",  "status": DeviceStatus.IDLE},
    {"device_id": 5, "type": "DCDC",  "status": DeviceStatus.TESTING},
    {"device_id": 6, "type": "DCDC",  "status": DeviceStatus.TESTING},
    {"device_id": 7, "type": "BMU",   "status": DeviceStatus.TESTING},
    {"device_id": 8, "type": "BMU",   "status": DeviceStatus.IDLE},
]


class Simulator(QObject):
    """Generates synthetic device data for demo / testing purposes.

    Usage::

        sim = Simulator()
        sim.start_sim()       # starts emitting DataBus signals
        sim.stop_sim()        # stops
        sim.set_running(device_id, True/False)
    """

    simulation_changed = pyqtSignal(bool)  # running state

    def __init__(self, parent=None):
        super().__init__(parent)
        self._devices: dict[int, dict] = {}
        self._running = False
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._tick_count = 0
        self._offline_devices: set[int] = set()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start_sim(self, devices: list[dict] | None = None):
        """Start the simulation with the given device configs.

        Args:
            devices: List of dicts with keys: device_id, type, status.
                     Defaults to _DEFAULT_DEVICES.
        """
        self._init_devices(devices or _DEFAULT_DEVICES)
        self._running = True
        self._tick_count = 0
        self._timer.start(1000)
        self.simulation_changed.emit(True)

        # Emit initial device status for all devices so cards are created
        bus = DataBus.instance()
        for dev in self._devices.values():
            bus.publish_device_status(
                dev["device_id"],
                DeviceStatus.IDLE if dev.get("offline") else dev["status"],
            )
        logger.info("Simulation started with %d devices", len(self._devices))

    def stop_sim(self):
        """Stop the simulation."""
        self._timer.stop()
        self._running = False
        self.simulation_changed.emit(False)
        logger.info("Simulation stopped")

    @property
    def is_running(self) -> bool:
        return self._running

    def set_running(self, device_id: int, running: bool):
        """Set a simulated device's test running state."""
        dev = self._devices.get(device_id)
        if dev:
            dev["offline"] = False
            dev["status"] = DeviceStatus.TESTING if running else DeviceStatus.IDLE
            DataBus.instance().publish_device_status(
                device_id, dev["status"]
            )

    def set_all_running(self, running: bool):
        """Set all devices to running or idle."""
        for device_id in self._devices:
            self.set_running(device_id, running)

    def _init_devices(self, configs: list[dict]):
        """Build internal device state from config list."""
        self._devices.clear()
        self._offline_devices.clear()
        for cfg in configs:
            profile = _PRODUCT_PROFILES.get(cfg["type"], _PRODUCT_PROFILES["PACK"])
            dev = {
                "device_id": cfg["device_id"],
                "type": cfg["type"],
                "status": cfg.get("status", DeviceStatus.IDLE),
                "name": profile["name"].format(id=cfg["device_id"]),
                "model": profile["model"],
                "profile": profile,
                # Per-parameter current value (will drift slowly)
                "current_values": {
                    p: profile["params"][p]["base"]
                    for p in profile["params"]
                },
                "offline": False,
            }
            self._devices[cfg["device_id"]] = dev

    # ------------------------------------------------------------------
    # Timer tick — generate data for every device
    # ------------------------------------------------------------------

    def _tick(self):
        self._tick_count += 1
        bus = DataBus.instance()
        now = datetime.now()

        for dev in self._devices.values():
            device_id = dev["device_id"]

            # --- Simulate occasional offline / online events ---
            if dev["offline"]:
                # Reconnect after 5-15 ticks
                if random.random() < 0.1:
                    dev["offline"] = False
                    dev["status"] = DeviceStatus.IDLE
                    bus.publish_device_status(device_id, dev["status"])
                continue

            if random.random() < 0.003:  # ~0.3% chance per tick
                dev["offline"] = True
                dev["status"] = DeviceStatus.OFFLINE
                bus.publish_device_status(device_id, DeviceStatus.OFFLINE)
                continue

            # --- Only TESTING devices generate data ---
            if dev["status"] != DeviceStatus.TESTING:
                continue

            # --- Generate parameters with drift + noise ---
            params = {}
            profile = dev["profile"]
            alarm_triggered = False

            for param_name, spec in profile["params"].items():
                base = spec["base"]
                noise = spec["noise"]

                # Slow random walk (drift)
                current = dev["current_values"][param_name]
                drift = random.gauss(0, noise * 0.05)
                current += drift

                # Occasional spike (for alarm demonstration)
                spike = 0.0
                if self._tick_count > 5 and random.random() < 0.008:
                    # Spike to ~2x noise away from base
                    direction = random.choice([-1, 1])
                    spike = direction * noise * random.uniform(1.5, 2.5)
                    alarm_triggered = True

                # Keep within reasonable bounds
                min_val = max(0, base - noise * 4)
                max_val = base + noise * 4
                current = max(min_val, min(max_val, current + spike))

                # Add measurement noise
                measured = current + random.gauss(0, noise * 0.1)

                dev["current_values"][param_name] = current
                params[param_name] = round(measured, 2)

            # --- Build and emit DeviceData ---
            data = DeviceData(
                device_id=device_id,
                timestamp=now,
                parameters=params,
                communication_ok=True,
            )
            bus.publish_device_data(data)

            # --- Occasionally flip device status between TESTING and IDLE ---
            if random.random() < 0.005:
                new_status = DeviceStatus.IDLE
                dev["status"] = new_status
                bus.publish_device_status(device_id, new_status)
            elif random.random() < 0.008:
                new_status = DeviceStatus.TESTING
                dev["status"] = new_status
                bus.publish_device_status(device_id, new_status)
