from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QObject, pyqtSignal, QTranslator, QSettings


class LanguageManager(QObject):
    language_changed = pyqtSignal(str)

    _instance = None

    def __init__(self):
        super().__init__()
        self._translator = QTranslator()
        self._current = None
        self._languages = [
            {"name": "中文", "locale": "zh_CN", "qm": ":/i18n/SigenPro_zh_CN.qm"},
            {"name": "English", "locale": "en_US", "qm": ":/i18n/SigenPro_en_US.qm"},
        ]

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def switch_language(self, locale):
        """Switch the application language and persist the choice in QSettings."""
        app = QApplication.instance()
        app.removeTranslator(self._translator)

        for lang in self._languages:
            if lang["locale"] == locale:
                if self._translator.load(lang["qm"]):
                    app.installTranslator(self._translator)
                self._current = lang
                break

        settings = QSettings()
        settings.setValue("language", locale)
        self.language_changed.emit(locale)

    def current_language(self):
        return self._current

    def available_languages(self):
        return self._languages
