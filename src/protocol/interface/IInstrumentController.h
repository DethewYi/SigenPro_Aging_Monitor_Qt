#pragma once

#include <QtPlugin>
#include <QString>
#include "core/common/Types.h"

struct InstrumentStatus {
    bool powered = false;
    double voltage = 0;
    double current = 0;
    bool fault = false;
};

class IInstrumentController {
public:
    virtual ~IInstrumentController() = default;
    virtual bool connect(const DeviceConfig& config) = 0;
    virtual void disconnect() = 0;
    virtual bool isConnected() const = 0;
    virtual bool powerOn(int channel) = 0;
    virtual bool powerOff(int channel) = 0;
    virtual bool setVoltage(int channel, double voltage) = 0;
    virtual bool setCurrent(int channel, double current) = 0;
    virtual bool readStatus(int channel, InstrumentStatus& status) = 0;
    virtual QString protocolName() const = 0;
};

#define IInstrumentController_iid "com.sigenpro.IInstrumentController"
Q_DECLARE_INTERFACE(IInstrumentController, IInstrumentController_iid)
