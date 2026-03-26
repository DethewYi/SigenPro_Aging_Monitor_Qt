#pragma once

#include <QObject>
#include <QMap>
#include <QSet>
#include <QDateTime>
#include "core/common/DeviceData.h"
#include "core/common/AlarmRecord.h"
#include "core/common/TestTemplate.h"

class AlarmEngine : public QObject {
    Q_OBJECT
public:
    explicit AlarmEngine(QObject* parent = nullptr);

    void setActiveThresholds(int deviceId, const QMap<QString, AlarmThreshold>& thresholds);
    void setPhaseThresholds(int deviceId, const QVector<TestPhase>& phases);
    void clearThresholds(int deviceId);
    void setPhaseStartTime(int deviceId, const QDateTime& startTime);
    void acknowledgeAlarm(int alarmId);

private slots:
    void onDeviceDataReceived(const DeviceData& data);

private:
    void checkThresholds(const DeviceData& data);
    const AlarmThreshold* getCurrentThresholds(int deviceId, const QString& paramName) const;

    struct DeviceAlarmContext {
        QMap<QString, AlarmThreshold> defaultThresholds;
        QVector<TestPhase> phases;
        QDateTime phaseStartTime;
    };

    // Track which (device, param) pairs currently have active alarms for hysteresis
    QMap<int, QSet<QString>> m_activeAlarms;

    QMap<int, DeviceAlarmContext> m_deviceContexts;
};
