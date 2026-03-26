#pragma once

#include <QWidget>
#include <QMap>
#include "core/common/Types.h"

class StatsBarWidget;
class DeviceCardWidget;
class QComboBox;
class QLineEdit;
class QScrollArea;
class QGridLayout;
struct DeviceData;

class DeviceOverviewPage : public QWidget {
    Q_OBJECT
public:
    explicit DeviceOverviewPage(QWidget* parent = nullptr);

    void refreshDevices();
    void addOrUpdateDevice(int deviceId, const QString& name, const QString& model,
                           const QString& sn, DeviceStatus status);
    void removeDevice(int deviceId);
    void updateDeviceStatus(int deviceId, DeviceStatus status);
    void onDeviceDataUpdated(const DeviceData& data);

signals:
    void deviceClicked(int deviceId);

private slots:
    void onFilterChanged();

private:
    StatsBarWidget* m_statsBar = nullptr;

    // Filters
    QComboBox* m_statusFilter = nullptr;
    QComboBox* m_modelFilter = nullptr;
    QLineEdit* m_searchEdit = nullptr;

    // Device grid
    QScrollArea* m_scrollArea = nullptr;
    QWidget* m_gridWidget = nullptr;
    QGridLayout* m_gridLayout = nullptr;
    QMap<int, DeviceCardWidget*> m_deviceCards;

    QString m_currentStatusFilter;
    QString m_currentModelFilter;
    QString m_currentSearch;

    void setupUI();
    void rebuildGrid();
    bool shouldShowDevice(int deviceId) const;
    bool eventFilter(QObject* watched, QEvent* event) override;
};
