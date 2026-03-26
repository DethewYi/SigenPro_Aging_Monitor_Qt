#pragma once

#include <QWidget>
#include <QMap>
#include "core/common/Types.h"

class QLabel;

class DeviceCardWidget : public QWidget {
    Q_OBJECT
public:
    explicit DeviceCardWidget(int deviceId, QWidget* parent = nullptr);

    void setDeviceInfo(const QString& name, const QString& model, const QString& sn);
    void setStatus(DeviceStatus status);
    void updateParameter(const QString& name, double value, const QString& unit);
    void updateParameters(const QMap<QString, double>& parameters);
    void clearParameters();

signals:
    void clicked(int deviceId);

protected:
    void mousePressEvent(QMouseEvent* event) override;

private:
    int m_deviceId = -1;
    DeviceStatus m_status = DeviceStatus::Offline;
    QString m_name;
    QString m_model;
    QString m_sn;

    QLabel* m_nameLabel = nullptr;
    QLabel* m_modelLabel = nullptr;
    QLabel* m_snLabel = nullptr;
    QLabel* m_statusLabel = nullptr;
    QMap<QString, QLabel*> m_paramLabels;

    void setupUI();
    void updateStyleSheet();
    static QString statusColor(DeviceStatus status);
    static QString statusText(DeviceStatus status);
};
