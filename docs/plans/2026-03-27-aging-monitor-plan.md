# 储能产品老化监控系统 — 实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 构建一个完整的储能产品老化监控桌面应用，支持 100-500 台设备实时监控、仪器控制、扫码绑定、报表生成。

**Architecture:** 分层架构 — 界面层 / 业务逻辑层 / 数据总线 / 通信层+仪器控制层+存储层。通信与控制协议通过插件 DLL 扩展。数据采集走 TCP 为主，CAN/485 为辅，本地 SQLite + 远程 MySQL 双存储。

**Tech Stack:** Qt 6, CMake, C++17, QCustomPlot, SQLite, MySQL, QPrinter, QXlsx, Qt Linguist

---

## Phase 1: 项目脚手架与基础设施

### Task 1: CMake 项目结构搭建

**Files:**
- Create: `CMakeLists.txt` (根)
- Create: `src/CMakeLists.txt`
- Create: `src/main.cpp`
- Create: `src/app/Application.h`
- Create: `src/app/Application.cpp`

**Step 1: 创建根 CMakeLists.txt**

```cmake
cmake_minimum_required(VERSION 3.20)
project(SigenPro_Aging_Monitor VERSION 1.0.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC ON)
set(CMAKE_AUTORCC ON)
set(CMAKE_AUTOUIC ON)

find_package(Qt6 REQUIRED COMPONENTS Core Gui Widgets Sql Network SerialPort PrintSupport)
find_package(Qt6 OPTIONAL_COMPONENTS LinguistTools)

add_subdirectory(src)
```

**Step 2: 创建 src/CMakeLists.txt**

```cmake
set(SOURCES
    main.cpp
    app/Application.cpp
)

set(HEADERS
    app/Application.h
)

add_executable(${PROJECT_NAME} WIN32 ${SOURCES} ${HEADERS})

target_link_libraries(${PROJECT_NAME} PRIVATE
    Qt6::Core
    Qt6::Gui
    Qt6::Widgets
    Qt6::Sql
    Qt6::Network
    Qt6::SerialPort
    Qt6::PrintSupport
)

target_include_directories(${PROJECT_NAME} PRIVATE ${CMAKE_SOURCE_DIR}/src)
```

**Step 3: 创建 Application 类**

`src/app/Application.h`:
```cpp
#pragma once

#include <QApplication>

class MainWindow;

class Application : public QApplication {
    Q_OBJECT
public:
    Application(int& argc, char* argv[]);
    ~Application();

private:
    MainWindow* m_mainWindow = nullptr;
};
```

`src/app/Application.cpp`:
```cpp
#include "Application.h"
#include <QQmlApplicationEngine>

Application::Application(int& argc, char* argv[])
    : QApplication(argc, argv)
{
    setApplicationName("SigenPro Aging Monitor");
    setApplicationVersion("1.0.0");
    setOrganizationName("SigenPro");
}

Application::~Application() = default;
```

`src/main.cpp`:
```cpp
#include "app/Application.h"

int main(int argc, char* argv[])
{
    Application app(argc, argv);
    // MainWindow 将在 Task 2 中创建
    return app.exec();
}
```

**Step 4: 编译验证**

Run: `cmake -B build -S . -DCMAKE_PREFIX_PATH=<Qt6路径>` 和 `cmake --build build`
Expected: 编译成功，生成可执行文件

**Step 5: 初始化 Git 仓库并提交**

Run:
```bash
git init
git add CMakeLists.txt src/CMakeLists.txt src/main.cpp src/app/Application.h src/app/Application.cpp
git commit -m "feat: scaffold CMake + Qt6 project structure"
```

---

### Task 2: 数据模型定义

**Files:**
- Create: `src/core/common/Types.h`
- Create: `src/core/common/DeviceData.h`
- Create: `src/core/common/ChannelInfo.h`
- Create: `src/core/common/TestTemplate.h`
- Create: `src/core/common/AlarmRecord.h`

**Step 1: 定义枚举与基础类型**

`src/core/common/Types.h`:
```cpp
#pragma once

#include <QString>

enum class DeviceStatus {
    Offline,      // 离线
    Idle,         // 空闲
    Testing,      // 测试中
    Completed,    // 已完成
    Alarm,        // 报警
    Fault         // 故障
};

enum class ChannelStatus {
    Free,         // 空闲
    Bound,        // 已绑定SN/PN
    Testing,      // 测试中
    Fault         // 故障
};

enum class TestResult {
    Pending,      // 待判定
    Passed,       // 通过
    Failed,       // 异常
    Interrupted   // 中断
};

enum class CommunicationType {
    TcpSocket,
    CanBus,
    Rs485
};

struct DeviceConfig {
    int deviceId = -1;
    QString name;
    QString model;          // 产品型号 (PCS/PACK/DCDC/BMU/BC)
    CommunicationType commType = CommunicationType::TcpSocket;
    QString ipAddress;
    int port = 0;
    QString protocolName;   // 协议插件名称
    int channelId = -1;     // 关联通道
};
```

**Step 2: 定义设备数据结构**

`src/core/common/DeviceData.h`:
```cpp
#pragma once

#include <QDateTime>
#include <QMap>
#include <QString>

struct DeviceData {
    int deviceId = -1;
    QDateTime timestamp;
    QMap<QString, double> parameters;  // 键值对: "voltage" -> 48.5
    bool communicationOk = true;
    int frameErrorCount = 0;
};
```

**Step 3: 定义通道信息结构**

