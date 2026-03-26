#include "DatabaseManager.h"
#include <QSettings>
#include <QCoreApplication>

DatabaseManager& DatabaseManager::instance()
{
    static DatabaseManager inst;
    return inst;
}

DatabaseManager::DatabaseManager(QObject* parent)
    : QObject(parent)
{
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
