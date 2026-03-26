#include "communication/tcp/TcpConnectionManager.h"
#include <QDebug>

TcpConnectionManager::TcpConnectionManager(QObject* parent)
    : QObject(parent)
{
}

TcpConnectionManager::~TcpConnectionManager()
{
    // Disconnect and remove all devices
    for (auto it = m_connections.begin(); it != m_connections.end(); ++it) {
        if (it.value()) {
            it.value()->disconnectFromHost();
            it.value()->deleteLater();
        }
    }
    m_connections.clear();
    m_deviceConfigs.clear();
}

bool TcpConnectionManager::addDevice(const DeviceConfig& config)
{
    if (config.deviceId < 0) {
        qWarning() << "TcpConnectionManager: Invalid device ID:" << config.deviceId;
        return false;
    }

    if (m_connections.contains(config.deviceId)) {
        qWarning() << "TcpConnectionManager: Device already exists:" << config.deviceId;
        return false;
    }

    auto* connection = new TcpDeviceConnection(config.deviceId, this);

    connect(connection, &TcpDeviceConnection::dataReceived,
            this, &TcpConnectionManager::onDataReceived);
    connect(connection, &TcpDeviceConnection::connectionStateChanged,
            this, &TcpConnectionManager::onConnectionStateChanged);

    m_connections.insert(config.deviceId, connection);
    m_deviceConfigs.insert(config.deviceId, config);

    connection->connectToHost(config.ipAddress, config.port);

    qDebug() << "TcpConnectionManager: Added device" << config.deviceId
             << "at" << config.ipAddress << ":" << config.port;

    return true;
}

void TcpConnectionManager::removeDevice(int deviceId)
{
    if (!m_connections.contains(deviceId)) {
        qWarning() << "TcpConnectionManager: Device not found:" << deviceId;
        return;
    }

    auto* connection = m_connections.take(deviceId);
    m_deviceConfigs.remove(deviceId);

    if (connection) {
        connection->disconnectFromHost();
        connection->deleteLater();
    }

    qDebug() << "TcpConnectionManager: Removed device" << deviceId;
}

void TcpConnectionManager::sendCommand(int deviceId, const QByteArray& cmd)
{
    auto it = m_connections.find(deviceId);
    if (it == m_connections.end()) {
        qWarning() << "TcpConnectionManager: Cannot send command - device not found:"
                   << deviceId;
        return;
    }

    it.value()->sendData(cmd);
}

bool TcpConnectionManager::isDeviceConnected(int deviceId) const
{
    auto it = m_connections.find(deviceId);
    if (it == m_connections.end()) {
        return false;
    }
    return it.value()->isConnected();
}

QList<int> TcpConnectionManager::connectedDeviceIds() const
{
    QList<int> result;
    for (auto it = m_connections.begin(); it != m_connections.end(); ++it) {
        if (it.value()->isConnected()) {
            result.append(it.key());
        }
    }
    return result;
}

void TcpConnectionManager::onDataReceived(int deviceId, const QByteArray& data)
{
    emit deviceDataReceived(deviceId, data);
}

void TcpConnectionManager::onConnectionStateChanged(int deviceId, DeviceStatus status)
{
    emit deviceStatusChanged(deviceId, status);
}
