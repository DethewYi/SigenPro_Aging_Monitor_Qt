#pragma once

#include <QObject>
#include <QSqlDatabase>
#include <QVector>
#include "core/common/DeviceData.h"
#include "core/common/ChannelInfo.h"
#include "core/common/AlarmRecord.h"
#include "core/common/TestTemplate.h"

class LocalDatabase : public QObject {
    Q_OBJECT
public:
    explicit LocalDatabase(QObject* parent = nullptr);
    ~LocalDatabase();

    bool initialize(const QString& dbPath);
    bool createDailyTable(const QString& dateStr); // format: YYYYMMDD
    bool insertDeviceData(const QVector<DeviceData>& dataList);
    QVector<DeviceData> queryDeviceData(int deviceId, const QDateTime& start, const QDateTime& end);
    bool insertAlarmRecord(const AlarmRecord& record);
    QVector<AlarmRecord> queryAlarms(const QDateTime& start, int limit = 100);
    bool acknowledgeAlarm(int alarmId);
    bool saveTestRecord(int deviceId, const QString& sn, const QString& pn,
                        const QString& templateName, const QDateTime& startTime,
                        const QDateTime& endTime, int testResult);
    bool saveChannelInfo(const ChannelInfo& info);
    QVector<ChannelInfo> loadAllChannels();
    bool saveTemplate(const TestTemplate& tmpl);
    QVector<TestTemplate> loadAllTemplates();
    TestTemplate loadTemplate(int templateId);
    bool deleteTemplate(int templateId);
    bool cleanOldData(int retainDays);

private:
    QSqlDatabase m_db;
    QString m_dbPath;
    bool createMetaTables();
    bool ensureDailyTable(const QString& dateStr);
};
