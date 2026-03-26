#include "LanguageManager.h"
#include <QApplication>
#include <QSettings>

LanguageManager& LanguageManager::instance()
{
    static LanguageManager inst;
    return inst;
}

void LanguageManager::switchLanguage(const QString& locale)
{
    qApp->removeTranslator(&m_translator);

    for (const auto& lang : m_languages) {
        if (lang.locale == locale) {
            if (m_translator.load(lang.qmFile)) {
                qApp->installTranslator(&m_translator);
                m_current = lang;
            }
            break;
        }
    }

    QSettings settings;
    settings.setValue("language", locale);
    emit languageChanged(locale);
}

LanguageInfo LanguageManager::currentLanguage() const
{
    return m_current;
}

QString LanguageManager::currentLocale() const
{
    return m_current.locale;
}

QVector<LanguageInfo> LanguageManager::availableLanguages() const
{
    return m_languages;
}
