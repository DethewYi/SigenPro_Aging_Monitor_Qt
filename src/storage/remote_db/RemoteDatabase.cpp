#include "RemoteDatabase.h"

#include <QSqlQuery>
#include <QSqlError>
#include <QDebug>
#include <QUuid>

static const QString REMOTE_CONNECTION_PREFIX = "aging_monitor_remote_";

// ---------------------------------------------------------------------------
// Construction / Destruction
// ---------------------------------------------------------------------------

RemoteDatabase::RemoteDatabase(QObject* parent)
    : QObject(parent)
    , m_connectionName(REMOTE_CONNECTION_PREFIX + QUuid::createUuid().toString(QUuid::WithoutBraces))
{
}

RemoteDatabase::~RemoteDatabase()
{
    disconnect();
}

// ---------------------------------------------------------------------------
// connect / disconnect
// ---------------------------------------------------------------------------

bool RemoteDatabase::connect(const QString& host, int port, const QString& dbName,
                              const QString& user, const QString& password, const QString& dbType)
{
    // Disconnect any existing connection
    disconnect();

    QString driverType = dbType.toUpper();
    if (driverType == "MYSQL") {
        driverType = "QMYSQL";
    } else if (driverType == "POSTGRESQL" || driverType == "PGSQL") {
        driverType = "QPSQL";
    } else if (!driverType.startsWith("Q")) {
        driverType = "Q" + driverType;
    }

    // Check if the driver is available
    if (!QSqlDatabase::isDriverAvailable(driverType)) {
        qWarning() << "RemoteDatabase: SQL driver not available:" << driverType;
        return false;
    }

    if (QSqlDatabase::contains(m_connectionName)) {
        m_db = QSqlDatabase::database(m_connectionName);
    } else {
        m_db = QSqlDatabase::addDatabase(driverType, m_connectionName);
    }

    m_db.setHostName(host);
    m_db.setPort(port);
    m_db.setDatabaseName(dbName);
    m_db.setUserName(user);
    m_db.setPassword(password);

    // Set connection timeouts
    m_db.setConnectOptions("CONNECT_TIMEOUT=10");

    if (!m_db.open()) {
        qWarning() << "RemoteDatabase: failed to connect to remote database:"
                   << m_db.lastError().text();
        m_connected = false;
        return false;
    }

    m_connected = true;
    qDebug() << "RemoteDatabase: connected to" << host << "database" << dbName;
    return true;
}

void RemoteDatabase::disconnect()
{
    if (m_db.isOpen()) {
        m_db.close();
    }
    if (QSqlDatabase::contains(m_connectionName)) {
        QSqlDatabase::removeDatabase(m_connectionName);
    }
    m_connected = false;
    m_db = QSqlDatabase(); // Clear the reference
}

bool RemoteDatabase::isConnected() const
{
    return m_connected && m_db.isOpen();
}

// ---------------------------------------------------------------------------
// createMetaTables
// ---------------------------------------------------------------------------

