#include "BarcodeScanner.h"
#include <QApplication>
#include <QKeyEvent>
#include <QDebug>

BarcodeScanner::BarcodeScanner(QObject* parent)
    : QObject(parent)
    , m_serialPort(nullptr)
    , m_usbHidTimer(nullptr)
    , m_hidTimeoutTimer(nullptr)
{
}

BarcodeScanner::~BarcodeScanner()
{
    stopSerial();
    stopUsbHid();
}

// --- Serial Mode ---

bool BarcodeScanner::startSerial(const QString& portName, int baudRate,
                                  int dataBits, int stopBits, int parity)
{
    stopSerial();

    m_serialPort = new QSerialPort(this);
    m_serialPort->setPortName(portName);
    m_serialPort->setBaudRate(baudRate);
    m_serialPort->setDataBits(static_cast<QSerialPort::DataBits>(dataBits));
    m_serialPort->setStopBits(static_cast<QSerialPort::StopBits>(stopBits));
    m_serialPort->setParity(static_cast<QSerialPort::Parity>(parity));

    connect(m_serialPort, &QSerialPort::readyRead,
            this, &BarcodeScanner::onSerialReadyRead);
    connect(m_serialPort, &QSerialPort::errorOccurred,
            this, [this](QSerialPort::SerialPortError error) {
                if (error != QSerialPort::NoError) {
                    emit errorOccurred(m_serialPort->errorString());
                }
            });

    if (!m_serialPort->open(QIODevice::ReadOnly)) {
        QString errMsg = QStringLiteral("Failed to open serial port %1: %2")
                             .arg(portName, m_serialPort->errorString());
        qWarning() << errMsg;
        emit errorOccurred(errMsg);
        delete m_serialPort;
        m_serialPort = nullptr;
        return false;
    }

    m_mode = SerialMode;
    m_readBuffer.clear();

    qDebug() << "Barcode scanner started in serial mode on" << portName
             << "baud:" << baudRate;
    return true;
}

void BarcodeScanner::stopSerial()
{
    if (m_serialPort) {
        m_serialPort->close();
        delete m_serialPort;
        m_serialPort = nullptr;
    }
    m_readBuffer.clear();
}

// --- USB HID Mode ---

void BarcodeScanner::startUsbHid()
{
    stopUsbHid();

    m_mode = UsbHidMode;
    m_hidBuffer.clear();

    // Install event filter on QApplication to capture all keyboard events
    if (qApp) {
        qApp->installEventFilter(this);
    }

    // Timer to detect end of barcode input (no Enter key sent)
    m_hidTimeoutTimer = new QTimer(this);
    m_hidTimeoutTimer->setSingleShot(true);
    m_hidTimeoutTimer->setInterval(HID_TIMEOUT_MS);
    connect(m_hidTimeoutTimer, &QTimer::timeout,
            this, &BarcodeScanner::onUsbHidCheck);

    qDebug() << "Barcode scanner started in USB HID mode";
}

void BarcodeScanner::stopUsbHid()
{
    if (qApp) {
        qApp->removeEventFilter(this);
    }

    if (m_hidTimeoutTimer) {
        m_hidTimeoutTimer->stop();
        delete m_hidTimeoutTimer;
        m_hidTimeoutTimer = nullptr;
    }

    m_hidBuffer.clear();
}

// --- Queries ---

bool BarcodeScanner::isRunning() const
{
    if (m_mode == SerialMode) {
        return m_serialPort != nullptr && m_serialPort->isOpen();
    }
    return m_mode == UsbHidMode && m_hidTimeoutTimer != nullptr;
}

BarcodeScanner::ScanMode BarcodeScanner::scanMode() const
{
    return m_mode;
}

// --- Private Slots ---

void BarcodeScanner::onSerialReadyRead()
{
    if (!m_serialPort) return;

    m_readBuffer.append(m_serialPort->readAll());

    // Check for complete barcode: look for CRLF (\r\n) or lone \n or \r
    while (true) {
        int crlfPos = m_readBuffer.indexOf("\r\n");
        int lfPos = m_readBuffer.indexOf('\n');
        int crPos = m_readBuffer.indexOf('\r');

        int endPos = -1;
        int barcodeLen = 0;

        if (crlfPos >= 0) {
            endPos = crlfPos;
            barcodeLen = crlfPos;
        } else if (lfPos >= 0) {
            endPos = lfPos;
            barcodeLen = lfPos;
        } else if (crPos >= 0) {
            endPos = crPos;
            barcodeLen = crPos;
        }

        if (endPos < 0) {
            break; // No complete barcode yet
        }

        QString barcode = QString::fromUtf8(m_readBuffer.left(barcodeLen)).trimmed();

        // Remove the consumed bytes including the terminator(s)
        int terminatorLen = 1;
        if (crlfPos >= 0) {
            terminatorLen = 2;
        }
        m_readBuffer.remove(0, barcodeLen + terminatorLen);

        if (!barcode.isEmpty()) {
            qDebug() << "Barcode scanned (serial):" << barcode;
            emit barcodeScanned(barcode);
        }
    }
}

void BarcodeScanner::onUsbHidCheck()
{
    // Timeout fired: treat accumulated buffer as a complete barcode
    QString barcode = m_hidBuffer.trimmed();
    m_hidBuffer.clear();

    if (!barcode.isEmpty()) {
        qDebug() << "Barcode scanned (USB HID timeout):" << barcode;
        emit barcodeScanned(barcode);
    }
}

// --- Event Filter (USB HID Mode) ---

bool BarcodeScanner::eventFilter(QObject* watched, QEvent* event)
{
    if (m_mode != UsbHidMode) {
        return QObject::eventFilter(watched, event);
    }

    if (event->type() == QEvent::KeyPress) {
        auto* keyEvent = static_cast<QKeyEvent*>(event);

        // Enter/Return signals end of barcode input
        if (keyEvent->key() == Qt::Key_Return || keyEvent->key() == Qt::Key_Enter) {
            if (!m_hidBuffer.isEmpty()) {
                QString barcode = m_hidBuffer.trimmed();
                m_hidBuffer.clear();
                m_hidTimeoutTimer->stop();

                if (!barcode.isEmpty()) {
                    qDebug() << "Barcode scanned (USB HID Enter):" << barcode;
                    emit barcodeScanned(barcode);
                }
            }
            return true; // Consume the Enter key so it does not propagate
        }

        // Printable character: accumulate into HID buffer
        QString text = keyEvent->text();
        if (!text.isEmpty() && text.at(0).isPrint()) {
            m_hidBuffer.append(text);
            m_hidTimeoutTimer->start(); // Reset timeout on each character

            // Consume the event to prevent it from reaching focused widgets
            // when HID mode is active
            return true;
        }

        // Non-printable keys (modifiers, function keys, etc.): pass through
        return false;
    }

    return QObject::eventFilter(watched, event);
}
