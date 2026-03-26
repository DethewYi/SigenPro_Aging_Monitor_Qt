#include "communication/rs485/Rs485Bridge.h"
#include <QDebug>

Rs485Bridge::Rs485Bridge(QObject* parent)
    : QObject(parent)
{
}

Rs485Bridge::~Rs485Bridge()
{
    disconnectNetwork();
    disconnectSerial();
}

// --- Network mode ---

bool Rs485Bridge::connectNetwork(const QString& host, int port)
{
    disconnectSerial();

    if (!m_tcpSocket) {
        m_tcpSocket = new QTcpSocket(this);
        connect(m_tcpSocket, &QTcpSocket::connected, this, &Rs485Bridge::onTcpConnected);
        connect(m_tcpSocket, &QTcpSocket::disconnected, this, &Rs485Bridge::onTcpDisconnected);
        connect(m_tcpSocket, &QTcpSocket::readyRead, this, &Rs485Bridge::onTcpReadyRead);
        connect(m_tcpSocket, &QTcpSocket::errorOccurred, this, &Rs485Bridge::onTcpError);
    }

    m_mode = NetworkMode;
    m_readBuffer.clear();

    qDebug() << "Rs485Bridge: Connecting to serial server at" << host << "port" << port;
    emit connectionStateChanged(DeviceStatus::Offline);
    m_tcpSocket->connectToHost(host, port);

    return true;
}

void Rs485Bridge::disconnectNetwork()
{
    if (m_tcpSocket) {
        if (m_tcpSocket->state() != QAbstractSocket::UnconnectedState) {
            m_tcpSocket->disconnectFromHost();
        }
        m_tcpSocket->deleteLater();
        m_tcpSocket = nullptr;
    }
    m_readBuffer.clear();
}

// --- Serial mode ---

bool Rs485Bridge::connectSerial(const QString& portName, int baudRate,
                                int dataBits, int stopBits, int parity)
{
    disconnectNetwork();

    if (!m_serialPort) {
        m_serialPort = new QSerialPort(this);
        connect(m_serialPort, &QSerialPort::readyRead, this, &Rs485Bridge::onSerialReadyRead);
        connect(m_serialPort, &QSerialPort::errorOccurred, this, &Rs485Bridge::onSerialError);
    }

    m_mode = SerialMode;
    m_readBuffer.clear();

    m_serialPort->setPortName(portName);
    m_serialPort->setBaudRate(baudRate);
    m_serialPort->setDataBits(static_cast<QSerialPort::DataBits>(dataBits));
    m_serialPort->setStopBits(static_cast<QSerialPort::StopBits>(stopBits));
    m_serialPort->setParity(static_cast<QSerialPort::Parity>(parity));

    qDebug() << "Rs485Bridge: Opening serial port" << portName
             << "baud=" << baudRate << "data=" << dataBits
             << "stop=" << stopBits << "parity=" << parity;

    emit connectionStateChanged(DeviceStatus::Offline);

    if (!m_serialPort->open(QIODevice::ReadOnly)) {
        qWarning() << "Rs485Bridge: Failed to open serial port" << portName
                   << "-" << m_serialPort->errorString();
        return false;
    }

    emit connectionStateChanged(DeviceStatus::Idle);
    return true;
}

void Rs485Bridge::disconnectSerial()
{
    if (m_serialPort) {
        if (m_serialPort->isOpen()) {
            m_serialPort->close();
        }
        m_serialPort->deleteLater();
        m_serialPort = nullptr;
    }
    m_readBuffer.clear();
}

// --- Send data ---

void Rs485Bridge::sendData(const QByteArray& data)
{
    if (m_mode == NetworkMode && m_tcpSocket &&
        m_tcpSocket->state() == QAbstractSocket::ConnectedState) {
        m_tcpSocket->write(data);
    } else if (m_mode == SerialMode && m_serialPort && m_serialPort->isOpen()) {
        m_serialPort->write(data);
    }
}

bool Rs485Bridge::isConnected() const
{
    if (m_mode == NetworkMode) {
        return m_tcpSocket && m_tcpSocket->state() == QAbstractSocket::ConnectedState;
    } else {
        return m_serialPort && m_serialPort->isOpen();
    }
}

// --- TCP slots ---

void Rs485Bridge::onTcpConnected()
{
    qDebug() << "Rs485Bridge: Connected to serial server (network mode)";
    m_readBuffer.clear();
    emit connectionStateChanged(DeviceStatus::Idle);
}

void Rs485Bridge::onTcpDisconnected()
{
    qDebug() << "Rs485Bridge: Disconnected from serial server (network mode)";
    emit connectionStateChanged(DeviceStatus::Offline);
}

void Rs485Bridge::onTcpReadyRead()
{
    m_readBuffer.append(m_tcpSocket->readAll());
    parseFrames();
}

void Rs485Bridge::onTcpError(QAbstractSocket::SocketError error)
{
    Q_UNUSED(error)
    qWarning() << "Rs485Bridge: TCP error:" << m_tcpSocket->errorString();
}

// --- Serial slots ---

void Rs485Bridge::onSerialReadyRead()
{
    m_readBuffer.append(m_serialPort->readAll());
    parseFrames();
}

void Rs485Bridge::onSerialError(QSerialPort::SerialPortError error)
{
    if (error != QSerialPort::NoError && error != QSerialPort::ResourceError) {
        qWarning() << "Rs485Bridge: Serial port error:" << m_serialPort->errorString();
    }

    if (error == QSerialPort::ResourceError) {
        qWarning() << "Rs485Bridge: Serial port resource error, port may have been removed";
        emit connectionStateChanged(DeviceStatus::Fault);
    }
}

// --- Frame parsing ---

void Rs485Bridge::parseFrames()
{
    // RS485 frame delimiter: 0x0D 0x0A (CRLF)
    while (true) {
        int delimiterPos = m_readBuffer.indexOf("\r\n");
        if (delimiterPos < 0) {
            break;
        }

        // Extract the frame data (everything before the delimiter)
        QByteArray frameData = m_readBuffer.left(delimiterPos);
        m_readBuffer.remove(0, delimiterPos + 2); // +2 for CRLF

        if (!frameData.isEmpty()) {
            emit dataReceived(frameData);
        }
    }

    // Safety: prevent unbounded buffer growth
    if (m_readBuffer.size() > 65536) {
        qWarning() << "Rs485Bridge: Read buffer overflow, clearing" << m_readBuffer.size() << "bytes";
        m_readBuffer.clear();
    }
}
