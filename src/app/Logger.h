#pragma once

#include <QObject>
#include <QString>
#include <QtGlobal>

class QFile;
class QTextStream;

class Logger : public QObject {
    Q_OBJECT
public:
    enum LogLevel { Debug = 0, Info = 1, Warning = 2, Error = 3 };

    static Logger& instance();

    void debug(const QString& msg);
    void info(const QString& msg);
    void warning(const QString& msg);
    void error(const QString& msg);

    static void messageHandler(QtMsgType type, const QMessageLogContext& context, const QString& msg);

    void setLogDir(const QString& dir);
    void setMaxFileSize(int mb);
    void setLogLevel(LogLevel level);

private:
    Logger(QObject* parent = nullptr);
    ~Logger();

    Logger(const Logger&) = delete;
    Logger& operator=(const Logger&) = delete;

    void ensureLogFile();
    void rotateLogFile();
    void writeLog(LogLevel level, const QString& msg);

    QFile* m_logFile = nullptr;
    QTextStream* m_logStream = nullptr;
    QString m_logDir;
    QString m_currentLogFile;
    qint64 m_maxFileSize = 50 * 1024 * 1024; // 50MB
    LogLevel m_logLevel = Info;
    static constexpr int MAX_LOG_FILES = 30;
};