`src/core/common/ChannelInfo.h`:
```cpp
#pragma once

#include "Types.h"
#include <QString>

struct ChannelInfo {
    int channelId = -1;
    ChannelStatus status = ChannelStatus::Free;
    QString boundSN;             // 绑定的产品序列号
    QString boundPN;             // 绑定的产品料号
    int powerControllerId = -1;  // 电源控制器ID
    int contactorControllerId = -1; // 接触器控制器ID
    int powerChannel = -1;       // 电源通道号
    int contactorChannel = -1;   // 接触器通道号
    QString powerProtocolName;   // 电源控制协议插件名
    QString contactorProtocolName; // 接触器控制协议插件名
};
```

**Step 4: 定义测试模板结构**

`src/core/common/TestTemplate.h`:
```cpp
#pragma once

#include <QMap>
#include <QString>
#include <QVector>

struct AlarmThreshold {
    double upperLimit = 0;
    double lowerLimit = 0;
    bool enabled = false;
};

struct TestPhase {
    QString name;
    int durationMinutes = 0;
    QMap<QString, AlarmThreshold> thresholds;  // 该阶段各参数阈值
};

struct TestTemplate {
    int templateId = -1;
    QString name;
    QString productModel;    // 适用产品型号
    QMap<QString, double> collectParams;  // 采集参数: key -> 采样频率Hz
    int totalDurationMinutes = 0;
    QMap<QString, AlarmThreshold> defaultThresholds;
    QVector<TestPhase> phases;  // 可选分段
};
```

**Step 5: 定义报警记录结构**

`src/core/common/AlarmRecord.h`:
```cpp
#pragma once

#include <QDateTime>
#include <QString>

struct AlarmRecord {
    int id = -1;
    QDateTime timestamp;
    int deviceId = -1;
    QString deviceName;
    QString paramName;
    double currentValue = 0;
    double threshold = 0;
    bool isUpperLimit = true;
    bool acknowledged = false;
    QString message;
};
```

**Step 6: 提交**

```bash
git add src/core/common/
git commit -m "feat: define core data models (DeviceData, ChannelInfo, TestTemplate, AlarmRecord)"
```

---

### Task 3: 主窗口骨架

**Files:**
- Create: `src/ui/main_window/MainWindow.h`
- Create: `src/ui/main_window/MainWindow.cpp`
- Modify: `src/app/Application.cpp`
- Modify: `src/CMakeLists.txt`

**Step 1: 创建 MainWindow**

`src/ui/main_window/MainWindow.h`:
```cpp
#pragma once

#include <QMainWindow>
#include <QStackedWidget>
#include <QPushButton>

class QStatusBar;

class MainWindow : public QMainWindow {
    Q_OBJECT
public:
    explicit MainWindow(QWidget* parent = nullptr);
    ~MainWindow() = default;

private:
    void setupUI();
    void setupMenuBar();
    void setupSideNavigation();
    void setupContentArea();

    QWidget* m_sideNav = nullptr;
    QStackedWidget* m_contentStack = nullptr;

    // 导航按钮
    QPushButton* m_btnOverview = nullptr;
    QPushButton* m_btnAlarm = nullptr;
    QPushButton* m_btnDataQuery = nullptr;
    QPushButton* m_btnSettings = nullptr;

    int m_pageOverview = 0;
    int m_pageAlarm = 1;
    int m_pageDataQuery = 2;
    int m_pageSettings = 3;
};
```

`src/ui/main_window/MainWindow.cpp`:
```cpp
#include "MainWindow.h"
#include <QHBoxLayout>
#include <QVBoxLayout>
#include <QLabel>
#include <QStatusBar>
#include <QMenuBar>

MainWindow::MainWindow(QWidget* parent)
    : QMainWindow(parent)
{
    setWindowTitle(tr("SigenPro Aging Monitor"));
    resize(1400, 900);
    setupUI();
    setupMenuBar();
}

void MainWindow::setupUI()
{
    QWidget* centralWidget = new QWidget(this);
    QHBoxLayout* mainLayout = new QHBoxLayout(centralWidget);
    mainLayout->setContentsMargins(0, 0, 0, 0);
    mainLayout->setSpacing(0);

    setupSideNavigation();
    setupContentArea();

    mainLayout->addWidget(m_sideNav);
    mainLayout->addWidget(m_contentStack);

    setCentralWidget(centralWidget);
    statusBar()->showMessage(tr("Ready"));
}

void MainWindow::setupMenuBar()
{
    QMenuBar* menuBar = this->menuBar();

    // 文件菜单
    QMenu* fileMenu = menuBar->addMenu(tr("&File"));
    fileMenu->addAction(tr("&Settings"), this, [this]() {
        m_contentStack->setCurrentIndex(m_pageSettings);
    });
    fileMenu->addSeparator();
    fileMenu->addAction(tr("E&xit"), this, &QWidget::close);

    // 视图菜单
    QMenu* viewMenu = menuBar->addMenu(tr("&View"));
    viewMenu->addAction(tr("Device &Overview"), this, [this]() {
        m_contentStack->setCurrentIndex(m_pageOverview);
    });
    viewMenu->addAction(tr("&Alarms"), this, [this]() {
        m_contentStack->setCurrentIndex(m_pageAlarm);
    });
    viewMenu->addAction(tr("&Data Query"), this, [this]() {
        m_contentStack->setCurrentIndex(m_pageDataQuery);
    });
}

void MainWindow::setupSideNavigation()
{
    m_sideNav = new QWidget(this);
    m_sideNav->setFixedWidth(200);
    QVBoxLayout* layout = new QVBoxLayout(m_sideNav);
    layout->setContentsMargins(8, 16, 8, 16);
    layout->setSpacing(4);

    QLabel* logo = new QLabel(tr("SigenPro"), m_sideNav);
    logo->setAlignment(Qt::AlignCenter);
    QFont font;
    font.setPointSize(18);
    font.setBold(true);
    logo->setFont(font);
    layout->addWidget(logo);
    layout->addSpacing(24);

    auto createNavButton = [&](const QString& text, int pageIndex) -> QPushButton* {
        QPushButton* btn = new QPushButton(text, m_sideNav);
        btn->setCheckable(true);
        btn->setFixedHeight(44);
        btn->setCursor(Qt::PointingHandCursor);
        connect(btn, &QPushButton::clicked, this, [this, pageIndex]() {
            m_contentStack->setCurrentIndex(pageIndex);
        });
        layout->addWidget(btn);
        return btn;
    };

    m_btnOverview = createNavButton(tr("Device Overview"), m_pageOverview);
    m_btnOverview->setChecked(true);
    createNavButton(tr("Alarms"), m_pageAlarm);
    createNavButton(tr("Data Query"), m_pageDataQuery);
    layout->addStretch();
    createNavButton(tr("Settings"), m_pageSettings);
}

void MainWindow::setupContentArea()
{
    m_contentStack = new QStackedWidget(this);

    // 占位页面，后续替换为实际组件
    for (int i = 0; i < 4; ++i) {
        QLabel* placeholder = new QLabel(m_contentStack);
        placeholder->setAlignment(Qt::AlignCenter);
        QFont font;
        font.setPointSize(16);
        placeholder->setFont(font);
        m_contentStack->addWidget(placeholder);
    }

    // 占位文本
    static_cast<QLabel*>(m_contentStack->widget(m_pageOverview))->setText(tr("Device Overview"));
    static_cast<QLabel*>(m_contentStack->widget(m_pageAlarm))->setText(tr("Alarm Panel"));
    static_cast<QLabel*>(m_contentStack->widget(m_pageDataQuery))->setText(tr("Data Query"));
    static_cast<QLabel*>(m_contentStack->widget(m_pageSettings))->setText(tr("Settings"));
}
```

