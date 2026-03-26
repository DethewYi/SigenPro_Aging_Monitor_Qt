#pragma once

#include <QObject>
#include <QString>
#include <QMap>
#include <QPluginLoader>
#include <QVector>
#include "protocol/interface/IProtocolParser.h"
#include "protocol/interface/IInstrumentController.h"

class PluginManager : public QObject {
    Q_OBJECT
public:
    static PluginManager& instance();

    void loadPlugins(const QString& pluginDir);
    IProtocolParser* createParser(const QString& protocolName);
    IInstrumentController* createController(const QString& protocolName);
    QStringList availableParsers() const;
    QStringList availableControllers() const;

private:
    PluginManager() = default;

    struct PluginInfo {
        QString name;
        QString filePath;
    };

    QMap<QString, PluginInfo> m_parserPlugins;    // protocol name -> plugin info
    QMap<QString, PluginInfo> m_controllerPlugins; // protocol name -> plugin info
    QMap<QString, QObject*> m_loadedPlugins;       // file path -> loaded instance
};
