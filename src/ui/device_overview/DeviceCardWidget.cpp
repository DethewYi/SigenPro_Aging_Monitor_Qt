#include "DeviceCardWidget.h"

#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QLabel>
#include <QMouseEvent>
#include <QFrame>

DeviceCardWidget::DeviceCardWidget(int deviceId, QWidget* parent)
    : QWidget(parent)
    , m_deviceId(deviceId)
{
    setupUI();
    updateStyleSheet();
}

void DeviceCardWidget::setupUI()
{
    setObjectName(QStringLiteral("deviceCard"));
    setMinimumSize(260, 140);
    setCursor(Qt::PointingHandCursor);

    QVBoxLayout* mainLayout = new QVBoxLayout(this);
    mainLayout->setContentsMargins(14, 12, 14, 12);
    mainLayout->setSpacing(6);

    // Top row: device name + status badge
    QHBoxLayout* topRow = new QHBoxLayout();
    topRow->setSpacing(8);

    m_nameLabel = new QLabel(tr("Device #%1").arg(m_deviceId), this);
    QFont nameFont;
    nameFont.setPointSize(13);
    nameFont.setBold(true);
    m_nameLabel->setFont(nameFont);
    m_nameLabel->setStyleSheet(QStringLiteral("color: #cdd6f4; border: none;"));
    topRow->addWidget(m_nameLabel);

    topRow->addStretch();

    m_statusLabel = new QLabel(this);
    m_statusLabel->setObjectName(QStringLiteral("statusBadge"));
    m_statusLabel->setFixedHeight(22);
    m_statusLabel->setMinimumWidth(60);
    m_statusLabel->setAlignment(Qt::AlignCenter);
    QFont badgeFont;
    badgeFont.setPointSize(9);
    m_statusLabel->setFont(badgeFont);
    topRow->addWidget(m_statusLabel);

    mainLayout->addLayout(topRow);

    // Second row: model and SN
    m_modelLabel = new QLabel(tr("Model: --"), this);
    m_modelLabel->setStyleSheet(QStringLiteral("color: #a6adc8; font-size: 11px; border: none;"));
    mainLayout->addWidget(m_modelLabel);

    m_snLabel = new QLabel(tr("SN: --"), this);
    m_snLabel->setStyleSheet(QStringLiteral("color: #a6adc8; font-size: 11px; border: none;"));
    mainLayout->addWidget(m_snLabel);

    // Separator
    QFrame* separator = new QFrame(this);
    separator->setFrameShape(QFrame::HLine);
    separator->setStyleSheet(
        QStringLiteral("color: #45475a; border: none; background: #45475a; max-height: 1px;"));
    mainLayout->addWidget(separator);

    // Parameter area (Voltage, Current, Temperature)
    QHBoxLayout* paramLayout = new QHBoxLayout();
    paramLayout->setSpacing(12);

    const QStringList paramKeys = {QStringLiteral("V"), QStringLiteral("A"), QStringLiteral("T")};
    for (const auto& paramName : paramKeys) {
        QLabel* paramLabel = new QLabel(QStringLiteral("-- --"), this);
        paramLabel->setStyleSheet(
            QStringLiteral("color: #bac2de; font-size: 11px; border: none;"));
        paramLabel->setAlignment(Qt::AlignCenter);
        paramLayout->addWidget(paramLabel);
        m_paramLabels[paramName] = paramLabel;
    }

    mainLayout->addLayout(paramLayout);
    mainLayout->addStretch();

    // Set initial status
    setStatus(m_status);
}

void DeviceCardWidget::setDeviceInfo(const QString& name, const QString& model,
                                     const QString& sn)
{
    m_name = name;
    m_model = model;
    m_sn = sn;

    // Set properties used for filtering by DeviceOverviewPage
    setProperty("modelFilter", model);
    setProperty("searchText", name + QStringLiteral(" ") + sn);

    if (m_nameLabel) {
        m_nameLabel->setText(name.isEmpty()
            ? tr("Device #%1").arg(m_deviceId)
            : name);
    }
    if (m_modelLabel) {
        m_modelLabel->setText(model.isEmpty()
            ? tr("Model: --")
            : tr("Model: %1").arg(model));
    }
    if (m_snLabel) {
        m_snLabel->setText(sn.isEmpty()
            ? tr("SN: --")
            : tr("SN: %1").arg(sn));
    }
}

