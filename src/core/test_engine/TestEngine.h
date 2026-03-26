#pragma once

#include <QObject>
#include <QTimer>
#include <QDateTime>
#include <QMap>
#include "core/common/Types.h"
#include "core/common/TestTemplate.h"

class AlarmEngine;
class TemplateManager;

class TestEngine : public QObject {
    Q_OBJECT
public:
    enum class TestState {
        Idle,
        Starting,
        Running,
        Paused,
        Completed,
        Interrupted
    };

    explicit TestEngine(QObject* parent = nullptr);

    void setAlarmEngine(AlarmEngine* engine);
    void setTemplateManager(TemplateManager* manager);

    bool startTest(int channelId, int templateId);
    bool pauseTest(int channelId);
    bool resumeTest(int channelId);
    bool stopTest(int channelId, TestResult result = TestResult::Interrupted);
    TestState testState(int channelId) const;
    QDateTime testStartTime(int channelId) const;
    int elapsedSeconds(int channelId) const;
    int remainingSeconds(int channelId) const;

signals:
    void testStarted(int channelId);
    void testPaused(int channelId);
    void testResumed(int channelId);
    void testCompleted(int channelId, TestResult result);
    void testProgress(int channelId, int elapsed, int total);

private slots:
    void onTick();

private:
    void checkAutoComplete(int channelId);

    struct TestContext {
        TestState state = TestState::Idle;
        int templateId = -1;
        TestTemplate templateData;
        QDateTime startTime;
        QDateTime pauseTime;
        int pausedSeconds = 0;
        bool hasAlarm = false;
    };

    QMap<int, TestContext> m_contexts;
    QTimer m_tickTimer;  // 1-second timer for progress tracking and auto-completion

    AlarmEngine* m_alarmEngine = nullptr;
    TemplateManager* m_templateManager = nullptr;
};
