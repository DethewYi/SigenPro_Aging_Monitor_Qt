#include "TestControlPanel.h"
#include <QHBoxLayout>
#include <QVBoxLayout>
#include <QLabel>
#include <QPushButton>
#include <QProgressBar>
#include <QFont>

TestControlPanel::TestControlPanel(QWidget* parent)
    : QWidget(parent)
{
    QHBoxLayout* mainLayout = new QHBoxLayout(this);
    mainLayout->setContentsMargins(8, 8, 8, 8);

    // Left side: template info + progress
    QVBoxLayout* infoLayout = new QVBoxLayout();

    m_templateLabel = new QLabel(tr("Template: --"), this);
    QFont labelFont;
    labelFont.setPointSize(11);
    m_templateLabel->setFont(labelFont);
    infoLayout->addWidget(m_templateLabel);

    QHBoxLayout* progressLayout = new QHBoxLayout();

    m_stateLabel = new QLabel(tr("Idle"), this);
    progressLayout->addWidget(m_stateLabel);

    m_progressBar = new QProgressBar(this);
    m_progressBar->setRange(0, 100);
    m_progressBar->setValue(0);
    m_progressBar->setMinimumWidth(200);
    m_progressBar->setMaximumWidth(500);
    progressLayout->addWidget(m_progressBar);

    m_timeLabel = new QLabel(tr("00:00:00 / 00:00:00"), this);
    progressLayout->addWidget(m_timeLabel);

    infoLayout->addLayout(progressLayout);
    mainLayout->addLayout(infoLayout, 1);

    // Right side: control buttons
    QHBoxLayout* btnLayout = new QHBoxLayout();
    btnLayout->setSpacing(8);

    m_startBtn = new QPushButton(tr("Start"), this);
    m_startBtn->setFixedWidth(80);
    m_startBtn->setCursor(Qt::PointingHandCursor);

    m_pauseBtn = new QPushButton(tr("Pause"), this);
    m_pauseBtn->setFixedWidth(80);
    m_pauseBtn->setCursor(Qt::PointingHandCursor);
    m_pauseBtn->setEnabled(false);

    m_stopBtn = new QPushButton(tr("Stop"), this);
    m_stopBtn->setFixedWidth(80);
    m_stopBtn->setCursor(Qt::PointingHandCursor);
    m_stopBtn->setEnabled(false);

    btnLayout->addWidget(m_startBtn);
    btnLayout->addWidget(m_pauseBtn);
    btnLayout->addWidget(m_stopBtn);
    mainLayout->addLayout(btnLayout);

    // Connect signals
    connect(m_startBtn, &QPushButton::clicked, this, &TestControlPanel::startClicked);
    connect(m_pauseBtn, &QPushButton::clicked, this, &TestControlPanel::pauseClicked);
    connect(m_stopBtn, &QPushButton::clicked, this, &TestControlPanel::stopClicked);
}

void TestControlPanel::setTemplateInfo(const QString& templateName, int totalMinutes)
{
    m_templateLabel->setText(tr("Template: %1 (%2 min)").arg(templateName).arg(totalMinutes));
}

void TestControlPanel::setProgress(int elapsedSeconds, int totalSeconds)
{
    if (totalSeconds > 0) {
        int percent = static_cast<int>(100.0 * elapsedSeconds / totalSeconds);
        m_progressBar->setValue(percent);
    } else {
        m_progressBar->setValue(0);
    }

    auto formatTime = [](int seconds) -> QString {
        int h = seconds / 3600;
        int m = (seconds % 3600) / 60;
        int s = seconds % 60;
        return QString("%1:%2:%3")
            .arg(h, 2, 10, QLatin1Char('0'))
            .arg(m, 2, 10, QLatin1Char('0'))
            .arg(s, 2, 10, QLatin1Char('0'));
    };

    m_timeLabel->setText(tr("%1 / %2").arg(formatTime(elapsedSeconds)).arg(formatTime(totalSeconds)));
}

void TestControlPanel::setTestState(const QString& stateText)
{
    m_stateLabel->setText(stateText);

    bool isRunning = (stateText == tr("Running"));
    bool isPaused = (stateText == tr("Paused"));

    m_startBtn->setEnabled(!isRunning && !isPaused);
    m_pauseBtn->setEnabled(isRunning);
    m_stopBtn->setEnabled(isRunning || isPaused);
}
