#include "Application.h"
#include "app/ThemeManager.h"
#include "app/LanguageManager.h"
#include "app/Logger.h"
#include <QSettings>

Application::Application(int& argc, char* argv[])
    : QApplication(argc, argv)
{
    setApplicationName("SigenPro Aging Monitor");
    setApplicationVersion("1.0.0");
    setOrganizationName("SigenPro");

    // Initialize logging system
    Logger::instance().setLogDir(QCoreApplication::applicationDirPath() + "/logs");
    qInstallMessageHandler(Logger::messageHandler);
    Logger::instance().info(tr("Application starting"));

    m_mainWindow = new MainWindow();
    m_mainWindow->show();

    QSettings settings;
    int savedTheme = settings.value("theme", 0).toInt();
    ThemeManager::instance().applyTheme(static_cast<ThemeManager::Theme>(savedTheme));

    QString savedLang = settings.value("language", "zh_CN").toString();
    LanguageManager::instance().switchLanguage(savedLang);
}

Application::~Application()
{
    delete m_mainWindow;
}
