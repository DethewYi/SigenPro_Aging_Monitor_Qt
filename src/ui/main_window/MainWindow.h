#pragma once

#include <QMainWindow>
#include <QStackedWidget>
#include <QPushButton>

class SettingsPage;
class DeviceOverviewPage;
class DeviceDetailPage;
class AlarmPanelPage;
class DataQueryPage;
class TemplateConfigPage;

class MainWindow : public QMainWindow {
    Q_OBJECT
public:
    explicit MainWindow(QWidget* parent = nullptr);
    ~MainWindow() = default;

    void showDeviceDetail(int deviceId);
    void showOverviewPage();

private:
    void setupUI();
    void setupMenuBar();
    void setupSideNavigation();
    void setupContentArea();
    void setupDataBusConnections();

    QWidget* m_sideNav = nullptr;
    QStackedWidget* m_contentStack = nullptr;

    QPushButton* m_btnOverview = nullptr;
    QPushButton* m_btnAlarm = nullptr;
    QPushButton* m_btnDataQuery = nullptr;
    QPushButton* m_btnSettings = nullptr;
    QPushButton* m_btnTemplateConfig = nullptr;

    DeviceOverviewPage* m_overviewPage = nullptr;
    AlarmPanelPage* m_alarmPage = nullptr;
    DataQueryPage* m_dataQueryPage = nullptr;
    SettingsPage* m_settingsPage = nullptr;
    DeviceDetailPage* m_detailPage = nullptr;
    TemplateConfigPage* m_templateConfigPage = nullptr;

    int m_pageOverview = 0;
    int m_pageAlarm = 1;
    int m_pageDataQuery = 2;
    int m_pageSettings = 3;
    int m_pageDetail = 4;
    int m_pageTemplateConfig = 5;

private slots:
    void onOverviewDeviceClicked(int deviceId);
    void onDetailBackRequested();
    void onStackedPageChanged(int index);
};
