#pragma once

#include <QObject>
#include <QTimer>

class RemoteDatabase;
class LocalDatabase;
class DatabaseManager;

class DataSyncManager : public QObject {
    friend class DatabaseManager;
    Q_OBJECT
public:
    explicit DataSyncManager(QObject* parent = nullptr);

    void start();
    void stop();
    bool isRunning() const;

private slots:
    void onSyncTimer();

private:
    bool syncDeviceData();
    bool syncAlarms();

    QTimer m_syncTimer;
    RemoteDatabase* m_remoteDb = nullptr;
    LocalDatabase* m_localDb = nullptr;
    QString m_lastSyncTime; // track last successful sync point

    void loadRemoteDbConfig();
};