void DeviceCardWidget::setStatus(DeviceStatus status)
{
    m_status = status;

    // Update property for QSS-based dynamic styling
    QString statusStr;
    switch (status) {
    case DeviceStatus::Testing:   statusStr = QStringLiteral("testing");   break;
    case DeviceStatus::Idle:      statusStr = QStringLiteral("idle");      break;
    case DeviceStatus::Alarm:     statusStr = QStringLiteral("alarm");     break;
    case DeviceStatus::Offline:   statusStr = QStringLiteral("offline");   break;
    case DeviceStatus::Completed: statusStr = QStringLiteral("completed"); break;
    case DeviceStatus::Fault:     statusStr = QStringLiteral("fault");     break;
    }
    setProperty("status", statusStr);

    // Update status badge
    if (m_statusLabel) {
        QString color = statusColor(status);
        QString text = statusText(status);
        m_statusLabel->setText(text);
        m_statusLabel->setStyleSheet(QString(
            "QLabel#statusBadge {"
            "  background-color: %1;"
            "  color: #1e1e2e;"
            "  border-radius: 11px;"
            "  padding: 2px 10px;"
            "  font-weight: bold;"
            "}"
        ).arg(color));
    }

    updateStyleSheet();
}

void DeviceCardWidget::updateParameter(const QString& name, double value,
                                       const QString& unit)
{
    auto it = m_paramLabels.find(name);
    if (it != m_paramLabels.end() && *it) {
        (*it)->setText(QString("%1 %2").arg(value, 0, 'f', 2).arg(unit));
    }
}

void DeviceCardWidget::clearParameters()
{
    for (auto it = m_paramLabels.begin(); it != m_paramLabels.end(); ++it) {
        if (*it) {
            (*it)->setText(QStringLiteral("-- --"));
        }
    }
}

void DeviceCardWidget::updateParameters(const QMap<QString, double>& parameters)
{
    for (auto it = parameters.constBegin(); it != parameters.constEnd(); ++it) {
        // Try to find a matching param label key
        // Map common parameter names to the card's display keys
        QString key = it.key();
        QString displayKey;
        if (key.contains("voltage", Qt::CaseInsensitive) ||
            key.compare("V", Qt::CaseInsensitive) == 0 ||
            key.compare("U", Qt::CaseInsensitive) == 0) {
            displayKey = QStringLiteral("V");
        } else if (key.contains("current", Qt::CaseInsensitive) ||
                   key.compare("A", Qt::CaseInsensitive) == 0 ||
                   key.compare("I", Qt::CaseInsensitive) == 0) {
            displayKey = QStringLiteral("A");
        } else if (key.contains("temp", Qt::CaseInsensitive) ||
                   key.compare("T", Qt::CaseInsensitive) == 0) {
            displayKey = QStringLiteral("T");
        } else {
            displayKey = key;
        }
        updateParameter(displayKey, it.value(), {});
    }
}

void DeviceCardWidget::mousePressEvent(QMouseEvent* event)
{
    if (event->button() == Qt::LeftButton) {
        emit clicked(m_deviceId);
    }
    QWidget::mousePressEvent(event);
}

void DeviceCardWidget::updateStyleSheet()
{
    QString borderColor = statusColor(m_status);
    setStyleSheet(QString(
        "QWidget#deviceCard {"
        "  background-color: #1e1e2e;"
        "  border: 1px solid #313244;"
        "  border-top: 3px solid %1;"
        "  border-radius: 8px;"
        "}"
        "QWidget#deviceCard:hover {"
        "  background-color: #262637;"
        "  border: 1px solid %1;"
        "  border-top: 3px solid %1;"
        "}"
    ).arg(borderColor));
}

QString DeviceCardWidget::statusColor(DeviceStatus status)
{
    switch (status) {
    case DeviceStatus::Testing:   return QStringLiteral("#a6e3a1");
    case DeviceStatus::Idle:      return QStringLiteral("#f9e2af");
    case DeviceStatus::Alarm:     return QStringLiteral("#f38ba8");
    case DeviceStatus::Offline:   return QStringLiteral("#6c7086");
    case DeviceStatus::Completed: return QStringLiteral("#89b4fa");
    case DeviceStatus::Fault:     return QStringLiteral("#fab387");
    }
    return QStringLiteral("#6c7086");
}

QString DeviceCardWidget::statusText(DeviceStatus status)
{
    switch (status) {
    case DeviceStatus::Testing:   return tr("Testing");
    case DeviceStatus::Idle:      return tr("Idle");
    case DeviceStatus::Alarm:     return tr("Alarm");
    case DeviceStatus::Offline:   return tr("Offline");
    case DeviceStatus::Completed: return tr("Completed");
    case DeviceStatus::Fault:     return tr("Fault");
    }
    return tr("Unknown");
}
