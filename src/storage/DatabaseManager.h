#pragma once

#include <QObject>
#include "storage/local_db/LocalDatabase.h"
#include "storage/remote_db/RemoteDatabase.h"

class DataSyncManager;

class DatabaseManager : public QObject {
    Q_OBJECT
public:
    static DatabaseManager& instance();

    bool initialize();
    LocalDatabase* localDb();
    RemoteDatabase* remoteDb();
    DataSyncManager* syncManager();

    void startSync();
    void stopSync();

private:
    DatabaseManager(QObject* parent = nullptr);
    LocalDatabase m_localDb;
    RemoteDatabase m_remoteDb;
    DataSyncManager* m_syncManager = nullptr;
};
