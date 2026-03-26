#include "PluginManager.h"
#include <QDir>
#include <QCoreApplication>
#include <QDebug>

PluginManager& PluginManager::instance()
{
    static PluginManager inst;
    return inst;
}

void PluginManager::loadPlugins(const QString& pluginDir)
{
    QDir dir(pluginDir);
    if (!dir.exists()) {
        qDebug() << "Plugin directory does not exist:" << pluginDir;
        return;
    }

    QStringList filters;
    filters << "*.dll" << "*.so" << "*.dylib";

    for (const QFileInfo& fileInfo : dir.entryInfoList(filters, QDir::Files)) {
        QPluginLoader loader(fileInfo.absoluteFilePath());
        QObject* plugin = loader.instance();
        if (!plugin) {
            qDebug() << "Failed to load plugin:" << fileInfo.fileName()
                     << "Error:" << loader.errorString();
            continue;
        }

        // Check if it's a protocol parser
        auto* parser = qobject_cast<IProtocolParser*>(plugin);
        if (parser) {
            QString name = parser->protocolName();
            if (!name.isEmpty()) {
                PluginInfo info{name, fileInfo.absoluteFilePath()};
                m_parserPlugins[name] = info;
                m_loadedPlugins[fileInfo.absoluteFilePath()] = plugin;
                qDebug() << "Loaded parser plugin:" << name;
            }
        }

        // Check if it's an instrument controller
        auto* controller = qobject_cast<IInstrumentController*>(plugin);
        if (controller) {
            QString name = controller->protocolName();
            if (!name.isEmpty()) {
                PluginInfo info{name, fileInfo.absoluteFilePath()};
                m_controllerPlugins[name] = info;
                m_loadedPlugins[fileInfo.absoluteFilePath()] = plugin;
                qDebug() << "Loaded controller plugin:" << name;
            }
        }
    }
}

IProtocolParser* PluginManager::createParser(const QString& protocolName)
{
    if (!m_parserPlugins.contains(protocolName)) {
        return nullptr;
    }

    QString filePath = m_parserPlugins[protocolName].filePath;
    QPluginLoader loader(filePath);
    QObject* plugin = loader.instance();
    return qobject_cast<IProtocolParser*>(plugin);
}

IInstrumentController* PluginManager::createController(const QString& protocolName)
{
    if (!m_controllerPlugins.contains(protocolName)) {
        return nullptr;
    }

    QString filePath = m_controllerPlugins[protocolName].filePath;
    QPluginLoader loader(filePath);
    QObject* plugin = loader.instance();
    return qobject_cast<IInstrumentController*>(plugin);
}

QStringList PluginManager::availableParsers() const
{
    return m_parserPlugins.keys();
}

QStringList PluginManager::availableControllers() const
{
    return m_controllerPlugins.keys();
}