**Step 2: 更新 Application.cpp 显示 MainWindow**

```cpp
#include "Application.h"
#include "ui/main_window/MainWindow.h"

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
```

**Step 3: 更新 src/CMakeLists.txt 添加新文件**

在 SOURCES 中添加 `ui/main_window/MainWindow.cpp`，HEADERS 中添加 `ui/main_window/MainWindow.h`。

**Step 4: 编译运行，验证主窗口显示正确**

**Step 5: 提交**

```bash
git add src/ui/main_window/ src/app/Application.cpp src/CMakeLists.txt
git commit -m "feat: add MainWindow with side navigation and page stack"
```

---

## Phase 2: 主题与国际化系统

### Task 4: 主题系统

**Files:**
- Create: `src/app/ThemeManager.h`
- Create: `src/app/ThemeManager.cpp`
- Create: `resources/themes/dark.qss`
- Create: `resources/themes/light.qss`
- Create: `resources/themes/industrial.qss`
- Create: `resources/themes/highcontrast.qss`
- Create: `resources/resources.qrc`

**Step 1: 创建 ThemeManager**

`src/app/ThemeManager.h`:
```cpp
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

signals:
    void themeChanged(Theme theme);

private:
    ThemeManager() = default;
    Theme m_currentTheme = Dark;
    void loadAndApplyQSS(const QString& qssPath);
};
```

`src/app/ThemeManager.cpp`:
```cpp
#include "ThemeManager.h"
#include <QApplication>
#include <QFile>
#include <QSettings>
#include <QDir>

ThemeManager& ThemeManager::instance()
{
    static ThemeManager inst;
    return inst;
}

void ThemeManager::applyTheme(Theme theme)
{
    m_currentTheme = theme;
    QString qssPath = QString(":/themes/%1.qss").arg(toString(theme));
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

void ThemeManager::loadAndApplyQSS(const QString& qssPath)
{
    QFile file(qssPath);
    if (file.open(QIODevice::ReadOnly | QIODevice::Text)) {
        qApp->setStyleSheet(file.readAll());
        file.close();
    }
}

QString ThemeManager::toString(Theme theme)
{
    switch (theme) {
    case Dark: return "dark";
    case Light: return "light";
    case Industrial: return "industrial";
    case HighContrast: return "highcontrast";
    }
    return "dark";
}
```

**Step 2: 创建深色主题 QSS**

`resources/themes/dark.qss`: 完整的深色主题样式，覆盖 QMainWindow、QPushButton、QLabel、QTableWidget、QStackedWidget 等基础控件。参考工业监控软件深色风格，背景色 #1e1e2e，前景色 #cdd6f4，强调色 #89b4fa，成功色 #a6e3a1，警告色 #f9e2af，错误色 #f38ba8。

**Step 3: 创建其余主题 QSS 文件**

`resources/themes/light.qss`: 浅色主题，背景 #ffffff，前景 #333333
`resources/themes/industrial.qss`: 蓝灰工业风，背景 #2b2d42，前景 #edf2f4，强调色 #8d99ae
`resources/themes/highcontrast.qss`: 高对比度，背景 #000000，前景 #ffffff，强调色 #ffff00

**Step 4: 创建资源文件**

`resources/resources.qrc`:
```xml
<RCC>
    <qresource prefix="/themes">
        <file>themes/dark.qss</file>
        <file>themes/light.qss</file>
        <file>themes/industrial.qss</file>
        <file>themes/highcontrast.qss</file>
    </qresource>
</RCC>
```

**Step 5: 在 Application 初始化时加载上次保存的主题**

在 `Application.cpp` 构造函数末尾调用 `ThemeManager::instance().applyTheme(savedTheme);`

**Step 6: 编译验证主题切换效果**

**Step 7: 提交**

```bash
git add src/app/ThemeManager.h src/app/ThemeManager.cpp resources/ src/CMakeLists.txt
git commit -m "feat: add theme system with 4 themes (dark/light/industrial/highcontrast)"
```

