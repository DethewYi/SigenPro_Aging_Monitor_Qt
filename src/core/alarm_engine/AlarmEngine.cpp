#include "core/alarm_engine/AlarmEngine.h"
#include "core/data_bus/DataBus.h"
#include "storage/DatabaseManager.h"
#include <QDebug>

AlarmEngine::AlarmEngine(QObject* parent)
    : QObject(parent)
{
    connect(&DataBus::instance(), &DataBus::deviceDataReceived,
            this, &AlarmEngine::onDeviceDataReceived);
}

void AlarmEngine::setActiveThresholds(int deviceId, const QMap<QString, AlarmThreshold>& thresholds)
{
    m_deviceContexts[deviceId].defaultThresholds = thresholds;
}

void AlarmEngine::setPhaseThresholds(int deviceId, const QVector<TestPhase>& phases)
{
    m_deviceContexts[deviceId].phases = phases;
}

void AlarmEngine::clearThresholds(int deviceId)
{
    m_deviceContexts.remove(deviceId);
    m_activeAlarms.remove(deviceId);
}

void AlarmEngine::setPhaseStartTime(int deviceId, const QDateTime& startTime)
{
    m_deviceContexts[deviceId].phaseStartTime = startTime;
    // Reset alarm states when a new test phase sequence begins
    m_activeAlarms[deviceId].clear();
}

void AlarmEngine::acknowledgeAlarm(int alarmId)
{
    DatabaseManager::instance().localDb()->acknowledgeAlarm(alarmId);
}

void AlarmEngine::onDeviceDataReceived(const DeviceData& data)
{
    if (!data.communicationOk) {
        return;
    }
    checkThresholds(data);
}

void AlarmEngine::checkThresholds(const DeviceData& data)
{
    int deviceId = data.deviceId;
    QSet<QString>& activeSet = m_activeAlarms[deviceId];

    for (auto it = data.parameters.constBegin(); it != data.parameters.constEnd(); ++it) {
        const QString& paramName = it.key();
        double value = it.value();

        const AlarmThreshold* threshold = getCurrentThresholds(deviceId, paramName);
        if (!threshold || !threshold->enabled) {
            // If no threshold or disabled and alarm was active, clear it
            activeSet.remove(paramName);
            continue;
        }

        bool exceedsUpper = threshold->upperLimit > 0 && value > threshold->upperLimit;
        bool exceedsLower = threshold->lowerLimit > 0 && value < threshold->lowerLimit;
        bool inAlarm = exceedsUpper || exceedsLower;

        if (inAlarm && !activeSet.contains(paramName)) {
            // New alarm — record it
            AlarmRecord record;
            record.timestamp = data.timestamp;
            record.deviceId = deviceId;
            record.paramName = paramName;
            record.currentValue = value;
            record.isUpperLimit = exceedsUpper;
            record.acknowledged = false;

            if (exceedsUpper) {
                record.threshold = threshold->upperLimit;
                record.message = QString("%1 = %2 exceeds upper limit %3")
                    .arg(paramName).arg(value).arg(threshold->upperLimit);
            } else {
                record.threshold = threshold->lowerLimit;
                record.message = QString("%1 = %2 below lower limit %3")
                    .arg(paramName).arg(value).arg(threshold->lowerLimit);
            }

            // Publish via DataBus and persist to database
            DataBus::instance().publishAlarm(record);
            DatabaseManager::instance().localDb()->insertAlarmRecord(record);

            activeSet.insert(paramName);
        } else if (!inAlarm && activeSet.contains(paramName)) {
            // Value returned to normal range — clear hysteresis state so it can re-trigger
            activeSet.remove(paramName);
        }
    }
}

const AlarmThreshold* AlarmEngine::getCurrentThresholds(int deviceId, const QString& paramName) const
{
    auto ctxIt = m_deviceContexts.constFind(deviceId);
    if (ctxIt == m_deviceContexts.constEnd()) {
        return nullptr;
    }

    const DeviceAlarmContext& ctx = ctxIt.value();

    // If phases are configured and a start time is set, determine current phase
    if (!ctx.phases.isEmpty() && ctx.phaseStartTime.isValid()) {
        qint64 elapsedSeconds = ctx.phaseStartTime.secsTo(QDateTime::currentDateTime());
        qint64 elapsedMinutes = elapsedSeconds / 60;

        qint64 accumulated = 0;
        for (const TestPhase& phase : ctx.phases) {
            accumulated += phase.durationMinutes;
            if (elapsedMinutes < accumulated) {
                // We are in this phase — check if it has a threshold for this param
                auto threshIt = phase.thresholds.constFind(paramName);
                if (threshIt != phase.thresholds.constEnd()) {
                    return &(threshIt.value());
                }
                // Phase found but no specific threshold for this param — fall through to default
                break;
            }
        }
        // If elapsed time exceeds all phases, fall through to default thresholds
    }

    // Use default thresholds
    auto threshIt = ctx.defaultThresholds.constFind(paramName);
    if (threshIt != ctx.defaultThresholds.constEnd()) {
        return &(threshIt.value());
    }

    return nullptr;
}
