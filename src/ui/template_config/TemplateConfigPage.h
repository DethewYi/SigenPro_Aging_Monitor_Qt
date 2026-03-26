#pragma once

#include <QWidget>
#include <QVector>
#include "core/common/TestTemplate.h"

class QListWidget;
class QLabel;
class QPushButton;

class TemplateConfigPage : public QWidget {
    Q_OBJECT
public:
    explicit TemplateConfigPage(QWidget* parent = nullptr);

    void refreshList();

private slots:
    void onNewTemplate();
    void onEditTemplate();
    void onCopyTemplate();
    void onDeleteTemplate();
    void onSelectionChanged();

private:
    void setupUI();
    void showTemplateDetails(const TestTemplate& tmpl);

    QListWidget* m_listWidget = nullptr;
    QWidget* m_detailPanel = nullptr;
    QLabel* m_detailLabel = nullptr;

    QPushButton* m_newBtn = nullptr;
    QPushButton* m_editBtn = nullptr;
    QPushButton* m_copyBtn = nullptr;
    QPushButton* m_deleteBtn = nullptr;

    QVector<TestTemplate> m_templates;
    int m_selectedId = -1;
};