---

### Task 5: 国际化系统

**Files:**
- Create: `src/app/LanguageManager.h`
- Create: `src/app/LanguageManager.cpp`
- Create: `src/i18n/SigenPro_zh_CN.ts`
- Create: `src/i18n/SigenPro_en_US.ts`
- Modify: `src/CMakeLists.txt`

**Step 1: 创建 LanguageManager**

`src/app/LanguageManager.h`:
```cpp
#pragma once

#include <QObject>
#include <QString>
#include <QTranslator>

class LanguageManager : public QObject {
    Q_OBJECT
public:
    static LanguageManager& instance();

    struct LanguageInfo {
        QString name;      // 显示名: "中文"
        QString locale;    // locale: "zh_CN"
        QString qmFile;    // ":/i18n/SigenPro_zh_CN.qm"
    };

    void switchLanguage(const QString& locale);
    LanguageInfo currentLanguage() const;
    QVector<LanguageInfo> availableLanguages() const;

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
```

`src/app/LanguageManager.cpp`:
```cpp
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

QVector<LanguageInfo> LanguageManager::availableLanguages() const
{
    return m_languages;
}
```

**Step 2: 确保所有 UI 字符串使用 tr()**

Task 3 中的 MainWindow.cpp 已经使用了 `tr()`，后续所有新增 UI 代码也必须使用 `tr()`。

**Step 3: 使用 lupdate 生成 .ts 文件**

Run: `lupdate src/ -ts src/i18n/SigenPro_zh_CN.ts src/i18n/SigenPro_en_US.ts`

**Step 4: 编译 .qm 文件到资源**

Run: `lrelease src/i18n/SigenPro_zh_CN.ts src/i18n/SigenPro_en_US.ts`

将 .qm 添加到 resources.qrc。

**Step 5: 在 Application 初始化时加载保存的语言**

**Step 6: 提交**

```bash
git add src/app/LanguageManager.h src/app/LanguageManager.cpp src/i18n/ resources/resources.qrc src/CMakeLists.txt
git commit -m "feat: add i18n system with Chinese and English support"
```

---

### Task 6: 设置页面

**Files:**
- Create: `src/ui/settings/SettingsPage.h`
- Create: `src/ui/settings/SettingsPage.cpp`

**Step 1: 创建设置页面**

包含以下设置项：
- 主题选择（下拉框，4 个主题）
- 语言切换（下拉框，中文/English）
- 数据库配置（本地 SQLite 路径、远程 MySQL 连接信息）
- 数据保留天数（SpinBox）
- 数据同步间隔（SpinBox）

**Step 2: 切换主题和语言时实时生效**

通过信号槽连接 ThemeManager 和 LanguageManager。

**Step 3: 替换 MainWindow 中的 Settings 占位页为 SettingsPage**

**Step 4: 编译验证**

**Step 5: 提交**

```bash
git add src/ui/settings/
git commit -m "feat: add SettingsPage with theme, language, and database config"
```

---

## Phase 3: 存储层

### Task 7: SQLite 本地数据库

**Files:**
- Create: `src/storage/local_db/LocalDatabase.h`
- Create: `src/storage/local_db/LocalDatabase.cpp`
- Create: `src/storage/DatabaseManager.h`
- Create: `src/storage/DatabaseManager.cpp`

**Step 1: 创建 LocalDatabase 类**

提供以下功能：
- `initialize()`: 创建数据库文件和元数据表（devices, channels, test_templates, test_records, alarms）
- `createDailyTable(const QString& date)`: 按天创建数据表 device_data_YYYYMMDD
- `insertDeviceData(const QVector<DeviceData>& data)`: 批量插入设备数据
- `queryDeviceData(int deviceId, const QDateTime& start, const QDateTime& end)`: 查询历史数据
- `insertAlarmRecord(const AlarmRecord& record)`: 插入报警记录
- `queryAlarms(const QDateTime& start, int limit)`: 查询报警记录
- `saveTestRecord(...)`: 保存测试记录
- `saveChannelInfo(const ChannelInfo&)`: 保存通道绑定信息
- `loadChannels()`: 加载所有通道信息（用于断电恢复）
- `cleanOldData(int retainDays)`: 清理过期数据

**Step 2: 创建 DatabaseManager 作为统一入口**

封装 LocalDatabase 和后续的 RemoteDatabase，提供 `init()`、`writeData()`、`queryData()` 等统一接口。

**Step 3: 编译验证**

**Step 4: 提交**

```bash
git add src/storage/
git commit -m "feat: add SQLite local database with daily partitioning and batch insert"
```

---

### Task 8: 远程数据库同步

**Files:**
- Create: `src/storage/remote_db/RemoteDatabase.h`
- Create: `src/storage/remote_db/RemoteDatabase.cpp`
- Create: `src/storage/sync/DataSyncManager.h`
- Create: `src/storage/sync/DataSyncManager.cpp`

**Step 1: 创建 RemoteDatabase 类**

支持 MySQL/PostgreSQL（通过 Qt SQL 驱动），与 LocalDatabase 结构对称，按月分表。

**Step 2: 创建 DataSyncManager**

- 定时器驱动，按配置的同步间隔触发
- 从本地 SQLite 读取未同步数据，批量写入远程数据库
- 记录同步进度，支持断点续传
- 同步失败自动重试，记录错误日志

**Step 3: 编译验证**

**Step 4: 提交**

```bash
git add src/storage/remote_db/ src/storage/sync/
git commit -m "feat: add remote database sync with retry and progress tracking"
```

---

## Phase 4: 协议接口与插件系统

### Task 9: 协议接口定义

