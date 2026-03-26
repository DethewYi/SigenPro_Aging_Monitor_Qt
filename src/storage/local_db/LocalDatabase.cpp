#include "LocalDatabase.h"

#include <QSqlQuery>
#include <QSqlError>
#include <QDir>
#include <QDebug>
#include <QDateTime>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonArray>

static const char* DB_CONNECTION_NAME = "aging_monitor_local_db";

// ---------------------------------------------------------------------------
// Construction / Destruction
// ---------------------------------------------------------------------------

LocalDatabase::LocalDatabase(QObject* parent)
    : QObject(parent)
{
}

LocalDatabase::~LocalDatabase()
{
    if (m_db.isOpen()) {
        m_db.close();
    }
    if (QSqlDatabase::contains(DB_CONNECTION_NAME)) {
        QSqlDatabase::removeDatabase(DB_CONNECTION_NAME);
    }
}

// ---------------------------------------------------------------------------
// initialize
// ---------------------------------------------------------------------------

bool LocalDatabase::initialize(const QString& dbPath)
{
    m_dbPath = dbPath;

    // Ensure parent directory exists
    QDir dir(QFileInfo(dbPath).absolutePath());
    if (!dir.exists()) {
        if (!dir.mkpath(".")) {
            qWarning() << "LocalDatabase: failed to create directory:" << dir.absolutePath();
            return false;
        }
    }

    if (QSqlDatabase::contains(DB_CONNECTION_NAME)) {
        m_db = QSqlDatabase::database(DB_CONNECTION_NAME);
    } else {
        m_db = QSqlDatabase::addDatabase("QSQLITE", DB_CONNECTION_NAME);
    }

    m_db.setDatabaseName(dbPath);
    if (!m_db.open()) {
        qWarning() << "LocalDatabase: failed to open database:" << m_db.lastError().text();
        return false;
    }

    // Set performance pragmas
    QSqlQuery query(m_db);
    if (!query.exec("PRAGMA journal_mode=WAL")) {
        qWarning() << "LocalDatabase: failed to set WAL mode:" << query.lastError().text();
    }
    if (!query.exec("PRAGMA synchronous=NORMAL")) {
        qWarning() << "LocalDatabase: failed to set synchronous:" << query.lastError().text();
    }

    return createMetaTables();
}

// ---------------------------------------------------------------------------
// createMetaTables
// ---------------------------------------------------------------------------

