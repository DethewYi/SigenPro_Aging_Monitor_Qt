#pragma once

#include "Types.h"
#include <QString>

struct ChannelInfo {
    int channelId = -1;
    ChannelStatus status = ChannelStatus::Free;
    QString boundSN;
    QString boundPN;
    int powerControllerId = -1;
    int contactorControllerId = -1;
    int powerChannel = -1;
    int contactorChannel = -1;
    QString powerProtocolName;
    QString contactorProtocolName;
};
