#include "CurveChartWidget.h"
#include <qcustomplot.h>
#include <QVBoxLayout>

CurveChartWidget::CurveChartWidget(QWidget* parent)
    : QWidget(parent)
{
    m_plot = new QCustomPlot(this);

    // Dark theme styling
    m_plot->setBackground(QBrush(QColor("#1e1e2e")));
    m_plot->xAxis->setLabelColor(QColor("#cdd6f4"));
    m_plot->yAxis->setLabelColor(QColor("#cdd6f4"));
    m_plot->xAxis->setTickLabelColor(QColor("#cdd6f4"));
    m_plot->yAxis->setTickLabelColor(QColor("#cdd6f4"));

    // Grid lines
    m_plot->xAxis->grid()->setVisible(true);
    m_plot->yAxis->grid()->setVisible(true);
    m_plot->xAxis->grid()->setPen(QPen(QColor("#45475a"), 1, Qt::DotLine));
    m_plot->yAxis->grid()->setPen(QPen(QColor("#45475a"), 1, Qt::DotLine));

    // Axis base pen
    m_plot->xAxis->setBasePen(QPen(QColor("#45475a")));
    m_plot->yAxis->setBasePen(QPen(QColor("#45475a")));
    m_plot->xAxis->setTickPen(QPen(QColor("#45475a")));
    m_plot->yAxis->setTickPen(QPen(QColor("#45475a")));
    m_plot->xAxis->setSubTickPen(QPen(QColor("#45475a")));
    m_plot->yAxis->setSubTickPen(QPen(QColor("#45475a")));

    // X axis: time in seconds (relative)
    m_plot->xAxis->setLabel(tr("Time (s)"));
    // Y axis: auto-scale
    m_plot->yAxis->setLabel(tr("Value"));

    // Legend
    m_plot->legend->setVisible(true);
    m_plot->legend->setBrush(QBrush(QColor("#1e1e2e")));
    m_plot->legend->setTextColor(QColor("#cdd6f4"));
    m_plot->legend->setBorderPen(QPen(QColor("#45475a")));
    m_plot->axisRect()->insetLayout()->setInsetAlignment(0, Qt::AlignTop | Qt::AlignLeft);

    // Enable user interaction
    m_plot->setInteractions(QCP::iRangeDrag | QCP::iRangeZoom);
    m_plot->axisRect()->setRangeDrag(Qt::Horizontal | Qt::Vertical);
    m_plot->axisRect()->setRangeZoom(Qt::Horizontal | Qt::Vertical);

    // Fill this widget with the plot
    QVBoxLayout* layout = new QVBoxLayout(this);
    layout->setContentsMargins(0, 0, 0, 0);
    layout->addWidget(m_plot);
}

void CurveChartWidget::addCurve(const QString& paramName, const QColor& color)
{
    if (m_graphs.contains(paramName)) {
        return; // Already exists
    }

    QCPGraph* graph = m_plot->addGraph();
    graph->setName(paramName);
    graph->setPen(QPen(color, 2));
    graph->setLineStyle(QCPGraph::lsLine);

    // Allocate data vectors
    m_timeData[paramName] = QVector<double>();
    m_valueData[paramName] = QVector<double>();
    m_graphs[paramName] = graph;

    m_plot->replot();
}

void CurveChartWidget::removeCurve(const QString& paramName)
{
    if (!m_graphs.contains(paramName)) {
        return;
    }

    m_plot->removeGraph(m_graphs[paramName]);
    m_graphs.remove(paramName);
    m_timeData.remove(paramName);
    m_valueData.remove(paramName);

    m_plot->replot();
}

void CurveChartWidget::clearAllCurves()
{
    m_plot->clearGraphs();
    m_graphs.clear();
    m_timeData.clear();
    m_valueData.clear();
    m_startTime = 0;

    m_plot->replot();
}

void CurveChartWidget::appendData(const QString& paramName, double timestamp, double value)
{
    if (!m_graphs.contains(paramName)) {
        return;
    }

    // Initialize start time on first data point
    if (m_startTime == 0) {
        m_startTime = timestamp;
    }

    double relativeTime = timestamp - m_startTime;

    m_timeData[paramName].append(relativeTime);
    m_valueData[paramName].append(value);

    // Remove oldest points that exceed the display window
    while (!m_timeData[paramName].isEmpty() &&
           (m_timeData[paramName].last() - m_timeData[paramName].first()) > m_displayWindow) {
        m_timeData[paramName].removeFirst();
        m_valueData[paramName].removeFirst();
    }

    m_graphs[paramName]->setData(m_timeData[paramName], m_valueData[paramName]);

    // Auto-scroll X axis to follow latest data
    double xMax = relativeTime;
    double xMin = xMax - m_displayWindow;
    if (xMin < 0) {
        xMin = 0;
    }

    m_plot->xAxis->setRange(xMin, xMax);
    m_plot->yAxis->rescale(true);

    m_plot->replot();
}

void CurveChartWidget::clearData()
{
    for (auto it = m_timeData.begin(); it != m_timeData.end(); ++it) {
        it.value().clear();
    }
    for (auto it = m_valueData.begin(); it != m_valueData.end(); ++it) {
        it.value().clear();
    }
    m_startTime = 0;

    for (auto it = m_graphs.begin(); it != m_graphs.end(); ++it) {
        it.value()->data()->clear();
    }

    m_plot->replot();
}

void CurveChartWidget::setDisplayWindowSeconds(int seconds)
{
    m_displayWindow = seconds;
}
