#include "AlarmPanelPage.h"
#include "storage/DatabaseManager.h"

#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QTableWidget>
#include <QHeaderView>
#include <QComboBox>
#include <QLabel>
#include <QPushButton>
#include <QTableWidgetItem>
#include <QTimer>
#include <QBrush>
#include <QColor>
#include <QSet>
#include <algorithm>

// Column indices
enum AlarmColumn {
    ColId = 0,
    ColTime = 1,
    ColDevice = 2,
    ColParam = 3,
    ColValue = 4,
    ColThreshold = 5,
    ColDirection = 6,
    ColStatus = 7,
    ColCount = 8
};

AlarmPanelPage::AlarmPanelPage(QWidget* parent)
    : QWidget(parent)
{
    setupUI();
}

void AlarmPanelPage::setupUI()
{
    QVBoxLayout* mainLayout = new QVBoxLayout(this);
    mainLayout->setContentsMargins(16, 16, 16, 16);
    mainLayout->setSpacing(12);

    // --- Top toolbar: filter + stats + buttons ---
    QHBoxLayout* toolbarLayout = new QHBoxLayout();
    toolbarLayout->setSpacing(12);

    QLabel* filterLabel = new QLabel(tr("Filter:"), this);
    toolbarLayout->addWidget(filterLabel);

    m_filterCombo = new QComboBox(this);
    m_filterCombo->addItem(tr("All"), static_cast<int>(All));
    m_filterCombo->addItem(tr("Unacknowledged"), static_cast<int>(Unacknowledged));
    m_filterCombo->addItem(tr("Acknowledged"), static_cast<int>(Acknowledged));
    m_filterCombo->setFixedWidth(150);
    toolbarLayout->addWidget(m_filterCombo);

    toolbarLayout->addStretch();

    m_totalLabel = new QLabel(tr("Total: 0"), this);
    m_totalLabel->setStyleSheet(QLatin1String("font-weight: bold;"));
    toolbarLayout->addWidget(m_totalLabel);

    m_unackLabel = new QLabel(tr("Unacknowledged: 0"), this);
    m_unackLabel->setStyleSheet(QLatin1String("color: #f38ba8; font-weight: bold;"));
    toolbarLayout->addWidget(m_unackLabel);

    toolbarLayout->addStretch();

    QPushButton* ackSelectedBtn = new QPushButton(tr("Acknowledge Selected"), this);
    toolbarLayout->addWidget(ackSelectedBtn);

    QPushButton* ackAllBtn = new QPushButton(tr("Acknowledge All"), this);
    toolbarLayout->addWidget(ackAllBtn);

    mainLayout->addLayout(toolbarLayout);

    // --- Alarm table ---
    m_table = new QTableWidget(this);
    m_table->setColumnCount(ColCount);
    m_table->setHorizontalHeaderLabels({
        tr("ID"), tr("Time"), tr("Device"), tr("Parameter"),
        tr("Value"), tr("Threshold"), tr("Direction"), tr("Status")
    });
    m_table->horizontalHeader()->setStretchLastSection(true);
    m_table->horizontalHeader()->setSectionResizeMode(QHeaderView::Interactive);
    m_table->setSelectionBehavior(QAbstractItemView::SelectRows);
    m_table->setEditTriggers(QAbstractItemView::NoEditTriggers);
    m_table->setAlternatingRowColors(true);
    m_table->setSortingEnabled(false);
    m_table->verticalHeader()->setVisible(false);

    // Hide the ID column (used internally)
    m_table->setColumnHidden(ColId, true);

    mainLayout->addWidget(m_table);

    // --- Connections ---
    connect(m_filterCombo, QOverload<int>::of(&QComboBox::currentIndexChanged),
            this, &AlarmPanelPage::onFilterChanged);
    connect(ackSelectedBtn, &QPushButton::clicked,
            this, &AlarmPanelPage::onAcknowledgeSelected);
    connect(ackAllBtn, &QPushButton::clicked,
            this, &AlarmPanelPage::onAcknowledgeAll);
    connect(m_table, &QTableWidget::cellDoubleClicked,
            this, &AlarmPanelPage::onTableDoubleClicked);
}

