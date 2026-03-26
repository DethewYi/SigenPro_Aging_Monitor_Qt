#include "RealtimeDataPanel.h"
#include <QTableWidget>
#include <QHeaderView>
#include <QVBoxLayout>
#include <QLabel>

RealtimeDataPanel::RealtimeDataPanel(QWidget* parent)
    : QWidget(parent)
{
    QVBoxLayout* layout = new QVBoxLayout(this);
    layout->setContentsMargins(8, 8, 8, 8);

    QLabel* titleLabel = new QLabel(tr("Real-time Data"), this);
    QFont titleFont;
    titleFont.setPointSize(14);
    titleFont.setBold(true);
    titleLabel->setFont(titleFont);
    layout->addWidget(titleLabel);

    m_table = new QTableWidget(this);
    m_table->setColumnCount(3);
    m_table->setHorizontalHeaderLabels({
        tr("Parameter"),
        tr("Value"),
        tr("Status")
    });

    // Hide vertical header (row numbers) for cleaner look
    m_table->verticalHeader()->setVisible(false);

    // Make table read-only
    m_table->setEditTriggers(QAbstractItemView::NoEditTriggers);
    m_table->setSelectionBehavior(QAbstractItemView::SelectRows);
    m_table->setAlternatingRowColors(true);

    // Stretch columns
    m_table->horizontalHeader()->setSectionResizeMode(0, QHeaderView::Stretch);
    m_table->horizontalHeader()->setSectionResizeMode(1, QHeaderView::ResizeToContents);
    m_table->horizontalHeader()->setSectionResizeMode(2, QHeaderView::ResizeToContents);

    layout->addWidget(m_table);
}

void RealtimeDataPanel::setupParameters(const QStringList& paramNames)
{
    m_table->setRowCount(paramNames.size());
    m_paramRows.clear();

    for (int i = 0; i < paramNames.size(); ++i) {
        const QString& name = paramNames[i];
        m_paramRows[name] = i;

        // Parameter name column
        QTableWidgetItem* nameItem = new QTableWidgetItem(name);
        nameItem->setFlags(nameItem->flags() & ~Qt::ItemIsEditable);
        m_table->setItem(i, 0, nameItem);

        // Value column
        QTableWidgetItem* valueItem = new QTableWidgetItem(QString("--"));
        valueItem->setFlags(valueItem->flags() & ~Qt::ItemIsEditable);
        valueItem->setTextAlignment(Qt::AlignCenter);
        m_table->setItem(i, 1, valueItem);

        // Status column (green dot initially)
        QTableWidgetItem* statusItem = new QTableWidgetItem(QString::fromUtf8("\u25CF")); // filled circle
        statusItem->setFlags(statusItem->flags() & ~Qt::ItemIsEditable);
        statusItem->setTextAlignment(Qt::AlignCenter);
        statusItem->setForeground(QBrush(QColor("#a6e3a1"))); // green
        m_table->setItem(i, 2, statusItem);
    }
}

void RealtimeDataPanel::updateParameter(const QString& name, double value)
{
    if (!m_paramRows.contains(name)) {
        return;
    }

    int row = m_paramRows[name];
    QTableWidgetItem* valueItem = m_table->item(row, 1);
    if (valueItem) {
        valueItem->setText(QString::number(value, 'f', 3));
    }
}

void RealtimeDataPanel::clearAll()
{
    m_table->setRowCount(0);
    m_paramRows.clear();
}

int RealtimeDataPanel::parameterCount() const
{
    return m_table->rowCount();
}
