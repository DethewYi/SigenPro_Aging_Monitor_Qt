#pragma once

#include <QObject>
#include "core/common/DeviceData.h"
#include "core/common/AlarmRecord.h"
#include "core/common/Types.h"

class DataBus : public QObject {
    Q_OBJECT
public:
    static DataBus& instance();

    void publishDeviceData(const DeviceData& data);
    void publishAlarm(const AlarmRecord& alarm);
    void publishDeviceStatus(int deviceId, DeviceStatus status);
    void publishRawData(int deviceId, const QByteArray& rawData);

signals:
    void deviceDataReceived(const DeviceData& data);
    void alarmTriggered(const AlarmRecord& alarm);
    void deviceStatusChanged(int deviceId, DeviceStatus status);
    void rawDataReceived(int deviceId, const QByteArray& rawData);

private:
    DataBus() = default;
    DataBus(const DataBus&) = delete;
    DataBus& operator=(const DataBus&) = delete;
};