bool LocalDatabase::createMetaTables()
{
    QSqlQuery query(m_db);

    // devices
    query.exec(
        "CREATE TABLE IF NOT EXISTS devices ("
        "  device_id INTEGER PRIMARY KEY,"
        "  name TEXT NOT NULL,"
        "  model TEXT,"
        "  comm_type INTEGER DEFAULT 0,"
        "  ip_address TEXT,"
        "  port INTEGER DEFAULT 0,"
        "  protocol_name TEXT,"
        "  channel_id INTEGER DEFAULT -1"
        ")");
    if (query.lastError().isValid()) {
        qWarning() << "LocalDatabase: create devices table error:" << query.lastError().text();
        return false;
    }

    // channels
    query.exec(
        "CREATE TABLE IF NOT EXISTS channels ("
        "  channel_id INTEGER PRIMARY KEY,"
        "  status INTEGER DEFAULT 0,"
        "  bound_sn TEXT,"
        "  bound_pn TEXT,"
        "  power_controller_id INTEGER DEFAULT -1,"
        "  contactor_controller_id INTEGER DEFAULT -1,"
        "  power_channel INTEGER DEFAULT -1,"
        "  contactor_channel INTEGER DEFAULT -1,"
        "  power_protocol_name TEXT,"
        "  contactor_protocol_name TEXT"
        ")");
    if (query.lastError().isValid()) {
        qWarning() << "LocalDatabase: create channels table error:" << query.lastError().text();
        return false;
    }

    // test_templates
    query.exec(
        "CREATE TABLE IF NOT EXISTS test_templates ("
        "  template_id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "  name TEXT NOT NULL,"
        "  product_model TEXT,"
        "  total_duration INTEGER DEFAULT 0,"
        "  config_json TEXT,"
        "  created_at TEXT DEFAULT (datetime('now','localtime'))"
        ")");
    if (query.lastError().isValid()) {
        qWarning() << "LocalDatabase: create test_templates table error:" << query.lastError().text();
        return false;
    }

    // test_records
    query.exec(
        "CREATE TABLE IF NOT EXISTS test_records ("
        "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "  device_id INTEGER,"
        "  sn TEXT,"
        "  pn TEXT,"
        "  template_name TEXT,"
        "  start_time TEXT,"
        "  end_time TEXT,"
        "  result INTEGER DEFAULT 0,"
        "  created_at TEXT DEFAULT (datetime('now','localtime'))"
        ")");
    if (query.lastError().isValid()) {
        qWarning() << "LocalDatabase: create test_records table error:" << query.lastError().text();
        return false;
    }

    // alarms
    query.exec(
        "CREATE TABLE IF NOT EXISTS alarms ("
        "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "  timestamp TEXT,"
        "  device_id INTEGER,"
        "  device_name TEXT,"
        "  param_name TEXT,"
        "  current_value REAL,"
        "  threshold REAL,"
        "  is_upper_limit INTEGER DEFAULT 1,"
        "  acknowledged INTEGER DEFAULT 0,"
        "  message TEXT"
        ")");
    if (query.lastError().isValid()) {
        qWarning() << "LocalDatabase: create alarms table error:" << query.lastError().text();
        return false;
    }

    // db_info
    query.exec(
        "CREATE TABLE IF NOT EXISTS db_info ("
        "  key TEXT PRIMARY KEY,"
        "  value TEXT"
        ")");
    if (query.lastError().isValid()) {
        qWarning() << "LocalDatabase: create db_info table error:" << query.lastError().text();
        return false;
    }

    return true;
}

// ---------------------------------------------------------------------------
// Daily table helpers
// ---------------------------------------------------------------------------

bool LocalDatabase::ensureDailyTable(const QString& dateStr)
{
    // Check if the table already exists via sqlite_master
    QSqlQuery check(m_db);
    check.prepare("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?");
    check.addBindValue("device_data_" + dateStr);
    if (check.exec() && check.next() && check.value(0).toInt() > 0) {
        return true;
    }

    return createDailyTable(dateStr);
}

bool LocalDatabase::createDailyTable(const QString& dateStr)
{
    QSqlQuery query(m_db);

    QString tableName = "device_data_" + dateStr;
    QString sql = QString(
        "CREATE TABLE IF NOT EXISTS %1 ("
        "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "  device_id INTEGER NOT NULL,"
        "  timestamp TEXT NOT NULL,"
        "  param_key TEXT NOT NULL,"
        "  param_value REAL,"
        "  comm_ok INTEGER DEFAULT 1,"
        "  frame_errors INTEGER DEFAULT 0"
        ")").arg(tableName);

    if (!query.exec(sql)) {
        qWarning() << "LocalDatabase: create daily table error:" << query.lastError().text();
        return false;
    }

    // Create index on (device_id, timestamp) for query performance
    QString indexName = "idx_" + dateStr + "_device_ts";
    QString indexSql = QString(
        "CREATE INDEX IF NOT EXISTS %1 ON %2 (device_id, timestamp)"
        ).arg(indexName).arg(tableName);

    if (!query.exec(indexSql)) {
        qWarning() << "LocalDatabase: create index error:" << query.lastError().text();
        // Non-fatal: the table still works, just slower queries
    }

    return true;
}

// ---------------------------------------------------------------------------
// insertDeviceData
// ---------------------------------------------------------------------------

