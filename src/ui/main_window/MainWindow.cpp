#include "MainWindow.h"
#include "ui/settings/SettingsPage.h"
#include "ui/device_overview/DeviceOverviewPage.h"
#include "ui/device_detail/DeviceDetailPage.h"
#include "ui/alarm_panel/AlarmPanelPage.h"
#include "ui/data_query/DataQueryPage.h"
#include "ui/template_config/TemplateConfigPage.h"
#include "core/data_bus/DataBus.h"
#include "core/common/DeviceData.h"
#include "core/common/AlarmRecord.h"
#include "report/PdfReportGenerator.h"
#include "report/ExcelReportGenerator.h"
#include <QHBoxLayout>
#include <QVBoxLayout>
#include <QLabel>
#include <QStatusBar>
#include <QMenuBar>
#include <QButtonGroup>
#include <QFileDialog>

MainWindow::MainWindow(QWidget* parent)
    : QMainWindow(parent)
{
    setWindowTitle(tr("SigenPro Aging Monitor"));
    resize(1400, 900);
    setupUI();
    setupMenuBar();
    setupDataBusConnections();
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

    QMenu* fileMenu = menuBar->addMenu(tr("&File"));
    fileMenu->addAction(tr("&Settings"), this, [this]() {
        m_contentStack->setCurrentIndex(m_pageSettings);
        m_btnSettings->setChecked(true);
    });
    fileMenu->addSeparator();
    fileMenu->addAction(tr("E&xit"), this, &QWidget::close);

    QMenu* viewMenu = menuBar->addMenu(tr("&View"));
    viewMenu->addAction(tr("Device &Overview"), this, [this]() {
        showOverviewPage();
    });
    viewMenu->addAction(tr("&Alarms"), this, [this]() {
        m_contentStack->setCurrentIndex(m_pageAlarm);
        m_btnAlarm->setChecked(true);
    });
    viewMenu->addAction(tr("&Data Query"), this, [this]() {
        m_contentStack->setCurrentIndex(m_pageDataQuery);
        m_btnDataQuery->setChecked(true);
    });
    viewMenu->addSeparator();
    viewMenu->addAction(tr("&Template Management"), this, [this]() {
        m_contentStack->setCurrentIndex(m_pageTemplateConfig);
        m_btnTemplateConfig->setChecked(true);
        m_btnOverview->setChecked(false);
        m_btnAlarm->setChecked(false);
        m_btnDataQuery->setChecked(false);
        m_btnSettings->setChecked(false);
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

    // Use a QButtonGroup to ensure mutual exclusivity among checkable buttons
    QButtonGroup* navGroup = new QButtonGroup(this);
    navGroup->setExclusive(true);

    auto createNavButton = [&](const QString& text) -> QPushButton* {
        QPushButton* btn = new QPushButton(text, m_sideNav);
        btn->setCheckable(true);
        btn->setFixedHeight(44);
        btn->setCursor(Qt::PointingHandCursor);
        navGroup->addButton(btn);
        layout->addWidget(btn);
        return btn;
    };

    m_btnOverview = createNavButton(tr("Device Overview"));
    m_btnAlarm = createNavButton(tr("Alarms"));
    m_btnDataQuery = createNavButton(tr("Data Query"));
    layout->addStretch();
    m_btnTemplateConfig = createNavButton(tr("Template Mgmt"));
    m_btnSettings = createNavButton(tr("Settings"));

    m_btnOverview->setChecked(true);
}

void MainWindow::setupContentArea()
{
    m_contentStack = new QStackedWidget(this);

    // Page 0: DeviceOverviewPage (real page)
    m_overviewPage = new DeviceOverviewPage(m_contentStack);
    m_contentStack->addWidget(m_overviewPage);

    // Page 1: AlarmPanelPage
    m_alarmPage = new AlarmPanelPage(m_contentStack);
    m_contentStack->addWidget(m_alarmPage);

    // Page 2: DataQueryPage
    m_dataQueryPage = new DataQueryPage(m_contentStack);
    m_contentStack->addWidget(m_dataQueryPage);

    // Page 3: real SettingsPage
    m_settingsPage = new SettingsPage(m_contentStack);
    m_contentStack->addWidget(m_settingsPage);

    // Page 4: DeviceDetailPage
    m_detailPage = new DeviceDetailPage(m_contentStack);
    m_contentStack->addWidget(m_detailPage);

    // Page 5: TemplateConfigPage
    m_templateConfigPage = new TemplateConfigPage(m_contentStack);
    m_contentStack->addWidget(m_templateConfigPage);

    // Connect overview page device click signal
    connect(m_overviewPage, &DeviceOverviewPage::deviceClicked,
            this, &MainWindow::onOverviewDeviceClicked);

    // Connect detail page back signal
    connect(m_detailPage, &DeviceDetailPage::backRequested,
            this, &MainWindow::onDetailBackRequested);

    // Connect alarm page device click signal
    connect(m_alarmPage, &AlarmPanelPage::deviceAlarmClicked,
            this, &MainWindow::showDeviceDetail);

    // Connect data query page navigation signal
    connect(m_dataQueryPage, &DataQueryPage::navigateToDeviceDetail,
            this, &MainWindow::showDeviceDetail);

    // Connect template config page navigation button
    connect(m_btnTemplateConfig, &QPushButton::clicked, this, [this]() {
        m_contentStack->setCurrentIndex(m_pageTemplateConfig);
        m_templateConfigPage->refreshList();
    });

    // Connect QStackedWidget currentChanged to update nav button highlighting
    connect(m_contentStack, &QStackedWidget::currentChanged,
            this, &MainWindow::onStackedPageChanged);
}

void MainWindow::setupDataBusConnections()
{
    // Connect DataBus device status changes -> DeviceOverviewPage
    connect(&DataBus::instance(), &DataBus::deviceStatusChanged,
            m_overviewPage, [this](int deviceId, DeviceStatus status) {
        Q_UNUSED(this);
        m_overviewPage->updateDeviceStatus(deviceId, status);
    });

    // Connect DataBus device data -> DeviceOverviewPage (for parameter display on cards)
    connect(&DataBus::instance(), &DataBus::deviceDataReceived,
            m_overviewPage, [this](const DeviceData& data) {
        Q_UNUSED(this);
        // Update the card's parameter display when data arrives
        // DeviceOverviewPage::addOrUpdateDevice can be used to refresh card info
        m_overviewPage->onDeviceDataUpdated(data);
    });

    // Connect DataBus alarm triggered -> AlarmPanelPage
    connect(&DataBus::instance(), &DataBus::alarmTriggered,
            m_alarmPage, [this](const AlarmRecord& alarm) {
        Q_UNUSED(this);
        m_alarmPage->addAlarm(alarm.id, alarm.timestamp.toString("yyyy-MM-dd HH:mm:ss"),
                              alarm.deviceId, alarm.deviceName, alarm.paramName,
                              alarm.currentValue, alarm.threshold,
                              alarm.isUpperLimit, alarm.acknowledged);
    });

    // Connect DataBus device data -> DeviceDetailPage
    connect(&DataBus::instance(), &DataBus::deviceDataReceived,
            m_detailPage, &DeviceDetailPage::onDeviceDataReceived);

    // Connect export buttons from DataQueryPage to report generators
    connect(m_dataQueryPage, &DataQueryPage::exportPdfRequested, this, [this](int recordId) {
        Q_UNUSED(this);
        QString path = QFileDialog::getSaveFileName(this, tr("Save PDF Report"),
            QDateTime::currentDateTime().toString("yyyyMMdd_HHmmss") + "_report.pdf",
            "PDF Files (*.pdf)");
        if (!path.isEmpty()) {
            PdfReportGenerator gen;
            gen.generateReport(recordId, path);
            statusBar()->showMessage(tr("PDF report exported: %1").arg(path), 5000);
        }
    });

    connect(m_dataQueryPage, &DataQueryPage::exportExcelRequested, this, [this](int recordId) {
        Q_UNUSED(this);
        QString path = QFileDialog::getSaveFileName(this, tr("Save Excel Report"),
            QDateTime::currentDateTime().toString("yyyyMMdd_HHmmss") + "_report.csv",
            "CSV Files (*.csv);;Excel Files (*.xlsx)");
        if (!path.isEmpty()) {
            ExcelReportGenerator gen;
            gen.generateReport(recordId, path);
            statusBar()->showMessage(tr("Excel report exported: %1").arg(path), 5000);
        }
    });
}

void MainWindow::showDeviceDetail(int deviceId)
{
    m_detailPage->setDevice(deviceId);
    m_contentStack->setCurrentIndex(m_pageDetail);
    // Uncheck all nav buttons (detail page is not a nav target)
    m_btnOverview->setChecked(false);
    m_btnAlarm->setChecked(false);
    m_btnDataQuery->setChecked(false);
    m_btnSettings->setChecked(false);
    m_btnTemplateConfig->setChecked(false);
}

void MainWindow::showOverviewPage()
{
    m_contentStack->setCurrentIndex(m_pageOverview);
    m_btnOverview->setChecked(true);
}

void MainWindow::onOverviewDeviceClicked(int deviceId)
{
    showDeviceDetail(deviceId);
}

void MainWindow::onDetailBackRequested()
{
    showOverviewPage();
}

void MainWindow::onStackedPageChanged(int index)
{
    // Uncheck all nav buttons first
    m_btnOverview->setChecked(false);
    m_btnAlarm->setChecked(false);
    m_btnDataQuery->setChecked(false);
    m_btnSettings->setChecked(false);
    m_btnTemplateConfig->setChecked(false);

    // Check the corresponding button based on the page index
    switch (index) {
    case m_pageOverview:
        m_btnOverview->setChecked(true);
        break;
    case m_pageAlarm:
        m_btnAlarm->setChecked(true);
        break;
    case m_pageDataQuery:
        m_btnDataQuery->setChecked(true);
        break;
    case m_pageSettings:
        m_btnSettings->setChecked(true);
        break;
    case m_pageTemplateConfig:
        m_btnTemplateConfig->setChecked(true);
        break;
    default:
        break; // Detail page or other -- no nav button to highlight
    }
}
