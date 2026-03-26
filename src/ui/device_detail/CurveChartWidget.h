#pragma once

#include <QWidget>
#include <QMap>
#include <QDateTime>
#include "core/common/DeviceData.h"

class QCustomPlot;
class QCPGraph;

class CurveChartWidget : public QWidget {
    Q_OBJECT
public:
    explicit CurveChartWidget(QWidget* parent = nullptr);

    void addCurve(const QString& paramName, const QColor& color);
    void removeCurve(const QString& paramName);
    void clearAllCurves();
    void appendData(const QString& paramName, double timestamp, double value);
    void clearData();
    void setDisplayWindowSeconds(int seconds); // default 300 (5 min)

private:
    QCustomPlot* m_plot = nullptr;
    QMap<QString, QCPGraph*> m_graphs;
    QMap<QString, QVector<double>> m_timeData;
    QMap<QString, QVector<double>> m_valueData;
    int m_displayWindow = 300;
    double m_startTime = 0;
};
