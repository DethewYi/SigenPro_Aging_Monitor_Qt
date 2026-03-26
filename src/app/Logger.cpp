#include "Logger.h"

#include <QFile>
#include <QTextStream>
#include <QDir>
#include <QDateTime>
#include <QCoreApplication>
#include <QThread>
#include <QRegularExpression>

// ---------------------------------------------------------------------------
// Singleton
// ---------------------------------------------------------------------------

Logger& Logger::instance()
{
    static Logger logger;
    return logger;
}

// ---------------------------------------------------------------------------
// Construction / Destruction
// ---------------------------------------------------------------------------

Logger::Logger(QObject* parent)
    : QObject(parent)
{
    // Default log directory
    m_logDir = QCoreApplication::applicationDirPath() + "/logs";
}

Logger::~Logger()
{
    if (m_logStream) {
        m_logStream->flush();
        delete m_logStream;
        m_logStream = nullptr;
    }
    if (m_logFile) {
        m_logFile->close();
        delete m_logFile;
        m_logFile = nullptr;
    }
}

// ---------------------------------------------------------------------------
// Log level convenience methods
// ---------------------------------------------------------------------------

void Logger::debug(const QString& msg)
{
    writeLog(Debug, msg);
}

void Logger::info(const QString& msg)
{
    writeLog(Info, msg);
}

void Logger::warning(const QString& msg)
{
    writeLog(Warning, msg);
}

void Logger::error(const QString& msg)
{
    writeLog(Error, msg);
}

// ---------------------------------------------------------------------------
// messageHandler - static, installed via qInstallMessageHandler
// ---------------------------------------------------------------------------

void Logger::messageHandler(QtMsgType type, const QMessageLogContext& context, const QString& msg)
{
    Q_UNUSED(context)

    LogLevel level;
    switch (type) {
    case QtDebugMsg:
        level = Debug;
        break;
    case QtInfoMsg:
        level = Info;
        break;
    case QtWarningMsg:
        level = Warning;
        break;
    case QtCriticalMsg:
    case QtFatalMsg:
        level = Error;
        break;
    default:
        level = Info;
        break;
    }

    instance().writeLog(level, msg);

    // Fatal messages should still abort
    if (type == QtFatalMsg) {
        abort();
    }
}

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

void Logger::setLogDir(const QString& dir)
{
    m_logDir = dir;
}

void Logger::setMaxFileSize(int mb)
{
    if (mb > 0) {
        m_maxFileSize = static_cast<qint64>(mb) * 1024 * 1024;
    }
}

void Logger::setLogLevel(LogLevel level)
{
    m_logLevel = level;
}

// ---------------------------------------------------------------------------
// ensureLogFile
// ---------------------------------------------------------------------------

void Logger::ensureLogFile()
{
    // If current file is open and valid, keep using it
    if (m_logFile && m_logFile->isOpen()) {
        return;
    }

    // Create log directory if needed
    QDir dir(m_logDir);
    if (!dir.exists()) {
        if (!dir.mkpath(".")) {
            // Cannot create log directory - fall back to temp
            m_logDir = QDir::tempPath() + "/sigenpro_logs";
            QDir fallbackDir(m_logDir);
            if (!fallbackDir.mkpath(".")) {
                return; // Give up silently
            }
        }
    }

    // Generate log file name with timestamp
    QString timestamp = QDateTime::currentDateTime().toString("yyyyMMdd_HHmmss");
    m_currentLogFile = m_logDir + "/aging_monitor_" + timestamp + ".log";

    m_logFile = new QFile(m_currentLogFile);
    if (!m_logFile->open(QIODevice::WriteOnly | QIODevice::Append | QIODevice::Text)) {
        qWarning() << "Logger: failed to open log file:" << m_currentLogFile
                    << "- error:" << m_logFile->errorString();
        delete m_logFile;
        m_logFile = nullptr;
        return;
    }

    m_logStream = new QTextStream(m_logFile);
    m_logStream->setEncoding(QStringConverter::Utf8);

    // Rotate if there are too many log files
    rotateLogFile();
}

// ---------------------------------------------------------------------------
// rotateLogFile
// ---------------------------------------------------------------------------

void Logger::rotateLogFile()
{
    QDir dir(m_logDir);
    if (!dir.exists()) {
        return;
    }

    QStringList filters;
    filters << "aging_monitor_*.log";
    QStringList logFiles = dir.entryList(filters, QDir::Files, QDir::Name);

    // Remove old files beyond MAX_LOG_FILES
    while (logFiles.size() > MAX_LOG_FILES) {
        QString oldest = logFiles.takeFirst();
        dir.remove(oldest);
    }

    // Check if current file exceeds max size and needs rotation
    if (m_logFile && m_logFile->isOpen()) {
        if (m_logFile->size() >= m_maxFileSize) {
            // Close current file
            m_logStream->flush();
            m_logFile->close();
            delete m_logStream;
            m_logStream = nullptr;
            delete m_logFile;
            m_logFile = nullptr;

            // Will create a new file on next writeLog call
        }
    }
}

// ---------------------------------------------------------------------------
// writeLog
// ---------------------------------------------------------------------------

void Logger::writeLog(LogLevel level, const QString& msg)
{
    // Filter by log level
    if (level < m_logLevel) {
        return;
    }

    ensureLogFile();
    if (!m_logFile || !m_logStream) {
        return;
    }

    // Check rotation before writing
    if (m_logFile->size() >= m_maxFileSize) {
        rotateLogFile();
        ensureLogFile();
    }

    if (!m_logFile || !m_logStream) {
        return;
    }

    // Format level string
    QString levelStr;
    switch (level) {
    case Debug:    levelStr = "DEBUG"; break;
    case Info:     levelStr = "INFO"; break;
    case Warning:  levelStr = "WARN"; break;
    case Error:    levelStr = "ERROR"; break;
    }

    // Format: [YYYY-MM-DD HH:mm:ss.zzz] [LEVEL] [thread-id] message
    QString timestamp = QDateTime::currentDateTime().toString("yyyy-MM-dd HH:mm:ss.zzz");
    quintptr threadId = reinterpret_cast<quintptr>(QThread::currentThreadId());

    *m_logStream << QString("[%1] [%2] [%3] %4\n")
                       .arg(timestamp)
                       .arg(levelStr)
                       .arg(threadId)
                       .arg(msg);

    m_logStream->flush();
}