bool LocalDatabase::insertDeviceData(const QVector<DeviceData>& dataList)
{
    if (dataList.isEmpty()) {
        return true;
    }

    m_db.transaction();

    for (const auto& data : dataList) {
        QString dateStr = data.timestamp.toString("yyyyMMdd");
        if (!ensureDailyTable(dateStr)) {
            m_db.rollback();
            return false;
        }

        QString tableName = "device_data_" + dateStr;
        QSqlQuery insert(m_db);
        insert.prepare(
            QString("INSERT INTO %1 (device_id, timestamp, param_key, param_value, comm_ok, frame_errors) "
                    "VALUES (?, ?, ?, ?, ?, ?)").arg(tableName));

        for (auto it = data.parameters.constBegin(); it != data.parameters.constEnd(); ++it) {
            insert.addBindValue(data.deviceId);
            insert.addBindValue(data.timestamp.toString(Qt::ISODate));
            insert.addBindValue(it.key());
            insert.addBindValue(it.value());
            insert.addBindValue(data.communicationOk ? 1 : 0);
            insert.addBindValue(data.frameErrorCount);

            if (!insert.exec()) {
                qWarning() << "LocalDatabase: insert device data error:" << insert.lastError().text();
                m_db.rollback();
                return false;
            }
        }
    }

    return m_db.commit();
}

// ---------------------------------------------------------------------------
// queryDeviceData
// ---------------------------------------------------------------------------

QVector<DeviceData> LocalDatabase::queryDeviceData(int deviceId, const QDateTime& start, const QDateTime& end)
{
    QVector<DeviceData> results;

    // Iterate over each day in the range
    QDateTime dayStart = start;
    while (dayStart <= end) {
        QString dateStr = dayStart.toString("yyyyMMdd");
        QString tableName = "device_data_" + dateStr;

        // Check if table exists
        QSqlQuery check(m_db);
        check.prepare("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?");
        check.addBindValue(tableName);
        if (!check.exec() || !check.next() || check.value(0).toInt() == 0) {
            // Table does not exist for this day, skip
            dayStart = dayStart.addDays(1);
            continue;
        }

        // Query the daily table
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
                dd.communicationOk = query.value(4).toInt() != 0;
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
        }

        dayStart = dayStart.addDays(1);
    }

    return results;
}

// ---------------------------------------------------------------------------
// Alarm operations
// ---------------------------------------------------------------------------

bool LocalDatabase::insertAlarmRecord(const AlarmRecord& record)
{
    QSqlQuery query(m_db);
    query.prepare(
        "INSERT INTO alarms (timestamp, device_id, device_name, param_name, "
        "current_value, threshold, is_upper_limit, acknowledged, message) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)");
    query.addBindValue(record.timestamp.toString(Qt::ISODate));
    query.addBindValue(record.deviceId);
    query.addBindValue(record.deviceName);
    query.addBindValue(record.paramName);
    query.addBindValue(record.currentValue);
    query.addBindValue(record.threshold);
    query.addBindValue(record.isUpperLimit ? 1 : 0);
    query.addBindValue(record.acknowledged ? 1 : 0);
    query.addBindValue(record.message);

    if (!query.exec()) {
        qWarning() << "LocalDatabase: insert alarm error:" << query.lastError().text();
        return false;
    }
    return true;
}

QVector<AlarmRecord> LocalDatabase::queryAlarms(const QDateTime& start, int limit)
{
    QVector<AlarmRecord> results;

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
            ar.isUpperLimit = query.value(7).toInt() != 0;
            ar.acknowledged = query.value(8).toInt() != 0;
            ar.message = query.value(9).toString();
            results.append(ar);
        }
    }

    return results;
}

bool LocalDatabase::acknowledgeAlarm(int alarmId)
{
    QSqlQuery query(m_db);
    query.prepare("UPDATE alarms SET acknowledged=1 WHERE id=?");
    query.addBindValue(alarmId);

    if (!query.exec()) {
        qWarning() << "LocalDatabase: acknowledge alarm error:" << query.lastError().text();
        return false;
    }
    return query.numRowsAffected() > 0;
}

// ---------------------------------------------------------------------------
// Test record
// ---------------------------------------------------------------------------

