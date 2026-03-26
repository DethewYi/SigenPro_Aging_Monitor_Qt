#include "PdfReportGenerator.h"

#include <QPrinter>
#include <QPainter>
#include <QDateTime>
#include <QSqlQuery>
#include <QSqlError>
#include <QDir>
#include <QDesktopServices>
#include <QUrl>

#include "storage/DatabaseManager.h"

// ---------------------------------------------------------------------------
// Construction
// ---------------------------------------------------------------------------

PdfReportGenerator::PdfReportGenerator(QObject* parent)
    : QObject(parent)
{
}

// ---------------------------------------------------------------------------
// generateReport
// ---------------------------------------------------------------------------

bool PdfReportGenerator::generateReport(int testRecordId, const QString& filePath)
{
    // 1. Load test record from database
    auto* db = DatabaseManager::instance().localDb();
    QSqlQuery query(db->m_db);
    query.prepare(
        "SELECT id, device_id, sn, pn, template_name, start_time, end_time, result, created_at "
        "FROM test_records WHERE id = ?");
    query.addBindValue(testRecordId);

    if (!query.exec() || !query.next()) {
        qWarning() << tr("PdfReportGenerator: test record %1 not found").arg(testRecordId);
        return false;
    }

    QVariantMap recordInfo;
    recordInfo["id"] = query.value(0).toInt();
    recordInfo["device_id"] = query.value(1).toInt();
    recordInfo["sn"] = query.value(2).toString();
    recordInfo["pn"] = query.value(3).toString();
    recordInfo["template_name"] = query.value(4).toString();
    recordInfo["start_time"] = query.value(5).toString();
    recordInfo["end_time"] = query.value(6).toString();
    recordInfo["result"] = query.value(7).toInt();
    recordInfo["created_at"] = query.value(8).toString();

    // Get device name
    int deviceId = recordInfo["device_id"].toInt();
    QSqlQuery devQuery(db->m_db);
    devQuery.prepare("SELECT name FROM devices WHERE device_id = ?");
    devQuery.addBindValue(deviceId);
    if (devQuery.exec() && devQuery.next()) {
        recordInfo["device_name"] = devQuery.value(0).toString();
    } else {
        recordInfo["device_name"] = tr("Unknown");
    }

    // 2. Load alarm records for this test
    QString startTime = recordInfo["start_time"].toString();
    QVariantList alarms;
    QSqlQuery alarmQuery(db->m_db);
    alarmQuery.prepare(
        "SELECT timestamp, device_name, param_name, current_value, threshold, is_upper_limit, message "
        "FROM alarms WHERE device_id = ? AND timestamp >= ? AND timestamp <= ? "
        "ORDER BY timestamp ASC");
    alarmQuery.addBindValue(deviceId);
    alarmQuery.addBindValue(startTime);
    alarmQuery.addBindValue(recordInfo["end_time"].toString());

    if (alarmQuery.exec()) {
        while (alarmQuery.next()) {
            QVariantMap alarm;
            alarm["timestamp"] = alarmQuery.value(0).toString();
            alarm["device_name"] = alarmQuery.value(1).toString();
            alarm["param_name"] = alarmQuery.value(2).toString();
            alarm["current_value"] = alarmQuery.value(3).toDouble();
            alarm["threshold"] = alarmQuery.value(4).toDouble();
            alarm["is_upper_limit"] = alarmQuery.value(5).toInt() != 0;
            alarm["message"] = alarmQuery.value(6).toString();
            alarms.append(alarm);
        }
    }

    // 3. Calculate statistics from device data
    QDateTime startDt = QDateTime::fromString(startTime, Qt::ISODate);
    QDateTime endDt = QDateTime::fromString(recordInfo["end_time"].toString(), Qt::ISODate);
    QVector<DeviceData> deviceDataList = db->queryDeviceData(deviceId, startDt, endDt);

    // Collect per-parameter statistics
    QMap<QString, QVector<double>> paramDataMap;
    for (const auto& dd : deviceDataList) {
        for (auto it = dd.parameters.constBegin(); it != dd.parameters.constEnd(); ++it) {
            paramDataMap[it.key()].append(it.value());
        }
    }

    QVariantList stats;
    for (auto it = paramDataMap.constBegin(); it != paramDataMap.constEnd(); ++it) {
        const auto& values = it.value();
        if (values.isEmpty()) continue;

        double minVal = values.first();
        double maxVal = values.first();
        double sum = 0.0;
        for (double v : values) {
            if (v < minVal) minVal = v;
            if (v > maxVal) maxVal = v;
            sum += v;
        }
        double avg = sum / values.size();

        QVariantMap stat;
        stat["param_name"] = it.key();
        stat["min"] = minVal;
        stat["max"] = maxVal;
        stat["avg"] = avg;
        stat["count"] = values.size();
        stats.append(stat);
    }

    // 4. Setup QPrinter for PDF output
    QPrinter printer(QPrinter::HighResolution);
    printer.setOutputFormat(QPrinter::PdfFormat);
    printer.setOutputFileName(filePath);
    printer.setPageSize(QPageSize(QPageSize::A4));
    printer.setPageMargins(QMarginsF(20, 20, 20, 20), QPageLayout::Millimeter);

    // 5. Paint the PDF
    QPainter painter;
    if (!painter.begin(&printer)) {
        qWarning() << tr("PdfReportGenerator: failed to begin painting on printer");
        return false;
    }

    int pageWidth = printer.width();   // printable area in pixels
    int pageHeight = printer.height();
    int y = TOP_MARGIN;

    // Draw header
    drawHeader(painter, pageWidth, pageHeight);
    y = TOP_MARGIN + 600;

    // Draw test info
    drawTestInfo(painter, y, recordInfo);
    y += 1400;

    // Draw statistics
    if (!stats.isEmpty()) {
        drawStatistics(painter, y, stats);
        int statRowCount = stats.size() + 1; // +1 for header row
        y += statRowCount * 300 + 400;
    }

    // Check if we need a new page
    if (y > pageHeight - BOTTOM_MARGIN - 800) {
        printer.newPage();
        y = TOP_MARGIN;
    }

    // Draw alarm table
    if (!alarms.isEmpty()) {
        drawAlarmTable(painter, y, alarms);
        int alarmRowCount = qMin(alarms.size() + 1, 16); // max visible rows per page
        y += alarmRowCount * 300 + 400;
    }

    // Check if we need a new page for conclusion
    if (y > pageHeight - BOTTOM_MARGIN - 600) {
        printer.newPage();
        y = TOP_MARGIN;
    }

    // Draw conclusion
    drawConclusion(painter, y, recordInfo["result"].toInt());

    // Draw footer on all pages
    drawFooter(painter, pageHeight, 1);

    painter.end();
    return true;
}

