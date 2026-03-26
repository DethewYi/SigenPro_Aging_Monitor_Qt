#pragma once

#include <QObject>
#include <QTcpSocket>
#include <QTimer>
#include <QDateTime>
#include "core/common/Types.h"

class TcpDeviceConnection : public QObject {
    Q_OBJECT
public:
    explicit TcpDeviceConnection(int deviceId, QObject* parent = nullptr);
    ~TcpDeviceConnection();

    void connectToHost(const QString& host, int port);
    void disconnectFromHost();
    void sendData(const QByteArray& data);
    bool isConnected() const;
    int deviceId() const;

signals:
    void dataReceived(int deviceId, const QByteArray& data);
    void connectionStateChanged(int deviceId, DeviceStatus status);
    void errorOccurred(int deviceId, const QString& error);

private slots:
    void onConnected();
    void onDisconnected();
    void onReadyRead();
    void onSocketError(QAbstractSocket::SocketError error);
    void onHeartbeatTimeout();
    void onReconnectTimer();

private:
    void startHeartbeat();
    void stopHeartbeat();
    void startReconnectTimer();
    void stopReconnectTimer();

    int m_deviceId = -1;
    QTcpSocket* m_socket = nullptr;
    QTimer* m_heartbeatTimer = nullptr;
    QTimer* m_reconnectTimer = nullptr;

    QString m_host;
    int m_port = 0;

    // Reconnection
    int m_reconnectAttempts = 0;
    static constexpr int MAX_RECONNECT_ATTEMPTS = 10;
    static constexpr int INITIAL_RECONNECT_INTERVAL_MS = 1000; // 1 second
    static constexpr int MAX_RECONNECT_INTERVAL_MS = 60000;   // 60 seconds

    // Heartbeat
    static constexpr int HEARTBEAT_INTERVAL_MS = 30000; // 30 seconds
    static constexpr int HEARTBEAT_TIMEOUT_MS = 10000;  // 10 seconds

    // Data buffer
    QByteArray m_readBuffer;

    bool m_intentionalDisconnect = false;
};
