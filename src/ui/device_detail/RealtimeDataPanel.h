#pragma once

#include <QWidget>
#include <QMap>

class QTableWidget;

class RealtimeDataPanel : public QWidget {
    Q_OBJECT
public:
    explicit RealtimeDataPanel(QWidget* parent = nullptr);

    void setupParameters(const QStringList& paramNames);
    void updateParameter(const QString& name, double value);
    void clearAll();
    int parameterCount() const;

private:
    QTableWidget* m_table = nullptr;
    QMap<QString, int> m_paramRows; // param name -> row index
};
