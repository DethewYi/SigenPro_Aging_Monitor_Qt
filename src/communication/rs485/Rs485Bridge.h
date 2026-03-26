#pragma once

#include <QObject>
#include <QTcpSocket>
#include <QSerialPort>
#include "core/common/Types.h"

class Rs485Bridge : public QObject {
    Q_OBJECT
public:
    enum Mode { NetworkMode, SerialMode };

    explicit Rs485Bridge(QObject* parent = nullptr);
    ~Rs485Bridge();

    // Network mode
    bool connectNetwork(const QString& host, int port);
    void disconnectNetwork();

    // Serial mode
    bool connectSerial(const QString& portName, int baudRate = 9600,
                       int dataBits = 8, int stopBits = 1, int parity = 0);
    void disconnectSerial();

    void sendData(const QByteArray& data);
    bool isConnected() const;

signals:
    void dataReceived(const QByteArray& data);
    void connectionStateChanged(DeviceStatus status);

private slots:
    void onTcpConnected();
    void onTcpDisconnected();
    void onTcpReadyRead();
    void onTcpError(QAbstractSocket::SocketError error);
    void onSerialReadyRead();
    void onSerialError(QSerialPort::SerialPortError error);

private:
    void parseFrames();

    Mode m_mode = NetworkMode;
    QTcpSocket* m_tcpSocket = nullptr;
    QSerialPort* m_serialPort = nullptr;
    QByteArray m_readBuffer;
};
