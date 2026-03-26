#include "Application.h"
#include "app/ThemeManager.h"
#include <QSettings>

Application::Application(int& argc, char* argv[])
    : QApplication(argc, argv)
{
    setApplicationName("SigenPro Aging Monitor");
    setApplicationVersion("1.0.0");
    setOrganizationName("SigenPro");

    m_mainWindow = new MainWindow();
    m_mainWindow->show();

    QSettings settings;
    int savedTheme = settings.value("theme", 0).toInt();
    ThemeManager::instance().applyTheme(static_cast<ThemeManager::Theme>(savedTheme));
}

Application::~Application()
{
    delete m_mainWindow;
}
