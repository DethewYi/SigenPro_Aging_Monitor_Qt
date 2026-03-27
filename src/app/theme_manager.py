from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QObject, pyqtSignal, QSettings, QFile, QIODevice
import os


class ThemeManager(QObject):
    theme_changed = pyqtSignal(int)

    DARK = 0
    LIGHT = 1
    INDUSTRIAL = 2
    HIGH_CONTRAST = 3
    OCEAN = 4
    FOREST = 5
    SUNSET = 6
    PURPLE = 7

    _instance = None

    def __init__(self):
        super().__init__()
        self._current_theme = self.DARK

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def apply_theme(self, theme_id):
        """Apply a theme by its integer ID and persist the choice in QSettings."""
        self._current_theme = theme_id
        theme_names = ["dark", "light", "industrial", "highcontrast",
                       "ocean", "forest", "sunset", "purple"]
        qss_path = f":/themes/{theme_names[theme_id]}.qss"

        # Try Qt resource first, then file system
        qss_file = QFile(qss_path)
        if qss_file.open(QIODevice.OpenModeFlag.ReadOnly | QIODevice.OpenModeFlag.Text):
            app = QApplication.instance()
            app.setStyleSheet(qss_file.readAll().data().decode('utf-8'))
            qss_file.close()
        else:
            # Fallback to file system
            base_dir = os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            )
            file_path = os.path.join(
                base_dir, "resources", "themes", f"{theme_names[theme_id]}.qss"
            )
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    QApplication.instance().setStyleSheet(f.read())

        settings = QSettings()
        settings.setValue("theme", theme_id)
        self.theme_changed.emit(theme_id)

    def current_theme(self):
        return self._current_theme

    @staticmethod
    def available_themes():
        return ["Dark", "Light", "Industrial", "High Contrast",
                "Ocean Blue", "Forest Green", "Sunset Orange", "Royal Purple"]

    @staticmethod
    def theme_id_to_name(theme_id):
        names = {0: "dark", 1: "light", 2: "industrial", 3: "highcontrast",
                 4: "ocean", 5: "forest", 6: "sunset", 7: "purple"}
        return names.get(theme_id, "dark")
