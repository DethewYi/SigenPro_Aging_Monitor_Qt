#include "DataQueryPage.h"
#include "storage/DatabaseManager.h"

#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QLabel>
#include <QGroupBox>
#include <QComboBox>
#include <QDate>
#include <QTime>
#include <QDateEdit>
#include <QTableWidget>
#include <QHeaderView>
#include <QPushButton>
#include <QSqlDatabase>
#include <QSqlQuery>
#include <QDebug>

// Column indices for results table
enum ResultColumn {
    ResDeviceId = 0,
    ResSN = 1,
    ResPN = 2,
    ResTemplate = 3,
    ResStartTime = 4,
    ResEndTime = 5,
    ResDuration = 6,
    ResResult = 7,
    ResCount = 8
};

DataQueryPage::DataQueryPage(QWidget* parent)
    : QWidget(parent)
{
    setupUI();
    loadTestRecords();
}

void DataQueryPage::setupUI()
{
    QVBoxLayout* mainLayout = new QVBoxLayout(this);
    mainLayout->setContentsMargins(16, 16, 16, 16);
    mainLayout->setSpacing(12);

    // --- Query conditions panel ---
    QGroupBox* conditionBox = new QGroupBox(tr("Query Conditions"), this);
    QHBoxLayout* condLayout = new QHBoxLayout(conditionBox);
    condLayout->setSpacing(16);

    // Device combo
    QLabel* deviceLabel = new QLabel(tr("Device:"), conditionBox);
    m_deviceCombo = new QComboBox(conditionBox);
    m_deviceCombo->setFixedWidth(180);
    m_deviceCombo->addItem(tr("All Devices"), -1);
    condLayout->addWidget(deviceLabel);
    condLayout->addWidget(m_deviceCombo);

    // Start date
    QLabel* startLabel = new QLabel(tr("Start:"), conditionBox);
    m_startDate = new QDateEdit(conditionBox);
    m_startDate->setCalendarPopup(true);
    m_startDate->setDisplayFormat(QLatin1String("yyyy-MM-dd"));
    m_startDate->setDate(QDate::currentDate().addDays(-7));
    m_startDate->setFixedWidth(140);
    condLayout->addWidget(startLabel);
    condLayout->addWidget(m_startDate);

    // End date
    QLabel* endLabel = new QLabel(tr("End:"), conditionBox);
    m_endDate = new QDateEdit(conditionBox);
    m_endDate->setCalendarPopup(true);
    m_endDate->setDisplayFormat(QLatin1String("yyyy-MM-dd"));
    m_endDate->setDate(QDate::currentDate());
    m_endDate->setFixedWidth(140);
    condLayout->addWidget(endLabel);
    condLayout->addWidget(m_endDate);

    // Result filter
    QLabel* resultLabel = new QLabel(tr("Result:"), conditionBox);
    m_resultFilter = new QComboBox(conditionBox);
    m_resultFilter->setFixedWidth(130);
    m_resultFilter->addItem(tr("All"), -1);
    m_resultFilter->addItem(tr("Passed"), 1);
    m_resultFilter->addItem(tr("Failed"), 0);
    m_resultFilter->addItem(tr("Interrupted"), 2);
    condLayout->addWidget(resultLabel);
    condLayout->addWidget(m_resultFilter);

    condLayout->addStretch();

    // Query button
    m_queryBtn = new QPushButton(tr("Query"), conditionBox);
    m_queryBtn->setFixedWidth(100);
    condLayout->addWidget(m_queryBtn);

    mainLayout->addWidget(conditionBox);

    // --- Results panel ---
    QGroupBox* resultsBox = new QGroupBox(tr("Results"), this);
    QVBoxLayout* resultsLayout = new QVBoxLayout(resultsBox);
    resultsLayout->setSpacing(8);

    // Results table
    m_resultsTable = new QTableWidget(resultsBox);
    m_resultsTable->setColumnCount(ResCount);
    m_resultsTable->setHorizontalHeaderLabels({
        tr("ID"), tr("SN"), tr("PN"), tr("Template"),
        tr("Start Time"), tr("End Time"), tr("Duration"), tr("Result")
    });
    m_resultsTable->horizontalHeader()->setSectionResizeMode(QHeaderView::Interactive);
    m_resultsTable->horizontalHeader()->setStretchLastSection(true);
    m_resultsTable->setSelectionBehavior(QAbstractItemView::SelectRows);
    m_resultsTable->setEditTriggers(QAbstractItemView::NoEditTriggers);
    m_resultsTable->setAlternatingRowColors(true);
    m_resultsTable->verticalHeader()->setVisible(false);

    // Hide the ID column (used internally for navigation)
    m_resultsTable->setColumnHidden(ResDeviceId, true);

    resultsLayout->addWidget(m_resultsTable);

    // Export buttons
    QHBoxLayout* exportLayout = new QHBoxLayout();
    exportLayout->addStretch();

    m_exportPdfBtn = new QPushButton(tr("Export PDF"), resultsBox);
    exportLayout->addWidget(m_exportPdfBtn);

    m_exportExcelBtn = new QPushButton(tr("Export Excel"), resultsBox);
    exportLayout->addWidget(m_exportExcelBtn);

    resultsLayout->addLayout(exportLayout);

    mainLayout->addWidget(resultsBox);

    // --- Connections ---
    connect(m_queryBtn, &QPushButton::clicked, this, &DataQueryPage::onQuery);
    connect(m_exportPdfBtn, &QPushButton::clicked, this, &DataQueryPage::onExportPdf);
    connect(m_exportExcelBtn, &QPushButton::clicked, this, &DataQueryPage::onExportExcel);
    connect(m_resultsTable, &QTableWidget::cellDoubleClicked,
            this, &DataQueryPage::onTableDoubleClicked);
}

