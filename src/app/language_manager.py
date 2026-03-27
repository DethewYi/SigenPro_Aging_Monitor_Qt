from PyQt6.QtCore import QObject, pyqtSignal, QTranslator, QSettings, QLocale, QEvent
from PyQt6.QtWidgets import QApplication


class _DictTranslator(QTranslator):
    """QTranslator subclass that translates from a Python dict."""

    def __init__(self):
        super().__init__()
        self._table: dict[str, str] = {}

    def load_dict(self, table: dict[str, str]):
        self._table = table or {}

    def translate(self, context: str, source_text: str, disambiguation=None, n: int = -1):
        # Qt may pass empty context for tr() calls without context
        if n >= 0:
            return None  # let Qt handle plural forms
        return self._table.get(source_text, None)


class LanguageManager(QObject):
    language_changed = pyqtSignal(str)

    _instance = None

    def __init__(self):
        super().__init__()
        self._translator = _DictTranslator()
        self._current = None
        self._languages = [
            {"name": "中文", "locale": "zh_CN"},
            {"name": "English", "locale": "en_US"},
            # Reserved for future languages
            # {"name": "日本語", "locale": "ja_JP"},
            # {"name": "한국어", "locale": "ko_KR"},
        ]
        self._tables: dict[str, dict[str, str]] = {}
        self._preload_translations()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def switch_language(self, locale):
        """Switch application language and persist in QSettings."""
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance()
        app.removeTranslator(self._translator)

        for lang in self._languages:
            if lang["locale"] == locale:
                table = self._tables.get(locale, {})
                self._translator.load_dict(table)
                app.installTranslator(self._translator)
                self._current = lang
                break

        settings = QSettings()
        settings.setValue("language", locale)

        # Send LanguageChange to all widgets recursively so their
        # changeEvent handlers can retranslate existing widgets.
        event = QEvent(QEvent.Type.LanguageChange)
        for w in QApplication.topLevelWidgets():
            QApplication.sendEvent(w, event)
            for child in w.findChildren(QObject):
                QApplication.sendEvent(child, event)

        self.language_changed.emit(locale)

    def current_language(self):
        return self._current

    def available_languages(self):
        return self._languages

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _preload_translations(self):
        """Import all translation modules so they are available immediately."""
        from importlib import import_module

        for lang in self._languages:
            locale = lang["locale"]
            try:
                mod = import_module(f"src.i18n.{locale}")
                self._tables[locale] = getattr(mod, "TRANSLATIONS", {})
            except Exception:
                self._tables[locale] = {}
