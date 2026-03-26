#pragma once
#include <QWidget>

class QTableWidget;
class QComboBox;
class QLabel;

class AlarmPanelPage : public QWidget {
    Q_OBJECT
public:
    explicit AlarmPanelPage(QWidget* parent = nullptr);

public slots:
    void addAlarm(int id, const QString& timestamp, int deviceId,
                  const QString& deviceName, const QString& paramName,
                  double currentValue, double threshold,
                  bool isUpperLimit, bool acknowledged);
    void acknowledgeAlarm(int row);

signals:
    void deviceAlarmClicked(int deviceId);

private slots:
    void onAcknowledgeSelected();
    void onAcknowledgeAll();
    void onFilterChanged();
    void onTableDoubleClicked(int row, int column);

private:
    void setupUI();
    void updateFilterView();

    QTableWidget* m_table = nullptr;
    QComboBox* m_filterCombo = nullptr;
    QLabel* m_totalLabel = nullptr;
    QLabel* m_unackLabel = nullptr;

    enum FilterMode { All = 0, Unacknowledged = 1, Acknowledged = 2 };
};
