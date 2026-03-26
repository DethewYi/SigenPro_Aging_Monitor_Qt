#include "MainWindow.h"
#include "ui/settings/SettingsPage.h"
#include "ui/device_overview/DeviceOverviewPage.h"
#include "ui/device_detail/DeviceDetailPage.h"
#include <QHBoxLayout>
#include <QVBoxLayout>
#include <QLabel>
#include <QStatusBar>
#include <QMenuBar>
#include <QButtonGroup>

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
    m_btnSettings = createNavButton(tr("Settings"));

    m_btnOverview->setChecked(true);
}

void MainWindow::setupContentArea()
{
    m_contentStack = new QStackedWidget(this);

    // Page 0: DeviceOverviewPage (real page)
    m_overviewPage = new DeviceOverviewPage(m_contentStack);
    m_contentStack->addWidget(m_overviewPage);

    // Page 1-2: placeholders
    for (int i = 1; i <= 2; ++i) {
        QLabel* placeholder = new QLabel(m_contentStack);
        placeholder->setAlignment(Qt::AlignCenter);
        QFont font;
        font.setPointSize(16);
        placeholder->setFont(font);
        m_contentStack->addWidget(placeholder);
    }

    static_cast<QLabel*>(m_contentStack->widget(m_pageAlarm))->setText(tr("Alarm Panel"));
    static_cast<QLabel*>(m_contentStack->widget(m_pageDataQuery))->setText(tr("Data Query"));

    // Page 3: real SettingsPage
    m_settingsPage = new SettingsPage(m_contentStack);
    m_contentStack->addWidget(m_settingsPage);

    // Page 4: DeviceDetailPage
    m_detailPage = new DeviceDetailPage(m_contentStack);
    m_contentStack->addWidget(m_detailPage);

    // Connect overview page device click signal
    connect(m_overviewPage, &DeviceOverviewPage::deviceClicked,
            this, &MainWindow::onOverviewDeviceClicked);

    // Connect detail page back signal
    connect(m_detailPage, &DeviceDetailPage::backRequested,
            this, &MainWindow::onDetailBackRequested);
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
