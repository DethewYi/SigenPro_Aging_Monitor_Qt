#pragma once

#include <QDateTime>
#include <QMap>
#include <QString>

struct DeviceData {
    int deviceId = -1;
    QDateTime timestamp;
    QMap<QString, double> parameters;
    bool communicationOk = true;
    int frameErrorCount = 0;
};
