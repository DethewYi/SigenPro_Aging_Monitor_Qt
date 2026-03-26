#pragma once

#include <QObject>
#include <QString>

class ThemeManager : public QObject {
    Q_OBJECT
public:
    enum Theme {
        Dark = 0,
        Light = 1,
        Industrial = 2,
        HighContrast = 3
    };
    Q_ENUM(Theme)

    static ThemeManager& instance();

    void applyTheme(Theme theme);
    Theme currentTheme() const;
    QStringList availableThemes() const;
    static QString themeToString(Theme theme);

signals:
    void themeChanged(Theme theme);

private:
    ThemeManager() = default;
    Theme m_currentTheme = Dark;
    void loadAndApplyQSS(const QString& qssPath);
};