bool RemoteDatabase::createMetaTables()
{
    if (!isConnected()) {
        qWarning() << "RemoteDatabase: not connected, cannot create meta tables";
        return false;
    }

    QSqlQuery query(m_db);

    // devices
    if (!query.exec(
        "CREATE TABLE IF NOT EXISTS devices ("
        "  device_id INT PRIMARY KEY,"
        "  name VARCHAR(128) NOT NULL,"
        "  model VARCHAR(64),"
        "  comm_type INT DEFAULT 0,"
        "  ip_address VARCHAR(45),"
        "  port INT DEFAULT 0,"
        "  protocol_name VARCHAR(64),"
        "  channel_id INT DEFAULT -1"
        ")")) {
        qWarning() << "RemoteDatabase: create devices table error:" << query.lastError().text();
        return false;
    }

    // channels
    if (!query.exec(
        "CREATE TABLE IF NOT EXISTS channels ("
        "  channel_id INT PRIMARY KEY,"
        "  status INT DEFAULT 0,"
        "  bound_sn VARCHAR(64),"
        "  bound_pn VARCHAR(64),"
        "  power_controller_id INT DEFAULT -1,"
        "  contactor_controller_id INT DEFAULT -1,"
        "  power_channel INT DEFAULT -1,"
        "  contactor_channel INT DEFAULT -1,"
        "  power_protocol_name VARCHAR(64),"
        "  contactor_protocol_name VARCHAR(64)"
        ")")) {
        qWarning() << "RemoteDatabase: create channels table error:" << query.lastError().text();
        return false;
    }

    // test_templates
    if (!query.exec(
        "CREATE TABLE IF NOT EXISTS test_templates ("
        "  template_id SERIAL PRIMARY KEY,"
        "  name VARCHAR(128) NOT NULL,"
        "  product_model VARCHAR(64),"
        "  total_duration INT DEFAULT 0,"
        "  config_json TEXT,"
        "  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
        ")")) {
        qWarning() << "RemoteDatabase: create test_templates table error:" << query.lastError().text();
        return false;
    }

    // test_records
    if (!query.exec(
        "CREATE TABLE IF NOT EXISTS test_records ("
        "  id SERIAL PRIMARY KEY,"
        "  device_id INT,"
        "  sn VARCHAR(64),"
        "  pn VARCHAR(64),"
        "  template_name VARCHAR(128),"
        "  start_time TIMESTAMP,"
        "  end_time TIMESTAMP,"
        "  result INT DEFAULT 0,"
        "  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
        ")")) {
        qWarning() << "RemoteDatabase: create test_records table error:" << query.lastError().text();
        return false;
    }

    // alarms
    if (!query.exec(
        "CREATE TABLE IF NOT EXISTS alarms ("
        "  id SERIAL PRIMARY KEY,"
        "  timestamp TIMESTAMP,"
        "  device_id INT,"
        "  device_name VARCHAR(128),"
        "  param_name VARCHAR(64),"
        "  current_value DOUBLE PRECISION,"
        "  threshold DOUBLE PRECISION,"
        "  is_upper_limit BOOLEAN DEFAULT TRUE,"
        "  acknowledged BOOLEAN DEFAULT FALSE,"
        "  message TEXT"
        ")")) {
        qWarning() << "RemoteDatabase: create alarms table error:" << query.lastError().text();
        return false;
    }

    // db_info
    if (!query.exec(
        "CREATE TABLE IF NOT EXISTS db_info ("
        "  key VARCHAR(64) PRIMARY KEY,"
        "  value TEXT"
        ")")) {
        qWarning() << "RemoteDatabase: create db_info table error:" << query.lastError().text();
        return false;
    }

    return true;
}

// ---------------------------------------------------------------------------
// createMonthlyTable
// ---------------------------------------------------------------------------

bool RemoteDatabase::createMonthlyTable(const QString& monthStr)
{
    if (!isConnected()) {
        qWarning() << "RemoteDatabase: not connected, cannot create monthly table";
        return false;
    }

    QSqlQuery query(m_db);

    QString tableName = "device_data_" + monthStr;

    // Check if table already exists using information_schema (works for both MySQL and PostgreSQL)
    // Try PostgreSQL style first, then MySQL
    bool tableExists = false;

    QString driverName = m_db.driverName();
    if (driverName == "QPSQL") {
        query.prepare("SELECT COUNT(*) FROM information_schema.tables "
                      "WHERE table_name = ?");
        query.addBindValue(tableName);
        if (query.exec() && query.next() && query.value(0).toInt() > 0) {
            tableExists = true;
        }
    } else {
        // MySQL
        query.prepare("SELECT COUNT(*) FROM information_schema.tables "
                      "WHERE table_schema = DATABASE() AND table_name = ?");
        query.addBindValue(tableName);
        if (query.exec() && query.next() && query.value(0).toInt() > 0) {
            tableExists = true;
        }
    }

    if (tableExists) {
        return true;
    }

    QString sql = QString(
        "CREATE TABLE IF NOT EXISTS %1 ("
        "  id SERIAL PRIMARY KEY,"
        "  device_id INT NOT NULL,"
        "  timestamp TIMESTAMP NOT NULL,"
        "  param_key VARCHAR(64) NOT NULL,"
        "  param_value DOUBLE PRECISION,"
        "  comm_ok BOOLEAN DEFAULT TRUE,"
        "  frame_errors INT DEFAULT 0"
        ")").arg(tableName);

    if (!query.exec(sql)) {
        qWarning() << "RemoteDatabase: create monthly table error:" << query.lastError().text();
        return false;
    }

    // Create index on (device_id, timestamp) for query performance
    QString indexName = "idx_" + monthStr + "_device_ts";
    QString indexSql = QString(
        "CREATE INDEX IF NOT EXISTS %1 ON %2 (device_id, timestamp)"
        ).arg(indexName).arg(tableName);

    if (!query.exec(indexSql)) {
        qWarning() << "RemoteDatabase: create index error:" << query.lastError().text();
        // Non-fatal: the table still works, just slower queries
    }

    return true;
}

