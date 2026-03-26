#include "DatabaseManager.h"
#include "storage/sync/DataSyncManager.h"

#include <QSettings>
#include <QCoreApplication>

DatabaseManager& DatabaseManager::instance()
{
    static DatabaseManager inst;
    return inst;
}

DatabaseManager::DatabaseManager(QObject* parent)
    : QObject(parent)
    , m_syncManager(new DataSyncManager(this))
{
    // Wire the sync manager to the databases
    m_syncManager->m_localDb = &m_localDb;
    m_syncManager->m_remoteDb = &m_remoteDb;
}

bool DatabaseManager::initialize()
{
    QSettings settings;
    settings.beginGroup("Database");
    QString dbPath = settings.value("LocalPath",
        QCoreApplication::applicationDirPath() + "/data/aging_monitor.db").toString();
    settings.endGroup();

    return m_localDb.initialize(dbPath);
}

LocalDatabase* DatabaseManager::localDb()
{
    return &m_localDb;
}

RemoteDatabase* DatabaseManager::remoteDb()
{
    return &m_remoteDb;
}

DataSyncManager* DatabaseManager::syncManager()
{
    return m_syncManager;
}

void DatabaseManager::startSync()
{
    if (m_syncManager) {
        m_syncManager->start();
    }
}

void DatabaseManager::stopSync()
{
    if (m_syncManager) {
        m_syncManager->stop();
    }
}