void AlarmPanelPage::addAlarm(int id, const QString& timestamp, int deviceId,
                               const QString& deviceName, const QString& paramName,
                               double currentValue, double threshold,
                               bool isUpperLimit, bool acknowledged)
{
    // Insert at row 0 (newest first)
    m_table->insertRow(0);

    // ID (hidden, stored for acknowledge operations)
    auto* idItem = new QTableWidgetItem;
    idItem->setData(Qt::DisplayRole, id);
    m_table->setItem(0, ColId, idItem);

    // Time
    m_table->setItem(0, ColTime, new QTableWidgetItem(timestamp));

    // Device name
    auto* devItem = new QTableWidgetItem(deviceName);
    devItem->setData(Qt::UserRole, deviceId);
    m_table->setItem(0, ColDevice, devItem);

    // Parameter
    m_table->setItem(0, ColParam, new QTableWidgetItem(paramName));

    // Value
    m_table->setItem(0, ColValue, new QTableWidgetItem(QString::number(currentValue, 'f', 3)));

    // Threshold
    m_table->setItem(0, ColThreshold, new QTableWidgetItem(QString::number(threshold, 'f', 3)));

    // Direction
    QString direction = isUpperLimit ? QStringLiteral("\u2191") : QStringLiteral("\u2193");
    m_table->setItem(0, ColDirection, new QTableWidgetItem(direction));

    // Status
    QString statusText = acknowledged ? tr("ACK") : tr("UNACK");
    auto* statusItem = new QTableWidgetItem(statusText);
    statusItem->setData(Qt::UserRole, acknowledged);
    m_table->setItem(0, ColStatus, statusItem);

    // Highlight unacknowledged rows with red tint
    if (!acknowledged) {
        QColor bgColor(243, 139, 168, 48); // #f38ba830
        for (int col = 0; col < ColCount; ++col) {
            if (auto* item = m_table->item(0, col)) {
                item->setBackground(QBrush(bgColor));
            }
        }
        // Red text for status column
        statusItem->setForeground(QBrush(QColor(243, 139, 168)));
    }

    // Brief flash animation: set a white flash then restore
    if (!acknowledged) {
        QColor flashColor(255, 255, 255, 120);
        for (int col = 0; col < ColCount; ++col) {
            if (auto* item = m_table->item(0, col)) {
                QBrush origBg = item->background();
                item->setBackground(QBrush(flashColor));
                QTimer::singleShot(300, item, [item, origBg]() {
                    item->setBackground(origBg);
                });
            }
        }
    }

    updateFilterView();
}

void AlarmPanelPage::acknowledgeAlarm(int row)
{
    if (row < 0 || row >= m_table->rowCount()) {
        return;
    }

    int alarmId = m_table->item(row, ColId)->data(Qt::DisplayRole).toInt();
    bool ok = DatabaseManager::instance().localDb()->acknowledgeAlarm(alarmId);
    if (!ok) {
        return;
    }

    // Update status text and clear highlight
    auto* statusItem = m_table->item(row, ColStatus);
    if (statusItem) {
        statusItem->setText(tr("ACK"));
        statusItem->setData(Qt::UserRole, true);
        statusItem->setForeground(QBrush()); // Reset to default
    }

    // Remove red background from all cells in the row
    for (int col = 0; col < ColCount; ++col) {
        if (auto* item = m_table->item(row, col)) {
            item->setBackground(QBrush());
        }
    }

    updateFilterView();
}

void AlarmPanelPage::onAcknowledgeSelected()
{
    QList<QTableWidgetItem*> selected = m_table->selectedItems();
    QSet<int> rowsToAck;
    for (auto* item : selected) {
        rowsToAck.insert(item->row());
    }

    // Acknowledge in reverse order so row indices remain valid
    QList<int> sortedRows = rowsToAck.values();
    std::sort(sortedRows.begin(), sortedRows.end(), std::greater<int>());
    for (int row : sortedRows) {
        acknowledgeAlarm(row);
    }
}

void AlarmPanelPage::onAcknowledgeAll()
{
    // Acknowledge all rows (iterate from bottom to top)
    for (int row = m_table->rowCount() - 1; row >= 0; --row) {
        auto* statusItem = m_table->item(row, ColStatus);
        if (statusItem && !statusItem->data(Qt::UserRole).toBool()) {
            acknowledgeAlarm(row);
        }
    }
}

void AlarmPanelPage::onFilterChanged()
{
    updateFilterView();
}

void AlarmPanelPage::updateFilterView()
{
    int filterMode = m_filterCombo->currentData().toInt();
    int totalVisible = 0;
    int unackCount = 0;

    for (int row = 0; row < m_table->rowCount(); ++row) {
        auto* statusItem = m_table->item(row, ColStatus);
        if (!statusItem) {
            continue;
        }

        bool acked = statusItem->data(Qt::UserRole).toBool();
        if (!acked) {
            ++unackCount;
        }

        bool show = false;
        switch (filterMode) {
        case All:
            show = true;
            break;
        case Unacknowledged:
            show = !acked;
            break;
        case Acknowledged:
            show = acked;
            break;
        }

        m_table->setRowHidden(row, !show);
        if (show) {
            ++totalVisible;
        }
    }

    m_totalLabel->setText(tr("Total: %1").arg(m_table->rowCount()));
    m_unackLabel->setText(tr("Unacknowledged: %1").arg(unackCount));
}

void AlarmPanelPage::onTableDoubleClicked(int row, int column)
{
    Q_UNUSED(column);

    if (row < 0 || row >= m_table->rowCount()) {
        return;
    }

    auto* devItem = m_table->item(row, ColDevice);
    if (!devItem) {
        return;
    }

    int deviceId = devItem->data(Qt::UserRole).toInt();
    if (deviceId > 0) {
        emit deviceAlarmClicked(deviceId);
    }
}