// ---------------------------------------------------------------------------
// insertDeviceDataBatch
// ---------------------------------------------------------------------------

bool RemoteDatabase::insertDeviceDataBatch(const QVector<DeviceData>& dataList)
{
    if (!isConnected()) {
        qWarning() << "RemoteDatabase: not connected, cannot insert device data";
        return false;
    }

    if (dataList.isEmpty()) {
        return true;
    }

    if (!m_db.transaction()) {
        qWarning() << "RemoteDatabase: failed to start transaction:" << m_db.lastError().text();
        return false;
    }

    for (const auto& data : dataList) {
        QString monthStr = data.timestamp.toString("yyyyMM");
        if (!createMonthlyTable(monthStr)) {
            m_db.rollback();
            return false;
        }

        QString tableName = "device_data_" + monthStr;
        QSqlQuery insert(m_db);
        insert.prepare(
            QString("INSERT INTO %1 (device_id, timestamp, param_key, param_value, comm_ok, frame_errors) "
                    "VALUES (?, ?, ?, ?, ?, ?)").arg(tableName));

        for (auto it = data.parameters.constBegin(); it != data.parameters.constEnd(); ++it) {
            insert.addBindValue(data.deviceId);
            insert.addBindValue(data.timestamp.toString(Qt::ISODate));
            insert.addBindValue(it.key());
            insert.addBindValue(it.value());
            insert.addBindValue(data.communicationOk);
            insert.addBindValue(data.frameErrorCount);

            if (!insert.exec()) {
                qWarning() << "RemoteDatabase: insert device data error:" << insert.lastError().text();
                m_db.rollback();
                return false;
            }
        }
    }

    if (!m_db.commit()) {
        qWarning() << "RemoteDatabase: commit error:" << m_db.lastError().text();
        m_db.rollback();
        return false;
    }

    return true;
}

// ---------------------------------------------------------------------------
// insertAlarmRecords
// ---------------------------------------------------------------------------

bool RemoteDatabase::insertAlarmRecords(const QVector<AlarmRecord>& records)
{
    if (!isConnected()) {
        qWarning() << "RemoteDatabase: not connected, cannot insert alarm records";
        return false;
    }

    if (records.isEmpty()) {
        return true;
    }

    if (!m_db.transaction()) {
        qWarning() << "RemoteDatabase: failed to start transaction:" << m_db.lastError().text();
        return false;
    }

    QSqlQuery query(m_db);
    query.prepare(
        "INSERT INTO alarms (timestamp, device_id, device_name, param_name, "
        "current_value, threshold, is_upper_limit, acknowledged, message) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)");

    for (const auto& record : records) {
        query.addBindValue(record.timestamp.toString(Qt::ISODate));
        query.addBindValue(record.deviceId);
        query.addBindValue(record.deviceName);
        query.addBindValue(record.paramName);
        query.addBindValue(record.currentValue);
        query.addBindValue(record.threshold);
        query.addBindValue(record.isUpperLimit);
        query.addBindValue(record.acknowledged);
        query.addBindValue(record.message);

        if (!query.exec()) {
            qWarning() << "RemoteDatabase: insert alarm record error:" << query.lastError().text();
            m_db.rollback();
            return false;
        }
    }

    if (!m_db.commit()) {
        qWarning() << "RemoteDatabase: commit error:" << m_db.lastError().text();
        m_db.rollback();
        return false;
    }

    return true;
}

