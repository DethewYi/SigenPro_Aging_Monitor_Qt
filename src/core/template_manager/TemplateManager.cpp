#include "core/template_manager/TemplateManager.h"
#include "storage/DatabaseManager.h"
#include <QDebug>

TemplateManager::TemplateManager(QObject* parent)
    : QObject(parent)
{
}

void TemplateManager::loadTemplates()
{
    m_templates = DatabaseManager::instance().localDb()->loadAllTemplates();
    qDebug() << "TemplateManager: loaded" << m_templates.size() << "templates";
}

QVector<TestTemplate> TemplateManager::templates() const
{
    return m_templates;
}

TestTemplate TemplateManager::getTemplate(int templateId) const
{
    for (const TestTemplate& tmpl : m_templates) {
        if (tmpl.templateId == templateId) {
            return tmpl;
        }
    }
    return TestTemplate();
}

QVector<TestTemplate> TemplateManager::getTemplatesByModel(const QString& productModel) const
{
    QVector<TestTemplate> result;
    for (const TestTemplate& tmpl : m_templates) {
        if (tmpl.productModel == productModel) {
            result.append(tmpl);
        }
    }
    return result;
}

int TemplateManager::saveTemplate(const TestTemplate& tmpl)
{
    bool isNew = (tmpl.templateId == -1);
    bool ok = DatabaseManager::instance().localDb()->saveTemplate(tmpl);

    if (!ok) {
        qWarning() << "TemplateManager: failed to save template" << tmpl.name;
        return -1;
    }

    if (isNew) {
        // Reload all templates to get the auto-generated ID from the database
        loadTemplates();
        // The newly saved template will be the last one added
        int newId = -1;
        if (!m_templates.isEmpty()) {
            // Find the template by name since the ID was -1 before saving
            for (const TestTemplate& t : m_templates) {
                if (t.name == tmpl.name) {
                    newId = t.templateId;
                    break;
                }
            }
        }
        emit templateAdded(newId);
        return newId;
    } else {
        // Update existing template in the local cache
        for (int i = 0; i < m_templates.size(); ++i) {
            if (m_templates[i].templateId == tmpl.templateId) {
                m_templates[i] = tmpl;
                break;
            }
        }
        emit templateUpdated();
        return tmpl.templateId;
    }
}

bool TemplateManager::deleteTemplate(int templateId)
{
    bool ok = DatabaseManager::instance().localDb()->deleteTemplate(templateId);
    if (!ok) {
        qWarning() << "TemplateManager: failed to delete template" << templateId;
        return false;
    }

    // Remove from local cache
    for (int i = 0; i < m_templates.size(); ++i) {
        if (m_templates[i].templateId == templateId) {
            m_templates.removeAt(i);
            break;
        }
    }

    emit templateUpdated();
    return true;
}

int TemplateManager::cloneTemplate(int templateId)
{
    TestTemplate original = getTemplate(templateId);
    if (original.templateId == -1) {
        qWarning() << "TemplateManager: cannot clone, template" << templateId << "not found";
        return -1;
    }

    TestTemplate clone = original;
    clone.templateId = -1;
    clone.name = original.name + " - Copy";

    int newId = saveTemplate(clone);
    return newId;
}
