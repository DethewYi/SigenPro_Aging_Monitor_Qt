#pragma once

#include <QApplication>

#include "ui/main_window/MainWindow.h"

class Application : public QApplication {
    Q_OBJECT
public:
    Application(int& argc, char* argv[]);
    ~Application();

private:
    MainWindow* m_mainWindow = nullptr;
};
