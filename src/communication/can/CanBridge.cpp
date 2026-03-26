#include "communication/can/CanBridge.h"
#include <QDebug>

CanBridge::CanBridge(QObject* parent)
    : QObject(parent)
    , m_socket(new QTcpSocket(this))
{
    connect(m_socket, &QTcpSocket::connected, this, &CanBridge::onConnected);
    connect(m_socket, &QTcpSocket::disconnected, this, &CanBridge::onDisconnected);
    connect(m_socket, &QTcpSocket::readyRead, this, &CanBridge::onReadyRead);
    connect(m_socket, &QTcpSocket::errorOccurred, this, &CanBridge::onSocketError);
}

CanBridge::~CanBridge()
{
    disconnectFromConverter();
}

void CanBridge::connectToConverter(const QString& host, int port)
{
    m_host = host;
    m_port = port;
    m_intentionalDisconnect = false;

    qDebug() << "CanBridge: Connecting to CAN converter at" << host << "port" << port;
    emit connectionStateChanged(DeviceStatus::Offline);
    m_socket->connectToHost(host, port);
}

void CanBridge::disconnectFromConverter()
{
    m_intentionalDisconnect = true;

    if (m_socket->state() != QAbstractSocket::UnconnectedState) {
        m_socket->disconnectFromHost();
    }
    m_readBuffer.clear();
}

bool CanBridge::isConnected() const
{
    return m_socket && m_socket->state() == QAbstractSocket::ConnectedState;
}

void CanBridge::onConnected()
{
    qDebug() << "CanBridge: Connected to CAN converter at" << m_host << ":" << m_port;
    m_readBuffer.clear();
    emit connectionStateChanged(DeviceStatus::Idle);
}

void CanBridge::onDisconnected()
{
    qDebug() << "CanBridge: Disconnected from CAN converter";
    if (!m_intentionalDisconnect) {
        emit connectionStateChanged(DeviceStatus::Offline);
    }
}

void CanBridge::onReadyRead()
{
    m_readBuffer.append(m_socket->readAll());
    parseFrames();
}

void CanBridge::onSocketError(QAbstractSocket::SocketError error)
{
    Q_UNUSED(error)
    qWarning() << "CanBridge: Socket error:" << m_socket->errorString();
}

void CanBridge::parseFrames()
{
    // CAN frame format from converter:
    //   Device ID (2 bytes, big-endian)
    //   Frame length (1 byte)
    //   Frame data (N bytes)
    //   Delimiter: 0x0D 0x0A (CRLF)

    static constexpr int HEADER_SIZE = 3; // 2 bytes device ID + 1 byte length
    static constexpr int DELIMITER_SIZE = 2; // CR + LF

    while (m_readBuffer.size() >= HEADER_SIZE) {
        // Look for the next complete frame
        // Minimum frame: HEADER_SIZE + 0 data + DELIMITER_SIZE = 5 bytes
        int frameLength = static_cast<unsigned char>(m_readBuffer[2]);
        int totalSize = HEADER_SIZE + frameLength + DELIMITER_SIZE;

        if (m_readBuffer.size() < totalSize) {
            // Not enough data yet, wait for more
            break;
        }

        // Verify delimiter
        if (static_cast<unsigned char>(m_readBuffer[HEADER_SIZE + frameLength]) != 0x0D ||
            static_cast<unsigned char>(m_readBuffer[HEADER_SIZE + frameLength + 1]) != 0x0A) {
            qWarning() << "CanBridge: Invalid frame delimiter, discarding 1 byte";
            m_readBuffer.remove(0, 1);
            continue;
        }

        // Extract device ID (big-endian, 2 bytes)
        int deviceId = (static_cast<unsigned char>(m_readBuffer[0]) << 8) |
                        static_cast<unsigned char>(m_readBuffer[1]);

        // Extract frame data
        QByteArray frameData = m_readBuffer.mid(HEADER_SIZE, frameLength);

        emit canFrameReceived(deviceId, frameData);

        // Remove the processed frame from the buffer
        m_readBuffer.remove(0, totalSize);
    }

    // Safety: if we have too much unparseable data, clear the buffer
    if (m_readBuffer.size() > 65536) {
        qWarning() << "CanBridge: Read buffer overflow, clearing" << m_readBuffer.size() << "bytes";
        m_readBuffer.clear();
    }
}
