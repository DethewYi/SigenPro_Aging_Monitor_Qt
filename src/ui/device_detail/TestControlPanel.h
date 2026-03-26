#pragma once

#include <QWidget>

class QLabel;
class QPushButton;
class QProgressBar;

class TestControlPanel : public QWidget {
    Q_OBJECT
public:
    explicit TestControlPanel(QWidget* parent = nullptr);

    void setTemplateInfo(const QString& templateName, int totalMinutes);
    void setProgress(int elapsedSeconds, int totalSeconds);
    void setTestState(const QString& stateText);

signals:
    void startClicked();
    void pauseClicked();
    void stopClicked();

private:
    QLabel* m_templateLabel = nullptr;
    QLabel* m_stateLabel = nullptr;
    QProgressBar* m_progressBar = nullptr;
    QLabel* m_timeLabel = nullptr;
    QPushButton* m_startBtn = nullptr;
    QPushButton* m_pauseBtn = nullptr;
    QPushButton* m_stopBtn = nullptr;
};
