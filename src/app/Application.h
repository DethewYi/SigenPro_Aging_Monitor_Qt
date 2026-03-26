#pragma once

#include <QApplication>

#include "ui/main_window/MainWindow.h"

class AlarmEngine;
class TemplateManager;
class TestEngine;
class ChannelManager;
class BarcodeScanner;
class TcpConnectionManager;

class Application : public QApplication {
    Q_OBJECT
public:
    Application(int& argc, char* argv[]);
    ~Application();

private:
    MainWindow* m_mainWindow = nullptr;
    AlarmEngine* m_alarmEngine = nullptr;
    TemplateManager* m_templateManager = nullptr;
    TestEngine* m_testEngine = nullptr;
    ChannelManager* m_channelManager = nullptr;
    BarcodeScanner* m_barcodeScanner = nullptr;
    TcpConnectionManager* m_tcpManager = nullptr;
};
