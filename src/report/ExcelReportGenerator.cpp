#include "ExcelReportGenerator.h"

#include <QFile>
#include <QTextStream>
#include <QDateTime>
#include <QSqlQuery>
#include <QSqlError>
#include <QDebug>

#include "storage/DatabaseManager.h"

// ---------------------------------------------------------------------------
// Construction
// ---------------------------------------------------------------------------

ExcelReportGenerator::ExcelReportGenerator(QObject* parent)
    : QObject(parent)
{
}

// ---------------------------------------------------------------------------
// csvEscape - escape a field for CSV output
// ---------------------------------------------------------------------------

QString ExcelReportGenerator::csvEscape(const QString& field)
{
    if (field.contains(',') || field.contains('"') || field.contains('\n') || field.contains('\r')) {
        QString escaped = field;
        escaped.replace("\"", "\"\"");
        return "\"" + escaped + "\"";
    }
    return field;
}

// ---------------------------------------------------------------------------
// csvHeader - UTF-8 BOM for Excel compatibility
// ---------------------------------------------------------------------------

QString ExcelReportGenerator::csvHeader()
{
    return QString("\xEF\xBB\xBF");  // UTF-8 BOM
}

// ---------------------------------------------------------------------------
// generateReport
// ---------------------------------------------------------------------------

bool ExcelReportGenerator::generateReport(int testRecordId, const QString& filePath)
{
    // 1. Load test record from database
    auto* db = DatabaseManager::instance().localDb();
    QSqlQuery query(db->m_db);
    query.prepare(
        "SELECT id, device_id, sn, pn, template_name, start_time, end_time, result, created_at "
        "FROM test_records WHERE id = ?");
    query.addBindValue(testRecordId);

    if (!query.exec() || !query.next()) {
        qWarning() << tr("ExcelReportGenerator: test record %1 not found").arg(testRecordId);
        return false;
    }

    QVariantMap recordInfo;
    recordInfo["id"] = query.value(0).toInt();
    recordInfo["device_id"] = query.value(1).toInt();
    recordInfo["sn"] = query.value(2).toString();
    recordInfo["pn"] = query.value(3).toString();
    recordInfo["template_name"] = query.value(4).toString();
    recordInfo["start_time"] = query.value(5).toString();
    recordInfo["end_time"] = query.value(6).toString();
    recordInfo["result"] = query.value(7).toInt();
    recordInfo["created_at"] = query.value(8).toString();

    // Get device name
    int deviceId = recordInfo["device_id"].toInt();
    QSqlQuery devQuery(db->m_db);
    devQuery.prepare("SELECT name FROM devices WHERE device_id = ?");
    devQuery.addBindValue(deviceId);
    if (devQuery.exec() && devQuery.next()) {
        recordInfo["device_name"] = devQuery.value(0).toString();
    } else {
        recordInfo["device_name"] = tr("Unknown");
    }

    // 2. Load alarm records
    QString startTime = recordInfo["start_time"].toString();
    QVariantList alarms;
    QSqlQuery alarmQuery(db->m_db);
    alarmQuery.prepare(
        "SELECT timestamp, device_name, param_name, current_value, threshold, is_upper_limit, message "
        "FROM alarms WHERE device_id = ? AND timestamp >= ? AND timestamp <= ? "
        "ORDER BY timestamp ASC");
    alarmQuery.addBindValue(deviceId);
    alarmQuery.addBindValue(startTime);
    alarmQuery.addBindValue(recordInfo["end_time"].toString());

    if (alarmQuery.exec()) {
        while (alarmQuery.next()) {
            QVariantMap alarm;
            alarm["timestamp"] = alarmQuery.value(0).toString();
            alarm["device_name"] = alarmQuery.value(1).toString();
            alarm["param_name"] = alarmQuery.value(2).toString();
            alarm["current_value"] = alarmQuery.value(3).toDouble();
            alarm["threshold"] = alarmQuery.value(4).toDouble();
            alarm["is_upper_limit"] = alarmQuery.value(5).toInt() != 0;
            alarm["message"] = alarmQuery.value(6).toString();
            alarms.append(alarm);
        }
    }

    // 3. Calculate statistics from device data
    QDateTime startDt = QDateTime::fromString(startTime, Qt::ISODate);
    QDateTime endDt = QDateTime::fromString(recordInfo["end_time"].toString(), Qt::ISODate);
    QVector<DeviceData> deviceDataList = db->queryDeviceData(deviceId, startDt, endDt);

    QMap<QString, QVector<double>> paramDataMap;
    for (const auto& dd : deviceDataList) {
        for (auto it = dd.parameters.constBegin(); it != dd.parameters.constEnd(); ++it) {
            paramDataMap[it.key()].append(it.value());
        }
    }

    QVariantList stats;
    for (auto it = paramDataMap.constBegin(); it != paramDataMap.constEnd(); ++it) {
        const auto& values = it.value();
        if (values.isEmpty()) continue;

        double minVal = values.first();
        double maxVal = values.first();
        double sum = 0.0;
        for (double v : values) {
            if (v < minVal) minVal = v;
            if (v > maxVal) maxVal = v;
            sum += v;
        }
        double avg = sum / values.size();

        QVariantMap stat;
        stat["param_name"] = it.key();
        stat["min"] = minVal;
        stat["max"] = maxVal;
        stat["avg"] = avg;
        stat["count"] = values.size();
        stats.append(stat);
    }

    // 4. Write CSV file
    QFile file(filePath);
    if (!file.open(QIODevice::WriteOnly | QIODevice::Text)) {
        qWarning() << tr("ExcelReportGenerator: failed to open file: %1").arg(filePath);
        return false;
    }

    QTextStream stream(&file);
    stream.setEncoding(QStringConverter::Utf8);

    // Write BOM
    stream << csvHeader();

    // Write sections
    writeSummarySection(stream, recordInfo);
    stream << "\n\n";
    writeStatisticsSection(stream, stats);
    stream << "\n\n";
    writeAlarmsSection(stream, alarms);
    stream << "\n\n";
    writeDataSection(stream, deviceId, startDt, endDt);

    file.close();
    return true;
}

