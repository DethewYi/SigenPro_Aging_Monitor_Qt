#include "communication/tcp/TcpDeviceConnection.h"
#include <QDebug>

TcpDeviceConnection::TcpDeviceConnection(int deviceId, QObject* parent)
    : QObject(parent)
    , m_deviceId(deviceId)
    , m_socket(new QTcpSocket(this))
    , m_heartbeatTimer(new QTimer(this))
    , m_reconnectTimer(new QTimer(this))
{
    m_heartbeatTimer->setSingleShot(false);
    m_reconnectTimer->setSingleShot(true);

    connect(m_socket, &QTcpSocket::connected, this, &TcpDeviceConnection::onConnected);
    connect(m_socket, &QTcpSocket::disconnected, this, &TcpDeviceConnection::onDisconnected);
    connect(m_socket, &QTcpSocket::readyRead, this, &TcpDeviceConnection::onReadyRead);
    connect(m_socket, &QTcpSocket::errorOccurred, this, &TcpDeviceConnection::onSocketError);

    connect(m_heartbeatTimer, &QTimer::timeout, this, &TcpDeviceConnection::onHeartbeatTimeout);
    connect(m_reconnectTimer, &QTimer::timeout, this, &TcpDeviceConnection::onReconnectTimer);
}

TcpDeviceConnection::~TcpDeviceConnection()
{
    disconnectFromHost();
}

void TcpDeviceConnection::connectToHost(const QString& host, int port)
{
    m_host = host;
    m_port = port;
    m_intentionalDisconnect = false;
    m_reconnectAttempts = 0;

    emit connectionStateChanged(m_deviceId, DeviceStatus::Offline);
    m_socket->connectToHost(host, port);
}

void TcpDeviceConnection::disconnectFromHost()
{
    m_intentionalDisconnect = true;
    stopHeartbeat();
    stopReconnectTimer();

    if (m_socket->state() != QAbstractSocket::UnconnectedState) {
        m_socket->disconnectFromHost();
    }
}

void TcpDeviceConnection::sendData(const QByteArray& data)
{
    if (m_socket && m_socket->state() == QAbstractSocket::ConnectedState) {
        m_socket->write(data);
        if (!m_socket->waitForBytesWritten(1000)) {
            qWarning() << "TcpDeviceConnection: Failed to write data to device"
                       << m_deviceId << "-" << m_socket->errorString();
        }
    }
}

bool TcpDeviceConnection::isConnected() const
{
    return m_socket && m_socket->state() == QAbstractSocket::ConnectedState;
}

int TcpDeviceConnection::deviceId() const
{
    return m_deviceId;
}

void TcpDeviceConnection::onConnected()
{
    qDebug() << "TcpDeviceConnection: Device" << m_deviceId
             << "connected to" << m_host << ":" << m_port;

    m_reconnectAttempts = 0;
    stopReconnectTimer();
    m_readBuffer.clear();
    startHeartbeat();

    emit connectionStateChanged(m_deviceId, DeviceStatus::Idle);
}

void TcpDeviceConnection::onDisconnected()
{
    qDebug() << "TcpDeviceConnection: Device" << m_deviceId << "disconnected";

    stopHeartbeat();

    if (!m_intentionalDisconnect) {
        emit connectionStateChanged(m_deviceId, DeviceStatus::Offline);
        startReconnectTimer();
    }
}

void TcpDeviceConnection::onReadyRead()
{
    m_readBuffer.append(m_socket->readAll());

    // Process complete frames from the buffer.
    // The actual frame protocol parsing is handled by the protocol layer.
    // Here we emit all available data for each read cycle.
    // The protocol parser will handle frame delimiting.
    // However, to keep the connection layer generic, we forward raw data
    // and let higher layers handle framing.
    if (!m_readBuffer.isEmpty()) {
        emit dataReceived(m_deviceId, m_readBuffer);
        m_readBuffer.clear();
    }
}

void TcpDeviceConnection::onSocketError(QAbstractSocket::SocketError error)
{
    Q_UNUSED(error)
    QString errorMsg = m_socket->errorString();
    qWarning() << "TcpDeviceConnection: Device" << m_deviceId
               << "socket error:" << errorMsg;

    emit errorOccurred(m_deviceId, errorMsg);
}

void TcpDeviceConnection::onHeartbeatTimeout()
{
    if (m_socket && m_socket->state() == QAbstractSocket::ConnectedState) {
        // Send heartbeat ping packet: 0xAA 0x55
        QByteArray heartbeat;
        heartbeat.append(static_cast<char>(0xAA));
        heartbeat.append(static_cast<char>(0x55));

        m_socket->write(heartbeat);
        qDebug() << "TcpDeviceConnection: Heartbeat sent to device" << m_deviceId;

        // Start a single-shot timer to check for response.
        // If the response timer fires before any data is read, consider
        // the connection dead and reconnect.
        QTimer::singleShot(HEARTBEAT_TIMEOUT_MS, this, [this]() {
            if (m_socket && m_socket->state() == QAbstractSocket::ConnectedState) {
                qWarning() << "TcpDeviceConnection: Heartbeat timeout for device"
                           << m_deviceId << "- connection may be dead";
                // Force disconnect to trigger reconnection
                m_socket->abort();
            }
        });
    }
}

void TcpDeviceConnection::onReconnectTimer()
{
    if (m_reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
        qWarning() << "TcpDeviceConnection: Max reconnect attempts (" << MAX_RECONNECT_ATTEMPTS
                   << ") reached for device" << m_deviceId;
        emit connectionStateChanged(m_deviceId, DeviceStatus::Fault);
        return;
    }

    qDebug() << "TcpDeviceConnection: Reconnecting device" << m_deviceId
             << "- attempt" << (m_reconnectAttempts + 1) << "/"
             << MAX_RECONNECT_ATTEMPTS;

    m_intentionalDisconnect = false;
    m_socket->connectToHost(m_host, m_port);
}

void TcpDeviceConnection::startHeartbeat()
{
    m_heartbeatTimer->start(HEARTBEAT_INTERVAL_MS);
}

void TcpDeviceConnection::stopHeartbeat()
{
    m_heartbeatTimer->stop();
}

void TcpDeviceConnection::startReconnectTimer()
{
    // Exponential backoff: interval = min(INITIAL * 2^attempts, MAX)
    int interval = INITIAL_RECONNECT_INTERVAL_MS * (1 << m_reconnectAttempts);
    if (interval > MAX_RECONNECT_INTERVAL_MS) {
        interval = MAX_RECONNECT_INTERVAL_MS;
    }

    m_reconnectAttempts++;
    m_reconnectTimer->start(interval);

    qDebug() << "TcpDeviceConnection: Reconnect timer started for device"
             << m_deviceId << "- next attempt in" << interval << "ms";
}

void TcpDeviceConnection::stopReconnectTimer()
{
    m_reconnectTimer->stop();
}
