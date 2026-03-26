#pragma once

#include <QString>

enum class DeviceStatus {
    Offline,
    Idle,
    Testing,
    Completed,
    Alarm,
    Fault
};

enum class ChannelStatus {
    Free,
    Bound,
    Testing,
    Fault
};

enum class TestResult {
    Pending,
    Passed,
    Failed,
    Interrupted
};

enum class CommunicationType {
    TcpSocket,
    CanBus,
    Rs485
};

struct DeviceConfig {
    int deviceId = -1;
    QString name;
    QString model;
    CommunicationType commType = CommunicationType::TcpSocket;
    QString ipAddress;
    int port = 0;
    QString protocolName;
    int channelId = -1;
};
