#include "StatsBarWidget.h"

#include <QHBoxLayout>
#include <QLabel>

StatsBarWidget::StatsBarWidget(QWidget* parent)
    : QWidget(parent)
{
    QHBoxLayout* layout = new QHBoxLayout(this);
    layout->setContentsMargins(0, 0, 0, 0);
    layout->setSpacing(16);

    m_onlineCount = createStatCard(
        tr("Online"), QStringLiteral("0"), QStringLiteral("#89b4fa"));
    layout->addWidget(m_onlineCount);

    m_offlineCount = createStatCard(
        tr("Offline"), QStringLiteral("0"), QStringLiteral("#6c7086"));
    layout->addWidget(m_offlineCount);

    m_alarmCount = createStatCard(
        tr("Alarm"), QStringLiteral("0"), QStringLiteral("#f38ba8"));
    layout->addWidget(m_alarmCount);

    m_testingCount = createStatCard(
        tr("Testing"), QStringLiteral("0"), QStringLiteral("#a6e3a1"));
    layout->addWidget(m_testingCount);
}

QLabel* StatsBarWidget::createStatCard(const QString& title, const QString& valueText,
                                        const QString& accentColor)
{
    QLabel* card = new QLabel(this);
    card->setObjectName(QStringLiteral("statCard"));
    card->setMinimumHeight(80);
    card->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Fixed);

    card->setStyleSheet(QString(
        "QLabel#statCard {"
        "  background-color: #1e1e2e;"
        "  border-radius: 8px;"
        "  border-left: 4px solid %1;"
        "  padding: 12px 16px;"
        "}"
    ).arg(accentColor));

    card->setTextFormat(Qt::RichText);
    card->setText(QString(
        "<div style='color: #cdd6f4; font-size: 12px;'>%1</div>"
        "<div style='color: %2; font-size: 28px; font-weight: bold; margin-top: 4px;'>%3</div>"
    ).arg(title, accentColor, valueText));

    return card;
}

void StatsBarWidget::updateOnlineCount(int count)
{
    if (m_onlineCount) {
        QString accentColor = QStringLiteral("#89b4fa");
        m_onlineCount->setText(QString(
            "<div style='color: #cdd6f4; font-size: 12px;'>%1</div>"
            "<div style='color: %2; font-size: 28px; font-weight: bold; margin-top: 4px;'>%3</div>"
        ).arg(tr("Online"), accentColor, QString::number(count)));
    }
}

void StatsBarWidget::updateOfflineCount(int count)
{
    if (m_offlineCount) {
        QString accentColor = QStringLiteral("#6c7086");
        m_offlineCount->setText(QString(
            "<div style='color: #cdd6f4; font-size: 12px;'>%1</div>"
            "<div style='color: %2; font-size: 28px; font-weight: bold; margin-top: 4px;'>%3</div>"
        ).arg(tr("Offline"), accentColor, QString::number(count)));
    }
}

void StatsBarWidget::updateAlarmCount(int count)
{
    if (m_alarmCount) {
        QString accentColor = QStringLiteral("#f38ba8");
        m_alarmCount->setText(QString(
            "<div style='color: #cdd6f4; font-size: 12px;'>%1</div>"
            "<div style='color: %2; font-size: 28px; font-weight: bold; margin-top: 4px;'>%3</div>"
        ).arg(tr("Alarm"), accentColor, QString::number(count)));
    }
}

void StatsBarWidget::updateTestingCount(int count)
{
    if (m_testingCount) {
        QString accentColor = QStringLiteral("#a6e3a1");
        m_testingCount->setText(QString(
            "<div style='color: #cdd6f4; font-size: 12px;'>%1</div>"
            "<div style='color: %2; font-size: 28px; font-weight: bold; margin-top: 4px;'>%3</div>"
        ).arg(tr("Testing"), accentColor, QString::number(count)));
    }
}
