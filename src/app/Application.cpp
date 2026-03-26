#include "Application.h"
#include "app/ThemeManager.h"
#include "app/LanguageManager.h"
#include "app/Logger.h"
#include "storage/DatabaseManager.h"
#include "protocol/plugin_loader/PluginManager.h"
#include "core/alarm_engine/AlarmEngine.h"
#include "core/template_manager/TemplateManager.h"
#include "core/test_engine/TestEngine.h"
#include "instrument/channel_manager/ChannelManager.h"
#include "instrument/scanner/BarcodeScanner.h"
#include "communication/tcp/TcpConnectionManager.h"
#include "core/data_bus/DataBus.h"
#include <QSettings>

Application::Application(int& argc, char* argv[])
    : QApplication(argc, argv)
{
    setApplicationName("SigenPro Aging Monitor");
    setApplicationVersion("1.0.0");
    setOrganizationName("SigenPro");

    // 1. Initialize logging system
    Logger::instance().setLogDir(QCoreApplication::applicationDirPath() + "/logs");
    qInstallMessageHandler(Logger::messageHandler);
    Logger::instance().info(tr("Application starting"));

    // 2. Initialize database
    DatabaseManager::instance().initialize();
    Logger::instance().info(tr("Database initialized"));

    // 3. Load plugins
    PluginManager::instance().loadPlugins(QCoreApplication::applicationDirPath() + "/plugins");
    Logger::instance().info(tr("Plugins loaded"));

    // 4. Create business logic singletons (they auto-connect to DataBus)
    // These are created as children of Application so they get cleaned up
    m_alarmEngine = new AlarmEngine(this);
    m_templateManager = new TemplateManager(this);
    m_templateManager->loadTemplates();
    m_testEngine = new TestEngine(this);
    m_channelManager = new ChannelManager(this);
    m_channelManager->loadChannels();
    m_barcodeScanner = new BarcodeScanner(this);
    m_tcpManager = new TcpConnectionManager(this);

    // Wire TestEngine dependencies
    m_testEngine->setAlarmEngine(m_alarmEngine);
    m_testEngine->setTemplateManager(m_templateManager);

    Logger::instance().info(tr("Business logic modules initialized"));

    // 5. Create main window (after all modules are ready)
    m_mainWindow = new MainWindow();
    m_mainWindow->show();

    // 6. Wire TCP manager -> DataBus (raw data from devices)
    connect(m_tcpManager, &TcpConnectionManager::deviceDataReceived,
            [](int deviceId, const QByteArray& rawData) {
        DataBus::instance().publishRawData(deviceId, rawData);
    });

    // 7. Wire TCP manager status changes -> DataBus
    connect(m_tcpManager, &TcpConnectionManager::deviceStatusChanged,
            [](int deviceId, DeviceStatus status) {
        DataBus::instance().publishDeviceStatus(deviceId, status);
    });

    // 8. Wire barcode scanner -> status bar
    connect(m_barcodeScanner, &BarcodeScanner::barcodeScanned,
            this, [this](const QString& barcode) {
        if (m_mainWindow) {
            m_mainWindow->statusBar()->showMessage(
                tr("Barcode scanned: %1").arg(barcode), 5000);
        }
    });

    // 9. Wire test engine -> channel manager (power control)
    connect(m_testEngine, &TestEngine::testStarted,
            m_channelManager, [this](int channelId) {
        // Power on the channel when test starts
        m_channelManager->powerOn(channelId);
    });
    connect(m_testEngine, &TestEngine::testCompleted,
            m_channelManager, [this](int channelId, TestResult result) {
        // Power off and unbind when test completes
        Q_UNUSED(result);
        m_channelManager->powerOff(channelId);
        m_channelManager->unbindProduct(channelId);
    });

    Logger::instance().info(tr("Signal/slot wiring complete"));

    // Apply saved theme and language
    QSettings settings;
    int savedTheme = settings.value("theme", 0).toInt();
    ThemeManager::instance().applyTheme(static_cast<ThemeManager::Theme>(savedTheme));

    QString savedLang = settings.value("language", "zh_CN").toString();
    LanguageManager::instance().switchLanguage(savedLang);

    Logger::instance().info(tr("Application initialization complete"));
}

Application::~Application()
{
    delete m_mainWindow;
}