**Files:**
- Create: `src/protocol/interface/IProtocolParser.h`
- Create: `src/protocol/interface/IInstrumentController.h`
- Create: `src/protocol/interface/PluginInterface.h`

**Step 1: 定义 IProtocolParser**

```cpp
#pragma once

#include <QtPlugin>
#include "core/common/DeviceData.h"

class IProtocolParser {
public:
    virtual ~IProtocolParser() = default;
    virtual bool parse(const QByteArray& rawData, DeviceData& output) = 0;
    virtual QByteArray buildRequest(const QString& cmd) = 0;
    virtual QString protocolName() const = 0;
};

#define IProtocolParser_iid "com.sigenpro.IProtocolParser"
Q_DECLARE_INTERFACE(IProtocolParser, IProtocolParser_iid)
```

**Step 2: 定义 IInstrumentController**

```cpp
#pragma once

#include <QtPlugin>
#include "core/common/Types.h"

struct InstrumentStatus {
    bool powered = false;
    double voltage = 0;
    double current = 0;
    bool fault = false;
};

class IInstrumentController {
public:
    virtual ~IInstrumentController() = default;
    virtual bool connect(const DeviceConfig& config) = 0;
    virtual void disconnect() = 0;
    virtual bool powerOn(int channel) = 0;
    virtual bool powerOff(int channel) = 0;
    virtual bool setVoltage(int channel, double voltage) = 0;
    virtual bool setCurrent(int channel, double current) = 0;
    virtual bool readStatus(int channel, InstrumentStatus& status) = 0;
    virtual QString protocolName() const = 0;
};

#define IInstrumentController_iid "com.sigenpro.IInstrumentController"
Q_DECLARE_INTERFACE(IInstrumentController, IInstrumentController_iid)
```

**Step 3: 提交**

```bash
git add src/protocol/interface/
git commit -m "feat: define plugin interfaces for protocol parser and instrument controller"
```

---

### Task 10: 插件管理器

**Files:**
- Create: `src/protocol/plugin_loader/PluginManager.h`
- Create: `src/protocol/plugin_loader/PluginManager.cpp`

**Step 1: 实现 PluginManager**

功能：
- `loadPlugins(const QString& pluginDir)`: 扫描 plugins/ 目录，加载所有 DLL
- `getProtocolParser(const QString& name)`: 按协议名获取解析器实例
- `getInstrumentController(const QString& name)`: 按协议名获取控制器实例
- `availableParsers()`: 列出所有已加载的解析协议
- `availableControllers()`: 列出所有已加载的控制协议

使用 QPluginLoader 动态加载 DLL，缓存实例。

**Step 2: 编译验证**

**Step 3: 提交**

```bash
git add src/protocol/plugin_loader/
git commit -m "feat: add PluginManager for dynamic DLL loading"
```

---

## Phase 5: 通信层

### Task 11: TCP 通信管理器

**Files:**
- Create: `src/communication/tcp/TcpDeviceConnection.h`
- Create: `src/communication/tcp/TcpDeviceConnection.cpp`
- Create: `src/communication/tcp/TcpConnectionManager.h`
- Create: `src/communication/tcp/TcpConnectionManager.cpp`

**Step 1: 创建 TcpDeviceConnection**

单台设备的 TCP 连接，运行在独立线程中：
- 自动重连（指数退避）
- 心跳检测
- 数据帧接收缓冲与校验
- 通过信号发射 `dataReceived(QByteArray)` 和 `connectionStateChanged(DeviceStatus)`

**Step 2: 创建 TcpConnectionManager**

管理所有 TCP 连接：
- `addDevice(const DeviceConfig&)`: 添加设备并创建连接
- `removeDevice(int deviceId)`: 移除设备
- `sendCommand(int deviceId, const QByteArray& cmd)`: 发送指令
- 信号: `deviceDataReceived(DeviceData)`, `deviceStatusChanged(int, DeviceStatus)`
- 使用 QThreadPool 管理线程

**Step 3: 编译验证**

**Step 4: 提交**

```bash
git add src/communication/tcp/
git commit -m "feat: add TCP connection manager with auto-reconnect and heartbeat"
```

---

### Task 12: CAN 与 RS485 桥接

**Files:**
- Create: `src/communication/can/CanBridge.h`
- Create: `src/communication/can/CanBridge.cpp`
- Create: `src/communication/rs485/Rs485Bridge.h`
- Create: `src/communication/rs485/Rs485Bridge.cpp`

**Step 1: 创建 CanBridge**

通过 CAN-以太网转换器接入，本质是 TCP 客户端连接，接收 CAN 帧后封装为 DeviceData。

**Step 2: 创建 Rs485Bridge**

通过串口服务器（TCP）或本地串口（QSerialPort）接入。支持两种模式：
- 网络模式：TCP 连接到串口服务器
- 串口模式：本地 QSerialPort 直连

**Step 3: 编译验证**

**Step 4: 提交**

```bash
git add src/communication/can/ src/communication/rs485/
git commit -m "feat: add CAN and RS485 bridge communication"
```

---

### Task 13: 数据总线

**Files:**
- Create: `src/core/data_bus/DataBus.h`
- Create: `src/core/data_bus/DataBus.cpp`

**Step 1: 创建 DataBus**

全局单例事件总线，解耦数据生产者和消费者：
- `void publishDeviceData(const DeviceData& data)`: 发布设备数据
- `void publishAlarm(const AlarmRecord& alarm)`: 发布报警
- `void publishDeviceStatus(int deviceId, DeviceStatus status)`: 发布设备状态
- 信号: `deviceDataReceived(DeviceData)`, `alarmTriggered(AlarmRecord)`, `deviceStatusChanged(int, DeviceStatus)`