// ---------------------------------------------------------------------------
// queryDeviceData
// ---------------------------------------------------------------------------

QVector<DeviceData> RemoteDatabase::queryDeviceData(int deviceId, const QDateTime& start, const QDateTime& end)
{
    QVector<DeviceData> results;

    if (!isConnected()) {
        return results;
    }

    // Iterate over each month in the range
    QDateTime monthStart = start;
    while (monthStart <= end) {
        QString monthStr = monthStart.toString("yyyyMM");
        QString tableName = "device_data_" + monthStr;

        // Check if the monthly table exists
        QSqlQuery check(m_db);
        QString driverName = m_db.driverName();
        bool tableExists = false;

        if (driverName == "QPSQL") {
            check.prepare("SELECT COUNT(*) FROM information_schema.tables WHERE table_name = ?");
        } else {
            check.prepare("SELECT COUNT(*) FROM information_schema.tables "
                          "WHERE table_schema = DATABASE() AND table_name = ?");
        }
        check.addBindValue(tableName);

        if (!check.exec() || !check.next() || check.value(0).toInt() == 0) {
            // Table does not exist for this month, skip
            monthStart = monthStart.addMonths(1);
            continue;
        }

        // Query the monthly table
        QSqlQuery query(m_db);
        query.prepare(
            QString("SELECT device_id, timestamp, param_key, param_value, comm_ok, frame_errors "
                    "FROM %1 "
                    "WHERE device_id = ? AND timestamp >= ? AND timestamp <= ? "
                    "ORDER BY timestamp ASC").arg(tableName));
        query.addBindValue(deviceId);
        query.addBindValue(start.toString(Qt::ISODate));
        query.addBindValue(end.toString(Qt::ISODate));

        if (query.exec()) {
            while (query.next()) {
                DeviceData dd;
                dd.deviceId = query.value(0).toInt();
                dd.timestamp = QDateTime::fromString(query.value(1).toString(), Qt::ISODate);
                QString paramKey = query.value(2).toString();
                double paramValue = query.value(3).toDouble();
                dd.communicationOk = query.value(4).toBool();
                dd.frameErrorCount = query.value(5).toInt();

                // Try to merge with the last entry if it has the same timestamp
                bool merged = false;
                if (!results.isEmpty() && results.last().timestamp == dd.timestamp) {
                    results.last().parameters.insert(paramKey, paramValue);
                    merged = true;
                }
                if (!merged) {
                    dd.parameters.insert(paramKey, paramValue);
                    results.append(dd);
                }
            }
        } else {
            qWarning() << "RemoteDatabase: query device data error:" << query.lastError().text();
        }

        monthStart = monthStart.addMonths(1);
    }

    return results;
}

// ---------------------------------------------------------------------------
// queryAlarms
// ---------------------------------------------------------------------------

QVector<AlarmRecord> RemoteDatabase::queryAlarms(const QDateTime& start, int limit)
{
    QVector<AlarmRecord> results;

    if (!isConnected()) {
        return results;
    }

    QSqlQuery query(m_db);
    query.prepare(
        "SELECT id, timestamp, device_id, device_name, param_name, "
        "current_value, threshold, is_upper_limit, acknowledged, message "
        "FROM alarms "
        "WHERE timestamp >= ? "
        "ORDER BY timestamp DESC "
        "LIMIT ?");
    query.addBindValue(start.toString(Qt::ISODate));
    query.addBindValue(limit);

    if (query.exec()) {
        while (query.next()) {
            AlarmRecord ar;
            ar.id = query.value(0).toInt();
            ar.timestamp = QDateTime::fromString(query.value(1).toString(), Qt::ISODate);
            ar.deviceId = query.value(2).toInt();
            ar.deviceName = query.value(3).toString();
            ar.paramName = query.value(4).toString();
            ar.currentValue = query.value(5).toDouble();
            ar.threshold = query.value(6).toDouble();
            ar.isUpperLimit = query.value(7).toBool();
            ar.acknowledged = query.value(8).toBool();
            ar.message = query.value(9).toString();
            results.append(ar);
        }
    } else {
        qWarning() << "RemoteDatabase: query alarms error:" << query.lastError().text();
    }

    return results;
}
