#pragma once

#include <QObject>
#include <QMap>
#include <QVector>
#include "core/common/ChannelInfo.h"
#include "core/common/Types.h"
#include "protocol/interface/IInstrumentController.h"
#include "protocol/plugin_loader/PluginManager.h"

class ChannelManager : public QObject {
    Q_OBJECT
public:
    explicit ChannelManager(QObject* parent = nullptr);

    void loadChannels();
    QVector<ChannelInfo> allChannels() const;
    ChannelInfo channelInfo(int channelId) const;
    QVector<ChannelInfo> channelsByStatus(ChannelStatus status) const;

    bool bindProduct(int channelId, const QString& sn, const QString& pn);
    bool unbindProduct(int channelId);
    bool powerOn(int channelId);
    bool powerOff(int channelId);
    bool setPower(int channelId, double voltage, double current);
    void emergencyStopAll();

signals:
    void channelStatusChanged(int channelId, ChannelStatus status);
    void bindingChanged(int channelId, const QString& sn, const QString& pn);
    void powerStateChanged(int channelId, bool powered);

private:
    bool initializeController(ChannelInfo& info);
    QMap<int, ChannelInfo> m_channels;
    QMap<int, IInstrumentController*> m_powerControllers;
    QMap<int, IInstrumentController*> m_contactorControllers;
};
