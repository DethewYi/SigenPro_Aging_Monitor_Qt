#pragma once

#include <QObject>
#include <QMap>
#include "core/common/Types.h"
#include "core/common/DeviceData.h"
#include "communication/tcp/TcpDeviceConnection.h"

class TcpConnectionManager : public QObject {
    Q_OBJECT
public:
    explicit TcpConnectionManager(QObject* parent = nullptr);
    ~TcpConnectionManager();

    bool addDevice(const DeviceConfig& config);
    void removeDevice(int deviceId);
    void sendCommand(int deviceId, const QByteArray& cmd);
    bool isDeviceConnected(int deviceId) const;
    QList<int> connectedDeviceIds() const;

signals:
    void deviceDataReceived(int deviceId, const QByteArray& rawData);
    void deviceStatusChanged(int deviceId, DeviceStatus status);

private slots:
    void onDataReceived(int deviceId, const QByteArray& data);
    void onConnectionStateChanged(int deviceId, DeviceStatus status);

private:
    QMap<int, TcpDeviceConnection*> m_connections;
    QMap<int, DeviceConfig> m_deviceConfigs;
};
