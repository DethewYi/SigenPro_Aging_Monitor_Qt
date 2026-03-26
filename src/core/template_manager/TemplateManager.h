#pragma once

#include <QObject>
#include <QVector>
#include "core/common/TestTemplate.h"

class TemplateManager : public QObject {
    Q_OBJECT
public:
    explicit TemplateManager(QObject* parent = nullptr);

    void loadTemplates();
    QVector<TestTemplate> templates() const;
    TestTemplate getTemplate(int templateId) const;
    QVector<TestTemplate> getTemplatesByModel(const QString& productModel) const;
    int saveTemplate(const TestTemplate& tmpl);
    bool deleteTemplate(int templateId);
    int cloneTemplate(int templateId);  // returns new template ID

signals:
    void templateUpdated();
    void templateAdded(int templateId);

private:
    QVector<TestTemplate> m_templates;
};
