#pragma once

#include <QMap>
#include <QString>
#include <QVector>

struct AlarmThreshold {
    double upperLimit = 0;
    double lowerLimit = 0;
    bool enabled = false;
};

struct TestPhase {
    QString name;
    int durationMinutes = 0;
    QMap<QString, AlarmThreshold> thresholds;
};

struct TestTemplate {
    int templateId = -1;
    QString name;
    QString productModel;
    QMap<QString, double> collectParams;
    int totalDurationMinutes = 0;
    QMap<QString, AlarmThreshold> defaultThresholds;
    QVector<TestPhase> phases;
};