所有通信层连接到此总线，UI 层从此总线订阅数据。

**Step 2: 将 DataBus 集成到 Application 初始化**

**Step 3: 编译验证**

**Step 4: 提交**

```bash
git add src/core/data_bus/
git commit -m "feat: add DataBus event system for decoupling data flow"
```

---

## Phase 6: 核心业务逻辑

### Task 14: 报警引擎

**Files:**
- Create: `src/core/alarm_engine/AlarmEngine.h`
- Create: `src/core/alarm_engine/AlarmEngine.cpp`

**Step 1: 实现 AlarmEngine**

- 订阅 DataBus 的 `deviceDataReceived` 信号
- 根据当前测试模板的阈值配置判定报警
- 支持分阶段阈值（测试不同阶段用不同阈值）
- 触发报警时：发布到 DataBus、写入数据库、记录日志
- 支持报警确认操作

**Step 2: 编译验证**

**Step 3: 提交**

```bash
git add src/core/alarm_engine/
git commit -m "feat: add AlarmEngine with threshold checking and phase-aware alarms"
```

---

### Task 15: 模板管理器

**Files:**
- Create: `src/core/template_manager/TemplateManager.h`
- Create: `src/core/template_manager/TemplateManager.cpp`

**Step 1: 实现 TemplateManager**

- `loadTemplates()`: 从数据库加载所有模板
- `getTemplate(int id)`: 获取模板
- `getTemplateByModel(const QString& productModel)`: 按产品型号获取默认模板
- `saveTemplate(const TestTemplate&)`: 保存/更新模板
- `deleteTemplate(int id)`: 删除模板
- `cloneTemplate(int id)`: 复制模板（用于操作员微调）
- 信号: `templateUpdated()`, `templateAdded()`

**Step 2: 编译验证**

**Step 3: 提交**

```bash
git add src/core/template_manager/
git commit -m "feat: add TemplateManager with CRUD and model-based lookup"
```

---

### Task 16: 测试引擎

**Files:**
- Create: `src/core/test_engine/TestEngine.h`
- Create: `src/core/test_engine/TestEngine.cpp`

**Step 1: 实现 TestEngine**

管理单个通道的完整测试生命周期：
- 状态机：Idle → Starting → Running → Paused → Completed / Interrupted
- `startTest(int channelId, int templateId)`: 绑定模板启动测试
- `pauseTest(int channelId)`: 暂停
- `resumeTest(int channelId)`: 恢复
- `stopTest(int channelId)`: 手动停止
- 定时检查测试是否到达总时长，自动停止
- 测试结束时：保存测试记录、触发报表生成、更新通道状态
- 信号: `testStarted(int channelId)`, `testCompleted(int channelId, TestResult)`

**Step 2: 编译验证**

**Step 3: 提交**

```bash
git add src/core/test_engine/
git commit -m "feat: add TestEngine with state machine for test lifecycle"
```

---

## Phase 7: 仪器控制

### Task 17: 通道管理器

**Files:**
- Create: `src/instrument/channel_manager/ChannelManager.h`
- Create: `src/instrument/channel_manager/ChannelManager.cpp`

**Step 1: 实现 ChannelManager**

- `loadChannels()`: 从数据库加载通道配置（断电恢复）
- `bindProduct(int channelId, const QString& sn, const QString& pn)`: 绑定产品
- `unbindProduct(int channelId)`: 解绑产品
- `powerOn(int channelId)`: 上电（通过插件调用对应控制器）
- `powerOff(int channelId)`: 下电
- `emergencyStop()`: 紧急全部下电
- `getChannelInfo(int channelId)`: 获取通道信息
- `getAllChannels()`: 获取所有通道列表
- 信号: `channelStatusChanged(int channelId, ChannelStatus)`, `bindingChanged(int channelId, QString sn, QString pn)`

上电/下电操作：从 PluginManager 获取对应控制器插件，执行控制指令。

**Step 2: 编译验证**

**Step 3: 提交**

```bash
git add src/instrument/channel_manager/
git commit -m "feat: add ChannelManager with power control and SN binding"
```

---

### Task 18: 扫码枪监听

**Files:**
- Create: `src/instrument/scanner/BarcodeScanner.h`
- Create: `src/instrument/scanner/BarcodeScanner.cpp`

**Step 1: 实现 BarcodeScanner**

- 支持串口和 USB HID 两种接入方式
- 串口模式：通过 QSerialPort 监听，按行读取扫码数据
- USB HID 模式：监听全局键盘事件，捕获扫码枪模拟键盘输入（以回车结尾的一串数字/字母）
- 扫到条码后发射 `barcodeScanned(QString barcode)` 信号
- 需要配置扫码枪的串口参数（波特率、数据位、停止位、校验位）

**Step 2: 编译验证**

**Step 3: 提交**

```bash
git add src/instrument/scanner/
git commit -m "feat: add BarcodeScanner supporting serial and USB HID modes"
```

---

## Phase 8: UI 界面实现

### Task 19: 设备总览页

**Files:**
- Create: `src/ui/device_overview/DeviceOverviewPage.h`
- Create: `src/ui/device_overview/DeviceOverviewPage.cpp`
- Create: `src/ui/device_overview/DeviceCardWidget.h`
- Create: `src/ui/device_overview/DeviceCardWidget.cpp`
- Create: `src/ui/device_overview/StatsBarWidget.h`
- Create: `src/ui/device_overview/StatsBarWidget.cpp`

**Step 1: 创建 StatsBarWidget**

顶部统计卡片栏，显示 4 个数字卡片：在线数、离线数、报警数、测试中数。
订阅 DataBus 的 `deviceStatusChanged` 信号实时更新。

**Step 2: 创建 DeviceCardWidget**