bool LocalDatabase::saveTestRecord(int deviceId, const QString& sn, const QString& pn,
                                    const QString& templateName, const QDateTime& startTime,
                                    const QDateTime& endTime, int testResult)
{
    QSqlQuery query(m_db);
    query.prepare(
        "INSERT INTO test_records (device_id, sn, pn, template_name, start_time, end_time, result) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)");
    query.addBindValue(deviceId);
    query.addBindValue(sn);
    query.addBindValue(pn);
    query.addBindValue(templateName);
    query.addBindValue(startTime.toString(Qt::ISODate));
    query.addBindValue(endTime.toString(Qt::ISODate));
    query.addBindValue(testResult);

    if (!query.exec()) {
        qWarning() << "LocalDatabase: save test record error:" << query.lastError().text();
        return false;
    }
    return true;
}

// ---------------------------------------------------------------------------
// Channel operations
// ---------------------------------------------------------------------------

bool LocalDatabase::saveChannelInfo(const ChannelInfo& info)
{
    QSqlQuery query(m_db);
    query.prepare(
        "INSERT OR REPLACE INTO channels (channel_id, status, bound_sn, bound_pn, "
        "power_controller_id, contactor_controller_id, power_channel, contactor_channel, "
        "power_protocol_name, contactor_protocol_name) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)");
    query.addBindValue(info.channelId);
    query.addBindValue(static_cast<int>(info.status));
    query.addBindValue(info.boundSN);
    query.addBindValue(info.boundPN);
    query.addBindValue(info.powerControllerId);
    query.addBindValue(info.contactorControllerId);
    query.addBindValue(info.powerChannel);
    query.addBindValue(info.contactorChannel);
    query.addBindValue(info.powerProtocolName);
    query.addBindValue(info.contactorProtocolName);

    if (!query.exec()) {
        qWarning() << "LocalDatabase: save channel info error:" << query.lastError().text();
        return false;
    }
    return true;
}

QVector<ChannelInfo> LocalDatabase::loadAllChannels()
{
    QVector<ChannelInfo> results;

    QSqlQuery query(m_db);
    if (query.exec("SELECT channel_id, status, bound_sn, bound_pn, "
                   "power_controller_id, contactor_controller_id, power_channel, contactor_channel, "
                   "power_protocol_name, contactor_protocol_name "
                   "FROM channels ORDER BY channel_id ASC")) {
        while (query.next()) {
            ChannelInfo ci;
            ci.channelId = query.value(0).toInt();
            ci.status = static_cast<ChannelStatus>(query.value(1).toInt());
            ci.boundSN = query.value(2).toString();
            ci.boundPN = query.value(3).toString();
            ci.powerControllerId = query.value(4).toInt();
            ci.contactorControllerId = query.value(5).toInt();
            ci.powerChannel = query.value(6).toInt();
            ci.contactorChannel = query.value(7).toInt();
            ci.powerProtocolName = query.value(8).toString();
            ci.contactorProtocolName = query.value(9).toString();
            results.append(ci);
        }
    }

    return results;
}

// ---------------------------------------------------------------------------
// Template operations
// ---------------------------------------------------------------------------

static QJsonObject testTemplateToJson(const TestTemplate& tmpl)
{
    QJsonObject root;
    root["name"] = tmpl.name;
    root["product_model"] = tmpl.productModel;
    root["total_duration_minutes"] = tmpl.totalDurationMinutes;

    // collectParams
    QJsonObject collectParams;
    for (auto it = tmpl.collectParams.constBegin(); it != tmpl.collectParams.constEnd(); ++it) {
        collectParams[it.key()] = it.value();
    }
    root["collect_params"] = collectParams;

    // defaultThresholds
    QJsonObject thresholds;
    for (auto it = tmpl.defaultThresholds.constBegin(); it != tmpl.defaultThresholds.constEnd(); ++it) {
        QJsonObject th;
        th["upper_limit"] = it.value().upperLimit;
        th["lower_limit"] = it.value().lowerLimit;
        th["enabled"] = it.value().enabled;
        thresholds[it.key()] = th;
    }
    root["default_thresholds"] = thresholds;

    // phases
    QJsonArray phasesArray;
    for (const auto& phase : tmpl.phases) {
        QJsonObject phaseObj;
        phaseObj["name"] = phase.name;
        phaseObj["duration_minutes"] = phase.durationMinutes;

        QJsonObject phaseThresholds;
        for (auto it = phase.thresholds.constBegin(); it != phase.thresholds.constEnd(); ++it) {
            QJsonObject th;
            th["upper_limit"] = it.value().upperLimit;
            th["lower_limit"] = it.value().lowerLimit;
            th["enabled"] = it.value().enabled;
            phaseThresholds[it.key()] = th;
        }
        phaseObj["thresholds"] = phaseThresholds;
        phasesArray.append(phaseObj);
    }
    root["phases"] = phasesArray;

    return root;
}