// ---------------------------------------------------------------------------
// writeSummarySection
// ---------------------------------------------------------------------------

bool ExcelReportGenerator::writeSummarySection(QTextStream& stream, const QVariantMap& recordInfo)
{
    stream << csvEscape(tr("=== Test Summary ===")) << "\n\n";

    // Calculate duration
    QDateTime startDt = QDateTime::fromString(recordInfo["start_time"].toString(), Qt::ISODate);
    QDateTime endDt = QDateTime::fromString(recordInfo["end_time"].toString(), Qt::ISODate);
    qint64 durationSecs = startDt.secsTo(endDt);
    int hours = static_cast<int>(durationSecs / 3600);
    int minutes = static_cast<int>((durationSecs % 3600) / 60);
    int seconds = static_cast<int>(durationSecs % 60);
    QString durationStr = QString("%1h %2m %3s").arg(hours).arg(minutes, 2, 10, QChar('0')).arg(seconds, 2, 10, QChar('0'));

    // Result text
    int resultVal = recordInfo["result"].toInt();
    QString resultText;
    switch (resultVal) {
    case 0: resultText = tr("Pending"); break;
    case 1: resultText = tr("Passed"); break;
    case 2: resultText = tr("Failed"); break;
    case 3: resultText = tr("Interrupted"); break;
    default: resultText = tr("Unknown"); break;
    }

    stream << csvEscape(tr("Item")) << "," << csvEscape(tr("Value")) << "\n";
    stream << csvEscape(tr("Report Generated")) << "," << csvEscape(QDateTime::currentDateTime().toString(Qt::ISODate)) << "\n";
    stream << csvEscape(tr("Record ID")) << "," << csvEscape(QString::number(recordInfo["id"].toInt())) << "\n";
    stream << csvEscape(tr("Device Name")) << "," << csvEscape(recordInfo["device_name"].toString()) << "\n";
    stream << csvEscape(tr("Device SN")) << "," << csvEscape(recordInfo["sn"].toString()) << "\n";
    stream << csvEscape(tr("Product PN")) << "," << csvEscape(recordInfo["pn"].toString()) << "\n";
    stream << csvEscape(tr("Template")) << "," << csvEscape(recordInfo["template_name"].toString()) << "\n";
    stream << csvEscape(tr("Start Time")) << "," << csvEscape(recordInfo["start_time"].toString()) << "\n";
    stream << csvEscape(tr("End Time")) << "," << csvEscape(recordInfo["end_time"].toString()) << "\n";
    stream << csvEscape(tr("Duration")) << "," << csvEscape(durationStr) << "\n";
    stream << csvEscape(tr("Result")) << "," << csvEscape(resultText) << "\n";

    return true;
}