单台设备卡片：
- 显示：设备名称、产品型号、SN、状态（颜色标识）、关键参数（电压/电流/温度）
- 颜色规则：绿色=测试中，黄色=空闲，红色=报警，灰色=离线
- 点击卡片发射 `deviceClicked(int deviceId)` 信号
- 定时刷新显示数据（通过 DataBus 订阅）

**Step 3: 创建 DeviceOverviewPage**

- 顶部：StatsBarWidget
- 筛选栏：状态下拉框 + 产品类型下拉框 + 搜索框
- 中部：QScrollArea 内的 QGridLayout 显示 DeviceCardWidget 网格
- 订阅 DataBus 获取设备列表和状态更新
- 点击卡片导航到设备详情页

**Step 4: 替换 MainWindow 中的 Overview 占位页**

**Step 5: 编译验证，确认卡片动态刷新**

**Step 6: 提交**

```bash
git add src/ui/device_overview/
git commit -m "feat: add DeviceOverviewPage with stats bar and device card grid"
```

---

### Task 20: 设备详情页（含实时曲线）

**Files:**
- Create: `src/ui/device_detail/DeviceDetailPage.h`
- Create: `src/ui/device_detail/DeviceDetailPage.cpp`
- Create: `src/ui/device_detail/RealtimeDataPanel.h`
- Create: `src/ui/device_detail/RealtimeDataPanel.cpp`
- Create: `src/ui/device_detail/CurveChartWidget.h`
- Create: `src/ui/device_detail/CurveChartWidget.cpp`
- Create: `src/ui/device_detail/TestControlPanel.h`
- Create: `src/ui/device_detail/TestControlPanel.cpp`

**Step 1: 集成 QCustomPlot**

将 QCustomPlot 源码加入项目或通过 CMake FetchContent 获取。

**Step 2: 创建 RealtimeDataPanel**

左侧数据面板：
- QTableWidget 显示所有监控参数的当前值
- 每行：参数名、当前值、单位、状态指示灯

**Step 3: 创建 CurveChartWidget**

基于 QCustomPlot 的多通道实时曲线：
- 支持多条曲线（电压/电流/温度/功率）
- 滚动窗口显示最近 N 分钟数据
- 支持缩放（鼠标滚轮）和拖拽
- 图例可点击隐藏/显示某条曲线
- `appendData(paramName, timestamp, value)`: 追加数据点
- `clearData()`: 清空

**Step 4: 创建 TestControlPanel**

底部控制面板：
- 显示当前测试方案信息（模板名、已运行时长、总时长）
- 进度条显示测试进度
- 按钮：启动 / 暂停 / 停止
- 启动前需确认操作

**Step 5: 创建 DeviceDetailPage**

整合以上三个组件，左右布局。订阅 DataBus 更新数据和曲线。
从 MainWindow 导航时传入 deviceId 初始化。

**Step 6: 编译验证实时曲线滚动效果**

**Step 7: 提交**

```bash
git add src/ui/device_detail/
git commit -m "feat: add DeviceDetailPage with realtime QCustomPlot curves and test controls"
```

---

### Task 21: 报警面板

**Files:**
- Create: `src/ui/alarm_panel/AlarmPanelPage.h`
- Create: `src/ui/alarm_panel/AlarmPanelPage.cpp`

**Step 1: 创建 AlarmPanelPage**

- QTableWidget 报警列表，列：时间、设备名称、参数、当前值、阈值、状态
- 按时间倒序排列
- 红色高亮未确认的报警
- "确认"按钮：标记选中报警为已确认
- "全部确认"按钮
- 筛选：全部 / 未确认 / 已确认
- 订阅 DataBus 的 `alarmTriggered` 信号，新报警自动插入列表顶部并闪烁提示

**Step 2: 替换 MainWindow 中的 Alarm 占位页**

**Step 3: 编译验证**

**Step 4: 提交**

```bash
git add src/ui/alarm_panel/
git commit -m "feat: add AlarmPanelPage with real-time alarm list and acknowledge"
```

---

### Task 22: 数据查询页

**Files:**
- Create: `src/ui/data_query/DataQueryPage.h`
- Create: `src/ui/data_query/DataQueryPage.cpp`
- Create: `src/ui/data_query/CurvePlaybackWidget.h`
- Create: `src/ui/data_query/CurvePlaybackWidget.cpp`

**Step 1: 创建 DataQueryPage**

- 查询条件：设备选择（下拉框）、时间范围（日期选择器）、产品类型（可选）
- 查询结果：QTableWidget 显示测试记录列表
- 点击记录查看详情（弹窗或跳转）

**Step 2: 创建 CurvePlaybackWidget**

历史曲线回放：
- 基于查询的历史数据，用 QCustomPlot 绘制
- 支持时间轴缩放和拖拽
- 播放/暂停按钮，按时间回放数据变化过程
- 标注报警点

**Step 3: 替换 MainWindow 中的 DataQuery 占位页**

**Step 4: 编译验证**

**Step 5: 提交**

```bash
git add src/ui/data_query/
git commit -m "feat: add DataQueryPage with history search and curve playback"
```

---

### Task 23: 模板配置页

**Files:**
- Create: `src/ui/template_config/TemplateConfigPage.h`
- Create: `src/ui/template_config/TemplateConfigPage.cpp`
- Create: `src/ui/template_config/TemplateEditDialog.h`
- Create: `src/ui/template_config/TemplateEditDialog.cpp`

**Step 1: 创建 TemplateConfigPage**

- 左侧：模板列表（QListWidget）
- 右侧：选中模板的详细配置展示
- 按钮：新建、编辑、复制、删除

**Step 2: 创建 TemplateEditDialog**

