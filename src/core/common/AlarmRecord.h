#pragma once

#include <QDateTime>
#include <QString>

struct AlarmRecord {
    int id = -1;
    QDateTime timestamp;
    int deviceId = -1;
    QString deviceName;
    QString paramName;
    double currentValue = 0;
    double threshold = 0;
    bool isUpperLimit = true;
    bool acknowledged = false;
    QString message;
};