// ---------------------------------------------------------------------------
// writeStatisticsSection
// ---------------------------------------------------------------------------

bool ExcelReportGenerator::writeStatisticsSection(QTextStream& stream, const QVariantList& stats)
{
    stream << csvEscape(tr("=== Statistical Summary ===")) << "\n\n";

    stream << csvEscape(tr("Parameter")) << ","
           << csvEscape(tr("Min")) << ","
           << csvEscape(tr("Max")) << ","
           << csvEscape(tr("Avg")) << ","
           << csvEscape(tr("Count")) << "\n";

    for (const auto& stat : stats) {
        const QVariantMap& s = stat.toMap();
        stream << csvEscape(s["param_name"].toString()) << ","
               << csvEscape(QString::number(s["min"].toDouble(), 'f', 6)) << ","
               << csvEscape(QString::number(s["max"].toDouble(), 'f', 6)) << ","
               << csvEscape(QString::number(s["avg"].toDouble(), 'f', 6)) << ","
               << csvEscape(QString::number(s["count"].toInt())) << "\n";
    }

    return true;
}

// ---------------------------------------------------------------------------
// writeAlarmsSection
// ---------------------------------------------------------------------------

bool ExcelReportGenerator::writeAlarmsSection(QTextStream& stream, const QVariantList& alarms)
{
    stream << csvEscape(tr("=== Alarm Records ===")) << "\n\n";

    stream << csvEscape(tr("Time")) << ","
           << csvEscape(tr("Device")) << ","
           << csvEscape(tr("Parameter")) << ","
           << csvEscape(tr("Value")) << ","
           << csvEscape(tr("Threshold")) << ","
           << csvEscape(tr("Type")) << ","
           << csvEscape(tr("Message")) << "\n";

    for (const auto& alarm : alarms) {
        const QVariantMap& a = alarm.toMap();
        QString typeStr = a["is_upper_limit"].toBool() ? tr("Upper") : tr("Lower");

        stream << csvEscape(a["timestamp"].toString()) << ","
               << csvEscape(a["device_name"].toString()) << ","
               << csvEscape(a["param_name"].toString()) << ","
               << csvEscape(QString::number(a["current_value"].toDouble(), 'f', 6)) << ","
               << csvEscape(QString::number(a["threshold"].toDouble(), 'f', 6)) << ","
               << csvEscape(typeStr) << ","
               << csvEscape(a["message"].toString()) << "\n";
    }

    return true;
}

// ---------------------------------------------------------------------------
// writeDataSection
// ---------------------------------------------------------------------------

bool ExcelReportGenerator::writeDataSection(QTextStream& stream, int deviceId,
                                             const QDateTime& startTime, const QDateTime& endTime)
{
    stream << csvEscape(tr("=== Raw Data ===")) << "\n\n";

    auto* db = DatabaseManager::instance().localDb();
    QVector<DeviceData> dataList = db->queryDeviceData(deviceId, startTime, endTime);

    if (dataList.isEmpty()) {
        stream << csvEscape(tr("No data available")) << "\n";
        return true;
    }

    // Collect all parameter keys
    QSet<QString> paramKeys;
    for (const auto& dd : dataList) {
        for (auto it = dd.parameters.constBegin(); it != dd.parameters.constEnd(); ++it) {
            paramKeys.insert(it.key());
        }
    }

    QStringList keys = paramKeys.values();
    keys.sort();

    // Header row
    stream << csvEscape(tr("Timestamp"));
    for (const auto& key : keys) {
        stream << "," << csvEscape(key);
    }
    stream << "\n";

    // Data rows
    for (const auto& dd : dataList) {
        stream << csvEscape(dd.timestamp.toString(Qt::ISODate));
        for (const auto& key : keys) {
            stream << ",";
            if (dd.parameters.contains(key)) {
                stream << csvEscape(QString::number(dd.parameters[key], 'f', 6));
            }
        }
        stream << "\n";
    }

    return true;
}
