#pragma once

#include <QObject>
#include "storage/local_db/LocalDatabase.h"

class DatabaseManager : public QObject {
    Q_OBJECT
public:
    static DatabaseManager& instance();

    bool initialize();
    LocalDatabase* localDb();

private:
    DatabaseManager(QObject* parent = nullptr);
    LocalDatabase m_localDb;
};
