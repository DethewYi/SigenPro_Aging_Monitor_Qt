#pragma once

#include <QObject>
#include <QSerialPort>
#include <QTimer>

class BarcodeScanner : public QObject {
    Q_OBJECT
public:
    enum ScanMode { SerialMode, UsbHidMode };

    explicit BarcodeScanner(QObject* parent = nullptr);
    ~BarcodeScanner();

    // Serial mode
    bool startSerial(const QString& portName, int baudRate = 9600,
                     int dataBits = 8, int stopBits = 1, int parity = 0);
    void stopSerial();

    // USB HID mode
    void startUsbHid();
    void stopUsbHid();

    bool isRunning() const;
    ScanMode scanMode() const;

signals:
    void barcodeScanned(const QString& barcode);
    void errorOccurred(const QString& error);

private slots:
    void onSerialReadyRead();
    void onUsbHidCheck();

private:
    ScanMode m_mode = SerialMode;
    QSerialPort* m_serialPort = nullptr;
    QTimer* m_usbHidTimer = nullptr;
    QByteArray m_readBuffer;

    // USB HID mode - capture global keyboard input
    QString m_hidBuffer;
    QTimer* m_hidTimeoutTimer = nullptr;
    static constexpr int HID_TIMEOUT_MS = 100; // End of barcode input detection

    bool eventFilter(QObject* watched, QEvent* event) override;
};
