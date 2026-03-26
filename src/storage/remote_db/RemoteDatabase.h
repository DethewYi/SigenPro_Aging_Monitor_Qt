#pragma once

#include <QObject>
#include <QSqlDatabase>
#include <QVector>
#include "core/common/DeviceData.h"
#include "core/common/AlarmRecord.h"

class RemoteDatabase : public QObject {
    Q_OBJECT
public:
    explicit RemoteDatabase(QObject* parent = nullptr);
    ~RemoteDatabase();

    bool connect(const QString& host, int port, const QString& dbName,
                 const QString& user, const QString& password, const QString& dbType);
    void disconnect();
    bool isConnected() const;

    bool createMetaTables();
    bool createMonthlyTable(const QString& monthStr); // format: YYYYMM
    bool insertDeviceDataBatch(const QVector<DeviceData>& dataList);
    bool insertAlarmRecords(const QVector<AlarmRecord>& records);
    QVector<DeviceData> queryDeviceData(int deviceId, const QDateTime& start, const QDateTime& end);
    QVector<AlarmRecord> queryAlarms(const QDateTime& start, int limit = 100);

private:
    QSqlDatabase m_db;
    bool m_connected = false;
    QString m_connectionName;
};
