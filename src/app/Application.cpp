#include "Application.h"

Application::Application(int& argc, char* argv[])
    : QApplication(argc, argv)
{
    setApplicationName("SigenPro Aging Monitor");
    setApplicationVersion("1.0.0");
    setOrganizationName("SigenPro");

    m_mainWindow = new MainWindow();
    m_mainWindow->show();
}

Application::~Application()
{
    delete m_mainWindow;
}
