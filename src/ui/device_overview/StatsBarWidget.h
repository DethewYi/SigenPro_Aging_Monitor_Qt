#pragma once

#include <QWidget>

class QLabel;

class StatsBarWidget : public QWidget {
    Q_OBJECT
public:
    explicit StatsBarWidget(QWidget* parent = nullptr);

public slots:
    void updateOnlineCount(int count);
    void updateOfflineCount(int count);
    void updateAlarmCount(int count);
    void updateTestingCount(int count);

private:
    QLabel* createStatCard(const QString& title, const QString& valueText,
                           const QString& accentColor);

    QLabel* m_onlineCount = nullptr;
    QLabel* m_offlineCount = nullptr;
    QLabel* m_alarmCount = nullptr;
    QLabel* m_testingCount = nullptr;
};
