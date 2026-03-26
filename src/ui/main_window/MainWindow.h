#pragma once

#include <QMainWindow>
#include <QStackedWidget>
#include <QPushButton>

class SettingsPage;
class DeviceOverviewPage;

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

    QPushButton* m_btnOverview = nullptr;
    QPushButton* m_btnAlarm = nullptr;
    QPushButton* m_btnDataQuery = nullptr;
    QPushButton* m_btnSettings = nullptr;

    DeviceOverviewPage* m_overviewPage = nullptr;
    SettingsPage* m_settingsPage = nullptr;

    int m_pageOverview = 0;
    int m_pageAlarm = 1;
    int m_pageDataQuery = 2;
    int m_pageSettings = 3;
};