模板编辑对话框：
- 基本信息：名称、适用产品型号
- 采集参数表格：参数名、采样频率（可增删行）
- 测试时长
- 报警阈值表格：参数名、下限、上限、启用（可增删行）
- 测试阶段（可选）：可添加多个阶段，每阶段有名称、时长、阈值配置
- 确定/取消按钮

**Step 3: 编译验证**

**Step 4: 提交**

```bash
git add src/ui/template_config/
git commit -m "feat: add TemplateConfigPage with edit dialog and phase support"
```

---

## Phase 9: 报表生成

### Task 24: PDF 报表生成

**Files:**
- Create: `src/report/PdfReportGenerator.h`
- Create: `src/report/PdfReportGenerator.cpp`

**Step 1: 实现 PdfReportGenerator**

使用 QPrinter + QPainter 绘制 PDF：
- 页眉：公司名、报告标题、生成时间
- 测试信息：设备名称、SN、PN、测试模板、起止时间
- 关键统计数据：最大/最小/平均值（各参数）
- 曲线截图：通过 QCustomPlot 的 `toPixmap()` 导出
- 报警记录列表
- 测试结论：通过/异常/中断
- 页脚：页码

`generateReport(int testRecordId, const QString& filePath)` 接口。

**Step 2: 编译验证，检查生成的 PDF**

**Step 3: 提交**

```bash
git add src/report/PdfReportGenerator.h src/report/PdfReportGenerator.cpp
git commit -m "feat: add PDF report generation with charts and statistics"
```

---

### Task 25: Excel 报表生成

**Files:**
- Create: `src/report/ExcelReportGenerator.h`
- Create: `src/report/ExcelReportGenerator.cpp`

**Step 1: 集成 QXlsx 库**

通过 CMake FetchContent 或直接引入源码。

**Step 2: 实现 ExcelReportGenerator**

使用 QXlsx 生成 Excel：
- Sheet 1 "汇总"：测试基本信息、统计结论
- Sheet 2 "报警记录"：所有报警明细
- Sheet 3 "原始数据"：按时间排列的所有采集数据（列：时间、参数1、参数2...）
- 支持大数据量写入（分批写入避免内存溢出）

**Step 3: 在 DataQueryPage 和 DeviceDetailPage 添加导出按钮**

**Step 4: 编译验证，检查生成的 Excel**

**Step 5: 提交**

```bash
git add src/report/ExcelReportGenerator.h src/report/ExcelReportGenerator.cpp src/CMakeLists.txt
git commit -m "feat: add Excel report generation with QXlsx"
```

---

## Phase 10: 集成与联调

### Task 26: 全流程集成

**Files:**
- Modify: `src/app/Application.cpp`

**Step 1: 在 Application 中初始化所有模块**

按正确顺序初始化：
1. DatabaseManager（存储层）
2. PluginManager（协议插件）
3. DataBus（数据总线）
4. ChannelManager（通道管理）
5. TcpConnectionManager + CanBridge + Rs485Bridge（通信层）
6. AlarmEngine（报警引擎）
7. TemplateManager（模板管理）
8. TestEngine（测试引擎）
9. BarcodeScanner（扫码枪）
10. UI 组件

连接各模块信号槽：
- 通信层 → DataBus
- DataBus → AlarmEngine
- DataBus → UI（各页面）
- BarcodeScanner → ChannelManager
- ChannelManager → TestEngine

**Step 2: 端到端测试**

用模拟数据或真实设备测试完整流程：
扫码绑定 → 选择模板 → 上电启动 → 数据采集 → 报警判定 → 测试结束 → 下电解绑 → 生成报表

**Step 3: 提交**

```bash
git add -A
git commit -m "feat: integrate all modules for end-to-end test flow"
```

---

### Task 27: 导航同步与页面联动

**Files:**
- Modify: `src/ui/main_window/MainWindow.cpp`

**Step 1: 实现页面切换时的导航高亮同步**

点击侧边栏按钮时更新按钮选中状态。

**Step 2: 实现页面间联动**

- 设备总览点击卡片 → 导航到设备详情页
- 报警面板点击报警记录 → 导航到对应设备详情页
- 新报警到达时 → 自动切换到报警面板或弹出提示

**Step 3: 编译验证**

**Step 4: 提交**

```bash
git add src/ui/main_window/
git commit -m "feat: add page navigation sync and cross-page navigation"
```

---

### Task 28: 错误处理与日志系统

**Files:**
- Create: `src/app/Logger.h`
- Create: `src/app/Logger.cpp`

**Step 1: 实现 Logger**

基于 Qt 的日志系统：
- 输出到文件（按天滚动）+ 控制台（调试时）
- 日志级别：DEBUG, INFO, WARNING, ERROR
- 自动记录：通信异常、控制指令、报警事件、测试状态变更
- 使用 `qInstallMessageHandler` 全局拦截 Qt 日志

**Step 2: 在关键路径添加日志**

**Step 3: 编译验证**

**Step 4: 提交**

```bash
git add src/app/Logger.h src/app/Logger.cpp
git commit -m "feat: add file-based logging system with daily rotation"
```

---

## 实现顺序总览

| Phase | 内容 | Tasks |
|-------|------|-------|
| 1 | 项目脚手架与数据模型 | Task 1-3 |
| 2 | 主题与国际化系统 | Task 4-6 |
| 3 | 存储层 | Task 7-8 |
| 4 | 协议接口与插件系统 | Task 9-10 |
| 5 | 通信层 | Task 11-13 |
| 6 | 核心业务逻辑 | Task 14-16 |
| 7 | 仪器控制 | Task 17-18 |
| 8 | UI 界面实现 | Task 19-23 |
| 9 | 报表生成 | Task 24-25 |
| 10 | 集成与联调 | Task 26-28 |