static TestTemplate jsonToTestTemplate(int templateId, const QString& name, const QString& productModel,
                                        int totalDuration, const QJsonObject& root)
{
    TestTemplate tmpl;
    tmpl.templateId = templateId;
    tmpl.name = name;
    tmpl.productModel = productModel;
    tmpl.totalDurationMinutes = totalDuration;

    // collectParams
    QJsonObject collectParams = root["collect_params"].toObject();
    for (auto it = collectParams.constBegin(); it != collectParams.constEnd(); ++it) {
        tmpl.collectParams.insert(it.key(), it.value().toDouble());
    }

    // defaultThresholds
    QJsonObject thresholds = root["default_thresholds"].toObject();
    for (auto it = thresholds.constBegin(); it != thresholds.constEnd(); ++it) {
        QJsonObject th = it.value().toObject();
        AlarmThreshold at;
        at.upperLimit = th["upper_limit"].toDouble();
        at.lowerLimit = th["lower_limit"].toDouble();
        at.enabled = th["enabled"].toBool();
        tmpl.defaultThresholds.insert(it.key(), at);
    }

    // phases
    QJsonArray phasesArray = root["phases"].toArray();
    for (const auto& phaseVal : phasesArray) {
        QJsonObject phaseObj = phaseVal.toObject();
        TestPhase phase;
        phase.name = phaseObj["name"].toString();
        phase.durationMinutes = phaseObj["duration_minutes"].toInt();

        QJsonObject phaseThresholds = phaseObj["thresholds"].toObject();
        for (auto it = phaseThresholds.constBegin(); it != phaseThresholds.constEnd(); ++it) {
            QJsonObject th = it.value().toObject();
            AlarmThreshold at;
            at.upperLimit = th["upper_limit"].toDouble();
            at.lowerLimit = th["lower_limit"].toDouble();
            at.enabled = th["enabled"].toBool();
            phase.thresholds.insert(it.key(), at);
        }
        tmpl.phases.append(phase);
    }

    return tmpl;
}

bool LocalDatabase::saveTemplate(const TestTemplate& tmpl)
{
    QJsonObject configJson = testTemplateToJson(tmpl);
    QString configStr = QString::fromUtf8(QJsonDocument(configJson).toJson(QJsonDocument::Compact));

    QSqlQuery query(m_db);
    if (tmpl.templateId < 0) {
        // Insert new template
        query.prepare(
            "INSERT INTO test_templates (name, product_model, total_duration, config_json) "
            "VALUES (?, ?, ?, ?)");
        query.addBindValue(tmpl.name);
        query.addBindValue(tmpl.productModel);
        query.addBindValue(tmpl.totalDurationMinutes);
        query.addBindValue(configStr);
    } else {
        // Update existing template
        query.prepare(
            "UPDATE test_templates SET name=?, product_model=?, total_duration=?, config_json=? "
            "WHERE template_id=?");
        query.addBindValue(tmpl.name);
        query.addBindValue(tmpl.productModel);
        query.addBindValue(tmpl.totalDurationMinutes);
        query.addBindValue(configStr);
        query.addBindValue(tmpl.templateId);
    }

    if (!query.exec()) {
        qWarning() << "LocalDatabase: save template error:" << query.lastError().text();
        return false;
    }
    return true;
}