// ---------------------------------------------------------------------------
// generateReportPreview
// ---------------------------------------------------------------------------

bool PdfReportGenerator::generateReportPreview(int testRecordId)
{
    QString tempDir = QDir::tempPath();
    QString fileName = QString("SigenPro_Report_%1.pdf").arg(testRecordId);
    QString filePath = tempDir + "/" + fileName;

    if (!generateReport(testRecordId, filePath)) {
        return false;
    }

    return QDesktopServices::openUrl(QUrl::fromLocalFile(filePath));
}

// ---------------------------------------------------------------------------
// drawHeader
// ---------------------------------------------------------------------------

void PdfReportGenerator::drawHeader(QPainter& painter, int pageWidth, int pageHeight)
{
    // Company name / logo placeholder
    QFont companyFont("Arial", 8);
    painter.setFont(companyFont);
    painter.setPen(Qt::gray);
    painter.drawText(LEFT_MARGIN, 300, tr("SigenPro"));

    // Main title centered
    QFont titleFont("Arial", 16, QFont::Bold);
    painter.setFont(titleFont);
    painter.setPen(Qt::black);
    QString title = tr("SigenPro Aging Test Report");
    QRect titleRect(0, 200, pageWidth + LEFT_MARGIN + RIGHT_MARGIN, 400);
    painter.drawText(titleRect, Qt::AlignCenter, title);

    // Report date
    QFont dateFont("Arial", 8);
    painter.setFont(dateFont);
    painter.setPen(Qt::gray);
    QString dateStr = QDateTime::currentDateTime().toString("yyyy-MM-dd HH:mm:ss");
    painter.drawText(pageWidth - 1000, 300, dateStr);

    // Separator line
    painter.setPen(QPen(Qt::black, 20));
    painter.drawLine(LEFT_MARGIN, 450, pageWidth, 450);
}

