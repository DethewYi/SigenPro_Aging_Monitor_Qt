#include "ChannelManager.h"
#include "storage/DatabaseManager.h"
#include <QDebug>

ChannelManager::ChannelManager(QObject* parent)
    : QObject(parent)
{
}

void ChannelManager::loadChannels()
{
    m_channels.clear();

    auto channels = DatabaseManager::instance().localDb()->loadAllChannels();
    for (auto& ch : channels) {
        m_channels.insert(ch.channelId, ch);
    }

    qDebug() << "Loaded" << m_channels.size() << "channels from database";
}

QVector<ChannelInfo> ChannelManager::allChannels() const
{
    return m_channels.values().toVector();
}

ChannelInfo ChannelManager::channelInfo(int channelId) const
{
    return m_channels.value(channelId, ChannelInfo{});
}

QVector<ChannelInfo> ChannelManager::channelsByStatus(ChannelStatus status) const
{
    QVector<ChannelInfo> result;
    for (const auto& ch : m_channels) {
        if (ch.status == status) {
            result.append(ch);
        }
    }
    return result;
}

bool ChannelManager::bindProduct(int channelId, const QString& sn, const QString& pn)
{
    if (!m_channels.contains(channelId)) {
        qWarning() << "Cannot bind: channel" << channelId << "not found";
        return false;
    }

    auto& ch = m_channels[channelId];
    if (ch.status == ChannelStatus::Testing) {
        qWarning() << "Cannot bind: channel" << channelId << "is currently testing";
        return false;
    }

    ch.boundSN = sn;
    ch.boundPN = pn;
    ch.status = ChannelStatus::Bound;

    DatabaseManager::instance().localDb()->saveChannelInfo(ch);

    emit channelStatusChanged(channelId, ch.status);
    emit bindingChanged(channelId, sn, pn);

    qDebug() << "Bound product SN:" << sn << "PN:" << pn << "to channel" << channelId;
    return true;
}

bool ChannelManager::unbindProduct(int channelId)
{
    if (!m_channels.contains(channelId)) {
        qWarning() << "Cannot unbind: channel" << channelId << "not found";
        return false;
    }

    auto& ch = m_channels[channelId];

    // If channel was testing, power off first
    if (ch.status == ChannelStatus::Testing) {
        powerOff(channelId);
    }

    QString sn = ch.boundSN;
    QString pn = ch.boundPN;

    ch.boundSN.clear();
    ch.boundPN.clear();
    ch.status = ChannelStatus::Free;

    DatabaseManager::instance().localDb()->saveChannelInfo(ch);

    emit channelStatusChanged(channelId, ch.status);
    emit bindingChanged(channelId, QString(), QString());

    qDebug() << "Unbound product from channel" << channelId;
    return true;
}

bool ChannelManager::powerOn(int channelId)
{
    if (!m_channels.contains(channelId)) {
        qWarning() << "Cannot power on: channel" << channelId << "not found";
        return false;
    }

    auto& ch = m_channels[channelId];
    if (ch.status != ChannelStatus::Bound && ch.status != ChannelStatus::Testing) {
        qWarning() << "Cannot power on: channel" << channelId
                   << "is not bound or testing, status:" << static_cast<int>(ch.status);
        return false;
    }

    // Initialize power controller if needed
    if (!m_powerControllers.contains(ch.powerControllerId) || ch.powerControllerId < 0) {
        if (!initializeController(ch)) {
            qWarning() << "Failed to initialize controller for channel" << channelId;
            return false;
        }
    }

    // Turn on contactor first, then power supply
    bool success = true;

    if (ch.contactorControllerId >= 0 && m_contactorControllers.contains(ch.contactorControllerId)) {
        if (!m_contactorControllers.value(ch.contactorControllerId)->powerOn(ch.contactorChannel)) {
            qWarning() << "Failed to turn on contactor for channel" << channelId;
            success = false;
        }
    }

    if (ch.powerControllerId >= 0 && m_powerControllers.contains(ch.powerControllerId)) {
        if (!m_powerControllers.value(ch.powerControllerId)->powerOn(ch.powerChannel)) {
            qWarning() << "Failed to turn on power supply for channel" << channelId;
            success = false;
            // Turn off contactor on failure
            if (ch.contactorControllerId >= 0 && m_contactorControllers.contains(ch.contactorControllerId)) {
                m_contactorControllers.value(ch.contactorControllerId)->powerOff(ch.contactorChannel);
            }
        }
    }

    if (success) {
        ch.status = ChannelStatus::Testing;
        DatabaseManager::instance().localDb()->saveChannelInfo(ch);
        emit channelStatusChanged(channelId, ch.status);
        emit powerStateChanged(channelId, true);
        qDebug() << "Powered on channel" << channelId;
    }

    return success;
}

