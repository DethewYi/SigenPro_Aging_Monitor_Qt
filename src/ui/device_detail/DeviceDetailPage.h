#pragma once

#include <QWidget>

class RealtimeDataPanel;
class CurveChartWidget;
class TestControlPanel;
class QPushButton;
class QLabel;

class DeviceDetailPage : public QWidget {
    Q_OBJECT
public:
    explicit DeviceDetailPage(QWidget* parent = nullptr);

    void setDevice(int deviceId);
    int currentDeviceId() const;

signals:
    void backRequested();

public slots:
    void onDeviceDataReceived(const DeviceData& data);

private:
    int m_deviceId = -1;

    RealtimeDataPanel* m_dataPanel = nullptr;
    CurveChartWidget* m_chartWidget = nullptr;
    TestControlPanel* m_controlPanel = nullptr;
    QPushButton* m_backBtn = nullptr;
    QLabel* m_deviceTitleLabel = nullptr;

    void setupUI();
};
