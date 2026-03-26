#pragma once

#include <QObject>
#include <QString>
#include <QVariantMap>
#include <QVariantList>

class ExcelReportGenerator : public QObject {
    Q_OBJECT
public:
    explicit ExcelReportGenerator(QObject* parent = nullptr);

    bool generateReport(int testRecordId, const QString& filePath);

private:
    bool writeSummarySection(QTextStream& stream, const QVariantMap& recordInfo);
    bool writeAlarmsSection(QTextStream& stream, const QVariantList& alarms);
    bool writeDataSection(QTextStream& stream, int deviceId,
                          const QDateTime& startTime, const QDateTime& endTime);
    bool writeStatisticsSection(QTextStream& stream, const QVariantList& stats);

    static QString csvEscape(const QString& field);
    static QString csvHeader();
};