void DataQueryPage::loadTestRecords()
{
    // Populate device combo from database
    LocalDatabase* db = DatabaseManager::instance().localDb();
    if (!db) {
        return;
    }

    // Use QSqlQuery directly to fetch devices
    // We read from the channels table for bound SN/PN as device identifiers
    auto channels = db->loadAllChannels();
    for (const auto& ch : channels) {
        QString displayName = ch.boundSN.isEmpty()
            ? tr("Channel %1").arg(ch.channelId)
            : ch.boundSN;
        m_deviceCombo->addItem(displayName, ch.channelId);
    }

    // Load initial test records
    onQuery();
}

void DataQueryPage::onQuery()
{
    m_resultsTable->setRowCount(0);

    QDateTime startTime = QDateTime(m_startDate->date(), QTime(0, 0, 0));
    QDateTime endTime = QDateTime(m_endDate->date(), QTime(23, 59, 59));

    // Build query with optional filters
    QString sql = QLatin1String(
        "SELECT device_id, sn, pn, template_name, start_time, end_time, result "
        "FROM test_records "
        "WHERE start_time >= ? AND start_time <= ?");

    int resultFilter = m_resultFilter->currentData().toInt();
    if (resultFilter >= 0) {
        sql += QLatin1String(" AND result = ?");
    }

    sql += QLatin1String(" ORDER BY start_time DESC");

    // Query via the named database connection used by LocalDatabase
    {
        QSqlQuery directQ(QSqlDatabase::database(QLatin1String("aging_monitor_local_db")));
        directQ.prepare(sql);
        directQ.addBindValue(startTime.toString(Qt::ISODate));
        directQ.addBindValue(endTime.toString(Qt::ISODate));
        if (resultFilter >= 0) {
            directQ.addBindValue(resultFilter);
        }

        if (!directQ.exec()) {
            qWarning() << "DataQueryPage: query error:" << directQ.lastError().text();
            return;
        }

        int row = 0;
        while (directQ.next()) {
            int deviceId = directQ.value(0).toInt();
            QString sn = directQ.value(1).toString();
            QString pn = directQ.value(2).toString();
            QString templateName = directQ.value(3).toString();
            QString startStr = directQ.value(4).toString();
            QString endStr = directQ.value(5).toString();
            int result = directQ.value(6).toInt();

            m_resultsTable->insertRow(row);

            // Device ID (hidden, for navigation)
            auto* idItem = new QTableWidgetItem;
            idItem->setData(Qt::DisplayRole, deviceId);
            m_resultsTable->setItem(row, ResDeviceId, idItem);

            // SN
            m_resultsTable->setItem(row, ResSN, new QTableWidgetItem(sn));

            // PN
            m_resultsTable->setItem(row, ResPN, new QTableWidgetItem(pn));

            // Template
            m_resultsTable->setItem(row, ResTemplate, new QTableWidgetItem(templateName));

            // Start Time
            m_resultsTable->setItem(row, ResStartTime, new QTableWidgetItem(startStr));

            // End Time
            m_resultsTable->setItem(row, ResEndTime, new QTableWidgetItem(endStr));

            // Duration
            QDateTime startDt = QDateTime::fromString(startStr, Qt::ISODate);
            QDateTime endDt = QDateTime::fromString(endStr, Qt::ISODate);
            qint64 secs = startDt.isValid() && endDt.isValid()
                ? startDt.secsTo(endDt) : 0;
            int hours = static_cast<int>(secs / 3600);
            int mins = static_cast<int>((secs % 3600) / 60);
            QString durationStr = QString("%1h %2m").arg(hours).arg(mins);
            m_resultsTable->setItem(row, ResDuration, new QTableWidgetItem(durationStr));

            // Result
            QString resultText;
            QColor resultColor;
            switch (result) {
            case 1:
                resultText = tr("Passed");
                resultColor = QColor(166, 227, 161); // green
                break;
            case 0:
                resultText = tr("Failed");
                resultColor = QColor(243, 139, 168); // red
                break;
            case 2:
                resultText = tr("Interrupted");
                resultColor = QColor(249, 226, 175); // yellow
                break;
            default:
                resultText = tr("Unknown");
                break;
            }
            auto* resultItem = new QTableWidgetItem(resultText);
            resultItem->setForeground(QBrush(resultColor));
            m_resultsTable->setItem(row, ResResult, resultItem);

            ++row;
        }
    }

    // Resize columns to content
    m_resultsTable->resizeColumnsToContents();
}

void DataQueryPage::onExportPdf()
{
    // Stub: will be connected to PDF report generator in Task 24
    qInfo() << "DataQueryPage: Export PDF requested (stub)";
}

void DataQueryPage::onExportExcel()
{
    // Stub: will be connected to Excel report generator in Task 25
    qInfo() << "DataQueryPage: Export Excel requested (stub)";
}

void DataQueryPage::onTableDoubleClicked(int row, int column)
{
    Q_UNUSED(column);

    if (row < 0 || row >= m_resultsTable->rowCount()) {
        return;
    }

    auto* idItem = m_resultsTable->item(row, ResDeviceId);
    if (!idItem) {
        return;
    }

    int deviceId = idItem->data(Qt::DisplayRole).toInt();
    if (deviceId > 0) {
        emit navigateToDeviceDetail(deviceId);
    }
}
