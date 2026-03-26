#pragma once

#include <QObject>
#include <QTcpSocket>
#include "core/common/Types.h"

class CanBridge : public QObject {
    Q_OBJECT
public:
    explicit CanBridge(QObject* parent = nullptr);
    ~CanBridge();

    void connectToConverter(const QString& host, int port);
    void disconnectFromConverter();
    bool isConnected() const;

signals:
    void canFrameReceived(int deviceId, const QByteArray& frameData);
    void connectionStateChanged(DeviceStatus status);

private slots:
    void onConnected();
    void onDisconnected();
    void onReadyRead();
    void onSocketError(QAbstractSocket::SocketError error);

private:
    void parseFrames();

    QTcpSocket* m_socket = nullptr;
    QByteArray m_readBuffer;

    QString m_host;
    int m_port = 0;
    bool m_intentionalDisconnect = false;
};
