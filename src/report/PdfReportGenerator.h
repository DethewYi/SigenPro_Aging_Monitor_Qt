#pragma once

#include <QObject>
#include <QString>
#include <QVariantMap>
#include <QVariantList>

class QPainter;

class PdfReportGenerator : public QObject {
    Q_OBJECT
public:
    explicit PdfReportGenerator(QObject* parent = nullptr);

    bool generateReport(int testRecordId, const QString& filePath);
    bool generateReportPreview(int testRecordId);

private:
    void drawHeader(QPainter& painter, int pageWidth, int pageHeight);
    void drawTestInfo(QPainter& painter, int yOffset, const QVariantMap& recordInfo);
    void drawStatistics(QPainter& painter, int yOffset, const QVariantList& stats);
    void drawAlarmTable(QPainter& painter, int yOffset, const QVariantList& alarms);
    void drawConclusion(QPainter& painter, int yOffset, int testResult);
    void drawFooter(QPainter& painter, int pageHeight, int pageNumber);

    int drawTableRow(QPainter& painter, int yOffset, const QStringList& columns,
                     const QList<int>& colWidths, bool isHeader = false);

    static constexpr int LEFT_MARGIN = 570;   // ~20mm at 72 DPI
    static constexpr int RIGHT_MARGIN = 570;
    static constexpr int TOP_MARGIN = 570;
    static constexpr int BOTTOM_MARGIN = 570;
    static constexpr int LINE_SPACING = 250;
};
