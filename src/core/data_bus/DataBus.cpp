#include "core/data_bus/DataBus.h"
#include <QDebug>

DataBus& DataBus::instance()
{
    static DataBus instance;
    return instance;
}

void DataBus::publishDeviceData(const DeviceData& data)
{
    emit deviceDataReceived(data);
}

void DataBus::publishAlarm(const AlarmRecord& alarm)
{
    qDebug() << "DataBus: Alarm triggered - device" << alarm.deviceName
             << "param" << alarm.paramName
             << "value" << alarm.currentValue
             << (alarm.isUpperLimit ? "> upper" : "< lower")
             << "threshold" << alarm.threshold;

    emit alarmTriggered(alarm);
}

void DataBus::publishDeviceStatus(int deviceId, DeviceStatus status)
{
    emit deviceStatusChanged(deviceId, status);
}

void DataBus::publishRawData(int deviceId, const QByteArray& rawData)
{
    emit rawDataReceived(deviceId, rawData);
}
