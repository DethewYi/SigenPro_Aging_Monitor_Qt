import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QSettings


class Application(QApplication):
    def __init__(self, argv):
        super().__init__(argv)
        self.setApplicationName("SigenPro Aging Monitor")
        self.setApplicationVersion("1.0.0")
        self.setOrganizationName("SigenPro")

        self._main_window = None
        self._settings = QSettings("SigenPro", "SigenProAgingMonitor")

        # Modules will be initialized in Batch 6