// ---------------------------------------------------------------------------
// drawTestInfo
// ---------------------------------------------------------------------------

void PdfReportGenerator::drawTestInfo(QPainter& painter, int yOffset, const QVariantMap& recordInfo)
{
    // Section title
    QFont sectionFont("Arial", 11, QFont::Bold);
    painter.setFont(sectionFont);
    painter.setPen(Qt::black);
    painter.drawText(LEFT_MARGIN, yOffset, tr("Test Information"));

    yOffset += LINE_SPACING;

    // Info table
    QFont labelFont("Arial", 9, QFont::Bold);
    QFont valueFont("Arial", 9);

    QList<QPair<QString, QString>> infoFields = {
        { tr("Device Name"), recordInfo["device_name"].toString() },
        { tr("Device SN"), recordInfo["sn"].toString() },
        { tr("Product PN"), recordInfo["pn"].toString() },
        { tr("Template"), recordInfo["template_name"].toString() },
        { tr("Start Time"), recordInfo["start_time"].toString() },
        { tr("End Time"), recordInfo["end_time"].toString() },
    };

    // Calculate duration
    QDateTime startDt = QDateTime::fromString(recordInfo["start_time"].toString(), Qt::ISODate);
    QDateTime endDt = QDateTime::fromString(recordInfo["end_time"].toString(), Qt::ISODate);
    qint64 durationSecs = startDt.secsTo(endDt);
    int hours = static_cast<int>(durationSecs / 3600);
    int minutes = static_cast<int>((durationSecs % 3600) / 60);
    int seconds = static_cast<int>(durationSecs % 60);
    QString durationStr = QString("%1h %2m %3s").arg(hours).arg(minutes, 2, 10, QChar('0')).arg(seconds, 2, 10, QChar('0'));
    infoFields.append({ tr("Duration"), durationStr });

    // Result text
    int resultVal = recordInfo["result"].toInt();
    QString resultText;
    switch (resultVal) {
    case 0: resultText = tr("Pending"); break;
    case 1: resultText = tr("Passed"); break;
    case 2: resultText = tr("Failed"); break;
    case 3: resultText = tr("Interrupted"); break;
    default: resultText = tr("Unknown"); break;
    }
    infoFields.append({ tr("Result"), resultText });

    // Draw table border
    int tableWidth = painter.device()->width() - LEFT_MARGIN - RIGHT_MARGIN;
    int rowHeight = 280;
    int labelWidth = tableWidth / 3;
    int valueWidth = tableWidth / 3;
    int colCount = 2;
    int rowCount = (infoFields.size() + 1) / colCount;

    // Background
    painter.setPen(Qt::NoPen);
    painter.setBrush(QColor(245, 245, 245));
    painter.drawRect(LEFT_MARGIN, yOffset - 200, tableWidth, rowCount * rowHeight + 50);

    // Draw border
    painter.setPen(QPen(Qt::lightGray, 10));
    painter.setBrush(Qt::NoBrush);
    painter.drawRect(LEFT_MARGIN, yOffset - 200, tableWidth, rowCount * rowHeight + 50);

    // Draw info cells
    for (int i = 0; i < infoFields.size(); ++i) {
        int col = i % colCount;
        int row = i / colCount;
        int x = LEFT_MARGIN + col * (labelWidth + valueWidth) + 50;
        int y = yOffset + row * rowHeight;

        // Label
        painter.setFont(labelFont);
        painter.setPen(Qt::darkGray);
        painter.drawText(x, y + 100, infoFields[i].first + ":");

        // Value
        painter.setFont(valueFont);
        painter.setPen(Qt::black);
        painter.drawText(x + 500, y + 100, infoFields[i].second);
    }
}

// ---------------------------------------------------------------------------
// drawStatistics
// ---------------------------------------------------------------------------

