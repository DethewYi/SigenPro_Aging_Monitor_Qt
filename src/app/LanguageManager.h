#pragma once

#include <QObject>
#include <QString>
#include <QTranslator>
#include <QVector>

class LanguageManager : public QObject {
    Q_OBJECT
public:
    struct LanguageInfo {
        QString name;      // display name: "中文"
        QString locale;    // locale: "zh_CN"
        QString qmFile;    // ":/i18n/SigenPro_zh_CN.qm"
    };

    static LanguageManager& instance();

    void switchLanguage(const QString& locale);
    LanguageInfo currentLanguage() const;
    QVector<LanguageInfo> availableLanguages() const;
    QString currentLocale() const;

signals:
    void languageChanged(const QString& locale);

private:
    LanguageManager() = default;
    QTranslator m_translator;
    LanguageInfo m_current;
    QVector<LanguageInfo> m_languages = {
        {"中文", "zh_CN", ":/i18n/SigenPro_zh_CN.qm"},
        {"English", "en_US", ":/i18n/SigenPro_en_US.qm"}
    };
};