bool ChannelManager::powerOff(int channelId)
{
    if (!m_channels.contains(channelId)) {
        qWarning() << "Cannot power off: channel" << channelId << "not found";
        return false;
    }

    auto& ch = m_channels[channelId];

    bool success = true;

    // Turn off power supply first, then contactor
    if (ch.powerControllerId >= 0 && m_powerControllers.contains(ch.powerControllerId)) {
        if (!m_powerControllers.value(ch.powerControllerId)->powerOff(ch.powerChannel)) {
            qWarning() << "Failed to turn off power supply for channel" << channelId;
            success = false;
        }
    }

    if (ch.contactorControllerId >= 0 && m_contactorControllers.contains(ch.contactorControllerId)) {
        if (!m_contactorControllers.value(ch.contactorControllerId)->powerOff(ch.contactorChannel)) {
            qWarning() << "Failed to turn off contactor for channel" << channelId;
            success = false;
        }
    }

    if (success && ch.status == ChannelStatus::Testing) {
        ch.status = ChannelStatus::Bound;
        DatabaseManager::instance().localDb()->saveChannelInfo(ch);
        emit channelStatusChanged(channelId, ch.status);
    }

    emit powerStateChanged(channelId, false);
    qDebug() << "Powered off channel" << channelId;
    return success;
}

bool ChannelManager::setPower(int channelId, double voltage, double current)
{
    if (!m_channels.contains(channelId)) {
        qWarning() << "Cannot set power: channel" << channelId << "not found";
        return false;
    }

    auto& ch = m_channels[channelId];

    if (ch.powerControllerId >= 0 && m_powerControllers.contains(ch.powerControllerId)) {
        auto* ctrl = m_powerControllers.value(ch.powerControllerId);
        if (!ctrl->setVoltage(ch.powerChannel, voltage)) {
            qWarning() << "Failed to set voltage for channel" << channelId;
            return false;
        }
        if (!ctrl->setCurrent(ch.powerChannel, current)) {
            qWarning() << "Failed to set current for channel" << channelId;
            return false;
        }
        qDebug() << "Set power for channel" << channelId
                 << "voltage:" << voltage << "current:" << current;
        return true;
    }

    qWarning() << "No power controller available for channel" << channelId;
    return false;
}

void ChannelManager::emergencyStopAll()
{
    qDebug() << "Emergency stop: powering off all channels";

    for (auto it = m_channels.begin(); it != m_channels.end(); ++it) {
        int channelId = it.key();
        if (it.value().status == ChannelStatus::Testing) {
            powerOff(channelId);
        }
    }
}

bool ChannelManager::initializeController(ChannelInfo& info)
{
    // Initialize power controller
    if (!info.powerProtocolName.isEmpty() && info.powerControllerId >= 0) {
        if (!m_powerControllers.contains(info.powerControllerId)) {
            auto* ctrl = PluginManager::instance().createController(info.powerProtocolName);
            if (ctrl) {
                DeviceConfig config;
                config.deviceId = info.powerControllerId;
                config.protocolName = info.powerProtocolName;
                config.channelId = info.channelId;
                if (ctrl->connect(config)) {
                    m_powerControllers.insert(info.powerControllerId, ctrl);
                    qDebug() << "Initialized power controller for channel" << info.channelId;
                } else {
                    qWarning() << "Failed to connect power controller for channel" << info.channelId;
                    return false;
                }
            } else {
                qWarning() << "Failed to create power controller with protocol:" << info.powerProtocolName;
                return false;
            }
        }
    }

    // Initialize contactor controller
    if (!info.contactorProtocolName.isEmpty() && info.contactorControllerId >= 0) {
        if (!m_contactorControllers.contains(info.contactorControllerId)) {
            auto* ctrl = PluginManager::instance().createController(info.contactorProtocolName);
            if (ctrl) {
                DeviceConfig config;
                config.deviceId = info.contactorControllerId;
                config.protocolName = info.contactorProtocolName;
                config.channelId = info.channelId;
                if (ctrl->connect(config)) {
                    m_contactorControllers.insert(info.contactorControllerId, ctrl);
                    qDebug() << "Initialized contactor controller for channel" << info.channelId;
                } else {
                    qWarning() << "Failed to connect contactor controller for channel" << info.channelId;
                    return false;
                }
            } else {
                qWarning() << "Failed to create contactor controller with protocol:" << info.contactorProtocolName;
                return false;
            }
        }
    }

    return true;
}