void PdfReportGenerator::drawStatistics(QPainter& painter, int yOffset, const QVariantList& stats)
{
    // Section title
    QFont sectionFont("Arial", 11, QFont::Bold);
    painter.setFont(sectionFont);
    painter.setPen(Qt::black);
    painter.drawText(LEFT_MARGIN, yOffset, tr("Statistical Summary"));
    yOffset += LINE_SPACING;

    // Table header
    int tableWidth = painter.device()->width() - LEFT_MARGIN - RIGHT_MARGIN;
    QList<int> colWidths = { tableWidth * 3 / 10, tableWidth * 15 / 100, tableWidth * 15 / 100,
                              tableWidth * 17 / 100, tableWidth * 15 / 100 };
    QStringList headers = { tr("Parameter"), tr("Min"), tr("Max"), tr("Avg"), tr("Count") };

    // Draw header row
    drawTableRow(painter, yOffset, headers, colWidths, true);
    yOffset += 300;

    // Draw data rows
    QFont dataFont("Arial", 9);
    painter.setFont(dataFont);

    for (int i = 0; i < stats.size(); ++i) {
        const QVariantMap& stat = stats[i].toMap();
        QStringList columns;
        columns << stat["param_name"].toString()
                << QString::number(stat["min"].toDouble(), 'f', 3)
                << QString::number(stat["max"].toDouble(), 'f', 3)
                << QString::number(stat["avg"].toDouble(), 'f', 3)
                << QString::number(stat["count"].toInt());

        drawTableRow(painter, yOffset, columns, colWidths, false);
        yOffset += 300;
    }
}

// ---------------------------------------------------------------------------
// drawAlarmTable
// ---------------------------------------------------------------------------

void PdfReportGenerator::drawAlarmTable(QPainter& painter, int yOffset, const QVariantList& alarms)
{
    // Section title
    QFont sectionFont("Arial", 11, QFont::Bold);
    painter.setFont(sectionFont);
    painter.setPen(Qt::black);
    painter.drawText(LEFT_MARGIN, yOffset, tr("Alarm Records"));
    yOffset += LINE_SPACING;

    // Table header
    int tableWidth = painter.device()->width() - LEFT_MARGIN - RIGHT_MARGIN;
    QList<int> colWidths = { tableWidth * 25 / 100, tableWidth * 20 / 100,
                              tableWidth * 20 / 100, tableWidth * 20 / 100,
                              tableWidth * 15 / 100 };
    QStringList headers = { tr("Time"), tr("Parameter"), tr("Value"), tr("Threshold"), tr("Type") };

    drawTableRow(painter, yOffset, headers, colWidths, true);
    yOffset += 300;

    // Draw data rows (limit to prevent overflow)
    QFont dataFont("Arial", 8);
    painter.setFont(dataFont);

    int maxRows = alarms.size();
    int pageHeight = painter.device()->height() - BOTTOM_MARGIN;
    int availableSpace = pageHeight - yOffset;
    int maxVisibleRows = availableSpace / 300;

    for (int i = 0; i < qMin(maxRows, maxVisibleRows); ++i) {
        const QVariantMap& alarm = alarms[i].toMap();
        QString typeStr = alarm["is_upper_limit"].toBool() ? tr("Upper") : tr("Lower");

        QStringList columns;
        columns << alarm["timestamp"].toString().mid(11, 8)  // just HH:mm:ss
                << alarm["param_name"].toString()
                << QString::number(alarm["current_value"].toDouble(), 'f', 3)
                << QString::number(alarm["threshold"].toDouble(), 'f', 3)
                << typeStr;

        drawTableRow(painter, yOffset, columns, colWidths, false);
        yOffset += 300;
    }

    if (alarms.size() > maxVisibleRows) {
        yOffset += 50;
        QFont moreFont("Arial", 8);
        painter.setFont(moreFont);
        painter.setPen(Qt::gray);
        painter.drawText(LEFT_MARGIN, yOffset,
                         tr("... and %1 more alarm records").arg(alarms.size() - maxVisibleRows));
    }
}

// ---------------------------------------------------------------------------
// drawConclusion
// ---------------------------------------------------------------------------

