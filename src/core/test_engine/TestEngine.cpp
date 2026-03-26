#include "core/test_engine/TestEngine.h"
#include "core/alarm_engine/AlarmEngine.h"
#include "core/template_manager/TemplateManager.h"
#include "core/data_bus/DataBus.h"
#include "storage/DatabaseManager.h"
#include "core/common/ChannelInfo.h"
#include <QDebug>

TestEngine::TestEngine(QObject* parent)
    : QObject(parent)
{
    m_tickTimer.setInterval(1000);  // 1-second interval
    connect(&m_tickTimer, &QTimer::timeout, this, &TestEngine::onTick);
}

void TestEngine::setAlarmEngine(AlarmEngine* engine)
{
    m_alarmEngine = engine;
}

void TestEngine::setTemplateManager(TemplateManager* manager)
{
    m_templateManager = manager;
}

bool TestEngine::startTest(int channelId, int templateId)
{
    // Reject if a test is already active on this channel
    auto it = m_contexts.find(channelId);
    if (it != m_contexts.end() && it->state != TestState::Idle
        && it->state != TestState::Completed
        && it->state != TestState::Interrupted) {
        qWarning() << "TestEngine: channel" << channelId << "already has an active test";
        return false;
    }

    // Load template from TemplateManager
    if (!m_templateManager) {
        qWarning() << "TestEngine: TemplateManager not set";
        return false;
    }
    TestTemplate tmpl = m_templateManager->getTemplate(templateId);
    if (tmpl.templateId == -1) {
        qWarning() << "TestEngine: template" << templateId << "not found";
        return false;
    }

    // Create and configure test context
    TestContext ctx;
    ctx.state = TestState::Starting;
    ctx.templateId = templateId;
    ctx.templateData = tmpl;
    ctx.startTime = QDateTime::currentDateTime();
    ctx.pausedSeconds = 0;
    ctx.hasAlarm = false;

    m_contexts[channelId] = ctx;

    // Load channel info to get the device ID for alarm thresholds
    QVector<ChannelInfo> channels = DatabaseManager::instance().localDb()->loadAllChannels();
    int deviceId = -1;
    for (const ChannelInfo& ch : channels) {
        if (ch.channelId == channelId) {
            deviceId = ch.powerControllerId;
            break;
        }
    }

    // Set alarm thresholds on AlarmEngine for this channel's device
    if (m_alarmEngine && deviceId != -1) {
        m_alarmEngine->setActiveThresholds(deviceId, tmpl.defaultThresholds);
        if (!tmpl.phases.isEmpty()) {
            m_alarmEngine->setPhaseThresholds(deviceId, tmpl.phases);
        }
        m_alarmEngine->setPhaseStartTime(deviceId, ctx.startTime);
    }

    // Save test record to database (start_time = now, result = Pending)
    DatabaseManager::instance().localDb()->saveTestRecord(
        deviceId,       // deviceId
        QString(),      // sn — will be set by channel manager
        QString(),      // pn — will be set by channel manager
        tmpl.name,      // templateName
        ctx.startTime,  // startTime
        QDateTime(),    // endTime — not yet known
        static_cast<int>(TestResult::Pending)
    );

    // Transition to Running and notify
    m_contexts[channelId].state = TestState::Running;

    // Start the shared tick timer if not already running
    if (!m_tickTimer.isActive()) {
        m_tickTimer.start();
    }

    emit testStarted(channelId);
    qDebug() << "TestEngine: started test on channel" << channelId
             << "with template" << tmpl.name;
    return true;
}

bool TestEngine::pauseTest(int channelId)
{
    auto it = m_contexts.find(channelId);
    if (it == m_contexts.end() || it->state != TestState::Running) {
        qWarning() << "TestEngine: cannot pause channel" << channelId
                   << "— not in Running state";
        return false;
    }

    it->state = TestState::Paused;
    it->pauseTime = QDateTime::currentDateTime();

    emit testPaused(channelId);
    qDebug() << "TestEngine: paused test on channel" << channelId;
    return true;
}

bool TestEngine::resumeTest(int channelId)
{
    auto it = m_contexts.find(channelId);
    if (it == m_contexts.end() || it->state != TestState::Paused) {
        qWarning() << "TestEngine: cannot resume channel" << channelId
                   << "— not in Paused state";
        return false;
    }

    // Calculate how long the test was paused and accumulate it
    qint64 pauseDuration = it->pauseTime.secsTo(QDateTime::currentDateTime());
    it->pausedSeconds += static_cast<int>(pauseDuration);
    it->state = TestState::Running;

    emit testResumed(channelId);
    qDebug() << "TestEngine: resumed test on channel" << channelId;
    return true;
}