QVector<TestTemplate> LocalDatabase::loadAllTemplates()
{
    QVector<TestTemplate> results;

    QSqlQuery query(m_db);
    if (query.exec("SELECT template_id, name, product_model, total_duration, config_json "
                   "FROM test_templates ORDER BY template_id ASC")) {
        while (query.next()) {
            int tid = query.value(0).toInt();
            QString name = query.value(1).toString();
            QString productModel = query.value(2).toString();
            int totalDuration = query.value(3).toInt();
            QString configStr = query.value(4).toString();

            QJsonDocument doc = QJsonDocument::fromJson(configStr.toUtf8());
            if (doc.isObject()) {
                results.append(jsonToTestTemplate(tid, name, productModel, totalDuration, doc.object()));
            }
        }
    }

    return results;
}

TestTemplate LocalDatabase::loadTemplate(int templateId)
{
    TestTemplate tmpl;

    QSqlQuery query(m_db);
    query.prepare("SELECT template_id, name, product_model, total_duration, config_json "
                  "FROM test_templates WHERE template_id=?");
    query.addBindValue(templateId);

    if (query.exec() && query.next()) {
        int tid = query.value(0).toInt();
        QString name = query.value(1).toString();
        QString productModel = query.value(2).toString();
        int totalDuration = query.value(3).toInt();
        QString configStr = query.value(4).toString();

        QJsonDocument doc = QJsonDocument::fromJson(configStr.toUtf8());
        if (doc.isObject()) {
            tmpl = jsonToTestTemplate(tid, name, productModel, totalDuration, doc.object());
        }
    }

    return tmpl;
}

bool LocalDatabase::deleteTemplate(int templateId)
{
    QSqlQuery query(m_db);
    query.prepare("DELETE FROM test_templates WHERE template_id=?");
    query.addBindValue(templateId);

    if (!query.exec()) {
        qWarning() << "LocalDatabase: delete template error:" << query.lastError().text();
        return false;
    }
    return query.numRowsAffected() > 0;
}

// ---------------------------------------------------------------------------
// cleanOldData
// ---------------------------------------------------------------------------

bool LocalDatabase::cleanOldData(int retainDays)
{
    if (retainDays <= 0) {
        return true;
    }

    QDateTime cutoff = QDateTime::currentDateTime().addDays(-retainDays);
    QString cutoffDateStr = cutoff.toString("yyyyMMdd");

    // Get all daily tables
    QSqlQuery query(m_db);
    if (!query.exec("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'device_data_%'")) {
        qWarning() << "LocalDatabase: clean old data query error:" << query.lastError().text();
        return false;
    }

    QStringList tablesToDrop;
    while (query.next()) {
        QString tableName = query.value(0).toString();
        // Extract the date portion: "device_data_YYYYMMDD"
        QString datePortion = tableName.mid(12); // after "device_data_"
        if (datePortion < cutoffDateStr) {
            tablesToDrop.append(tableName);
        }
    }

    m_db.transaction();
    for (const auto& table : tablesToDrop) {
        QString dropSql = QString("DROP TABLE IF EXISTS %1").arg(table);
        if (!m_db.exec(dropSql)) {
            qWarning() << "LocalDatabase: drop table error:" << m_db.lastError().text();
            m_db.rollback();
            return false;
        }

        // Also drop the associated index
        QString indexName = "idx_" + table.mid(12) + "_device_ts";
        QString dropIndexSql = QString("DROP INDEX IF EXISTS %1").arg(indexName);
        m_db.exec(dropIndexSql); // Non-fatal if index doesn't exist
    }

    // Clean old alarm records
    QSqlQuery cleanAlarms(m_db);
    cleanAlarms.prepare("DELETE FROM alarms WHERE timestamp < ?");
    cleanAlarms.addBindValue(cutoff.toString(Qt::ISODate));
    cleanAlarms.exec();

    // Clean old test records
    QSqlQuery cleanTests(m_db);
    cleanTests.prepare("DELETE FROM test_records WHERE created_at < ?");
    cleanTests.addBindValue(cutoff.toString(Qt::ISODate));
    cleanTests.exec();

    return m_db.commit();
}
