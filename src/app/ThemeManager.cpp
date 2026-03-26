#include "ThemeManager.h"
#include <QApplication>
#include <QFile>
#include <QSettings>

ThemeManager& ThemeManager::instance()
{
    static ThemeManager inst;
    return inst;
}

void ThemeManager::applyTheme(Theme theme)
{
    m_currentTheme = theme;
    QString qssPath = QString(":/themes/%1.qss").arg(themeToString(theme));
    loadAndApplyQSS(qssPath);

    QSettings settings;
    settings.setValue("theme", static_cast<int>(theme));

    emit themeChanged(theme);
}

Theme ThemeManager::currentTheme() const
{
    return m_currentTheme;
}

QStringList ThemeManager::availableThemes() const
{
    return {"Dark", "Light", "Industrial", "HighContrast"};
}

QString ThemeManager::themeToString(Theme theme)
{
    switch (theme) {
    case Dark: return "dark";
    case Light: return "light";
    case Industrial: return "industrial";
    case HighContrast: return "highcontrast";
    }
    return "dark";
}

void ThemeManager::loadAndApplyQSS(const QString& qssPath)
{
    QFile file(qssPath);
    if (file.open(QIODevice::ReadOnly | QIODevice::Text)) {
        qApp->setStyleSheet(file.readAll());
        file.close();
    }
}