bool TestEngine::stopTest(int channelId, TestResult result)
{
    auto it = m_contexts.find(channelId);
    if (it == m_contexts.end() || (it->state != TestState::Running
                                    && it->state != TestState::Paused)) {
        qWarning() << "TestEngine: cannot stop channel" << channelId
                   << "— not in Running or Paused state";
        return false;
    }

    // Set final state
    if (result == TestResult::Passed || result == TestResult::Failed) {
        it->state = TestState::Completed;
    } else {
        it->state = TestState::Interrupted;
    }

    // Load channel info to get the device ID
    QVector<ChannelInfo> channels = DatabaseManager::instance().localDb()->loadAllChannels();
    int deviceId = -1;
    for (const ChannelInfo& ch : channels) {
        if (ch.channelId == channelId) {
            deviceId = ch.powerControllerId;
            break;
        }
    }

    // Clear alarm thresholds on AlarmEngine
    if (m_alarmEngine && deviceId != -1) {
        m_alarmEngine->clearThresholds(deviceId);
    }

    // Update test record in database (end_time = now, result)
    QDateTime endTime = QDateTime::currentDateTime();
    DatabaseManager::instance().localDb()->saveTestRecord(
        deviceId,
        QString(),
        QString(),
        it->templateData.name,
        it->startTime,
        endTime,
        static_cast<int>(result)
    );

    emit testCompleted(channelId, result);
    qDebug() << "TestEngine: stopped test on channel" << channelId
             << "with result" << static_cast<int>(result);

    // Stop the tick timer if no tests are running
    bool anyRunning = false;
    for (auto ctxIt = m_contexts.constBegin(); ctxIt != m_contexts.constEnd(); ++ctxIt) {
        if (ctxIt->state == TestState::Running || ctxIt->state == TestState::Paused) {
            anyRunning = true;
            break;
        }
    }
    if (!anyRunning) {
        m_tickTimer.stop();
    }

    return true;
}

TestEngine::TestState TestEngine::testState(int channelId) const
{
    auto it = m_contexts.constFind(channelId);
    if (it == m_contexts.constEnd()) {
        return TestState::Idle;
    }
    return it->state;
}

QDateTime TestEngine::testStartTime(int channelId) const
{
    auto it = m_contexts.constFind(channelId);
    if (it == m_contexts.constEnd()) {
        return QDateTime();
    }
    return it->startTime;
}

int TestEngine::elapsedSeconds(int channelId) const
{
    auto it = m_contexts.constFind(channelId);
    if (it == m_contexts.constEnd()) {
        return 0;
    }

    int totalSeconds = it->startTime.secsTo(QDateTime::currentDateTime());
    totalSeconds -= it->pausedSeconds;

    // If currently paused, subtract the ongoing pause duration
    if (it->state == TestState::Paused && it->pauseTime.isValid()) {
        totalSeconds -= static_cast<int>(it->pauseTime.secsTo(QDateTime::currentDateTime()));
    }

    return qMax(totalSeconds, 0);
}

int TestEngine::remainingSeconds(int channelId) const
{
    auto it = m_contexts.constFind(channelId);
    if (it == m_contexts.constEnd()) {
        return 0;
    }

    int totalDuration = it->templateData.totalDurationMinutes * 60;
    int elapsed = elapsedSeconds(channelId);
    return qMax(totalDuration - elapsed, 0);
}

void TestEngine::onTick()
{
    // Iterate over a copy of keys to allow safe modification during iteration
    QList<int> keys = m_contexts.keys();
    for (int channelId : keys) {
        auto it = m_contexts.find(channelId);
        if (it == m_contexts.end() || it->state != TestState::Running) {
            continue;
        }

        int elapsed = elapsedSeconds(channelId);
        int total = it->templateData.totalDurationMinutes * 60;
        emit testProgress(channelId, elapsed, total);

        checkAutoComplete(channelId);
    }
}

void TestEngine::checkAutoComplete(int channelId)
{
    auto it = m_contexts.find(channelId);
    if (it == m_contexts.end() || it->state != TestState::Running) {
        return;
    }

    int elapsed = elapsedSeconds(channelId);
    int totalDuration = it->templateData.totalDurationMinutes * 60;

    if (elapsed >= totalDuration) {
        // Auto-complete: Passed if no alarm occurred, Failed otherwise
        TestResult result = it->hasAlarm ? TestResult::Failed : TestResult::Passed;
        stopTest(channelId, result);
        qDebug() << "TestEngine: auto-completed test on channel" << channelId
                 << "result =" << (it->hasAlarm ? "Failed" : "Passed");
    }
}
