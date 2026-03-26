#pragma once

#include <QtPlugin>
#include <QByteArray>
#include <QString>
#include "core/common/DeviceData.h"

class IProtocolParser {
public:
    virtual ~IProtocolParser() = default;
    virtual bool parse(const QByteArray& rawData, DeviceData& output) = 0;
    virtual QByteArray buildRequest(const QString& cmd) = 0;
    virtual QString protocolName() const = 0;
    virtual bool initialize(const QVariantMap& config) { Q_UNUSED(config); return true; }
};

#define IProtocolParser_iid "com.sigenpro.IProtocolParser"
Q_DECLARE_INTERFACE(IProtocolParser, IProtocolParser_iid)