void PdfReportGenerator::drawConclusion(QPainter& painter, int yOffset, int testResult)
{
    // Section title
    QFont sectionFont("Arial", 11, QFont::Bold);
    painter.setFont(sectionFont);
    painter.setPen(Qt::black);
    painter.drawText(LEFT_MARGIN, yOffset, tr("Test Conclusion"));
    yOffset += LINE_SPACING + 100;

    int tableWidth = painter.device()->width() - LEFT_MARGIN - RIGHT_MARGIN;

    // Draw conclusion box
    painter.setPen(QPen(Qt::black, 20));
    painter.setBrush(QColor(250, 250, 250));
    painter.drawRect(LEFT_MARGIN, yOffset - 200, tableWidth, 500);

    // Result text
    QFont resultFont("Arial", 20, QFont::Bold);
    painter.setFont(resultFont);

    QString resultText;
    QColor resultColor;
    switch (testResult) {
    case 1:  // Passed
        resultText = tr("PASSED");
        resultColor = QColor(34, 139, 34); // Forest green
        break;
    case 2:  // Failed
        resultText = tr("FAILED");
        resultColor = QColor(220, 20, 60); // Crimson
        break;
    case 3:  // Interrupted
        resultText = tr("INTERRUPTED");
        resultColor = QColor(255, 140, 0); // Dark orange
        break;
    default:
        resultText = tr("PENDING");
        resultColor = QColor(128, 128, 128); // Gray
        break;
    }

    painter.setPen(resultColor);
    QRect resultRect(LEFT_MARGIN, yOffset - 150, tableWidth, 400);
    painter.drawText(resultRect, Qt::AlignCenter, resultText);
}

// ---------------------------------------------------------------------------
// drawFooter
// ---------------------------------------------------------------------------

void PdfReportGenerator::drawFooter(QPainter& painter, int pageHeight, int pageNumber)
{
    int tableWidth = painter.device()->width() - LEFT_MARGIN - RIGHT_MARGIN;

    // Separator line
    painter.setPen(QPen(Qt::lightGray, 10));
    painter.drawLine(LEFT_MARGIN, pageHeight - BOTTOM_MARGIN + 100, tableWidth, pageHeight - BOTTOM_MARGIN + 100);

    // Page number
    QFont footerFont("Arial", 8);
    painter.setFont(footerFont);
    painter.setPen(Qt::gray);
    QString pageStr = tr("Page %1").arg(pageNumber);
    QRect pageRect(0, pageHeight - BOTTOM_MARGIN + 100, painter.device()->width(), 300);
    painter.drawText(pageRect, Qt::AlignHCenter | Qt::AlignTop, pageStr);
}

// ---------------------------------------------------------------------------
// drawTableRow (helper)
// ---------------------------------------------------------------------------

int PdfReportGenerator::drawTableRow(QPainter& painter, int yOffset, const QStringList& columns,
                                      const QList<int>& colWidths, bool isHeader)
{
    int x = LEFT_MARGIN;

    // Background
    if (isHeader) {
        painter.setPen(Qt::NoPen);
        painter.setBrush(QColor(70, 130, 180)); // Steel blue
        painter.drawRect(x, yOffset - 200, colWidths[0] + colWidths[1] + colWidths[2]
                         + colWidths[3] + colWidths[4], 280);
    } else {
        painter.setPen(Qt::NoPen);
        painter.setBrush((yOffset / 300) % 2 == 0 ? QColor(255, 255, 255) : QColor(240, 248, 255));
        int totalWidth = 0;
        for (int w : colWidths) totalWidth += w;
        painter.drawRect(x, yOffset - 200, totalWidth, 280);
    }

    // Text
    QFont font("Arial", 8);
    if (isHeader) {
        font.setBold(true);
    }
    painter.setFont(font);
    painter.setPen(isHeader ? Qt::white : Qt::black);

    for (int i = 0; i < columns.size() && i < colWidths.size(); ++i) {
        QRect cellRect(x + 30, yOffset - 190, colWidths[i] - 60, 260);
        painter.drawText(cellRect, Qt::AlignVCenter | Qt::AlignLeft, columns[i]);
        x += colWidths[i];
    }

    // Border lines
    painter.setPen(QPen(Qt::lightGray, 10));
    painter.setBrush(Qt::NoBrush);
    x = LEFT_MARGIN;
    int totalWidth = 0;
    for (int w : colWidths) totalWidth += w;
    painter.drawRect(x, yOffset - 200, totalWidth, 280);

    // Vertical separators
    x = LEFT_MARGIN;
    for (int i = 0; i < columns.size() - 1 && i < colWidths.size() - 1; ++i) {
        x += colWidths[i];
        painter.drawLine(x, yOffset - 200, x, yOffset + 80);
    }

    return yOffset + 300;
}
