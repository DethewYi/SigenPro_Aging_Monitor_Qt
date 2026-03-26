#include "TemplateConfigPage.h"
#include "TemplateEditDialog.h"
#include "core/template_manager/TemplateManager.h"

#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QSplitter>
#include <QListWidget>
#include <QLabel>
#include <QPushButton>
#include <QMessageBox>
#include <QHeaderView>
#include <QApplication>

TemplateConfigPage::TemplateConfigPage(QWidget* parent)
    : QWidget(parent)
{
    setupUI();
    refreshList();
}

void TemplateConfigPage::setupUI()
{
    QVBoxLayout* mainLayout = new QVBoxLayout(this);
    mainLayout->setContentsMargins(16, 16, 16, 16);
    mainLayout->setSpacing(12);

    // Title
    QLabel* titleLabel = new QLabel(tr("Template Management"), this);
    QFont titleFont;
    titleFont.setPointSize(16);
    titleFont.setBold(true);
    titleLabel->setFont(titleFont);
    mainLayout->addWidget(titleLabel);

    // Splitter: left list + right details
    QSplitter* splitter = new QSplitter(Qt::Horizontal, this);

    // Left panel: template list (30%)
    QWidget* leftPanel = new QWidget(splitter);
    QVBoxLayout* leftLayout = new QVBoxLayout(leftPanel);
    leftLayout->setContentsMargins(0, 0, 0, 0);

    QLabel* listLabel = new QLabel(tr("Templates"), leftPanel);
    listLabel->setStyleSheet("font-weight: bold;");
    leftLayout->addWidget(listLabel);

    m_listWidget = new QListWidget(leftPanel);
    m_listWidget->setSelectionMode(QAbstractItemView::SingleSelection);
    leftLayout->addWidget(m_listWidget);

    splitter->addWidget(leftPanel);

    // Right panel: detail view (70%)
    m_detailPanel = new QWidget(splitter);
    QVBoxLayout* detailLayout = new QVBoxLayout(m_detailPanel);
    detailLayout->setContentsMargins(0, 0, 0, 0);

    QLabel* detailTitle = new QLabel(tr("Template Details"), m_detailPanel);
    detailTitle->setStyleSheet("font-weight: bold;");
    detailLayout->addWidget(detailTitle);

    m_detailLabel = new QLabel(m_detailPanel);
    m_detailLabel->setWordWrap(true);
    m_detailLabel->setAlignment(Qt::AlignTop | Qt::AlignLeft);
    m_detailLabel->setTextFormat(Qt::RichText);
    m_detailLabel->setStyleSheet("padding: 8px; background-color: palette(base);"
                                 "border: 1px solid palette(mid);"
                                 "border-radius: 4px;");
    detailLayout->addWidget(m_detailLabel);

    splitter->addWidget(m_detailPanel);

    // Set initial splitter sizes (30% / 70%)
    splitter->setSizes({300, 700});
    mainLayout->addWidget(splitter, 1);

    // Bottom toolbar
    QHBoxLayout* toolbarLayout = new QHBoxLayout();
    toolbarLayout->setSpacing(8);

    m_newBtn = new QPushButton(tr("New"), this);
    m_editBtn = new QPushButton(tr("Edit"), this);
    m_copyBtn = new QPushButton(tr("Copy"), this);
    m_deleteBtn = new QPushButton(tr("Delete"), this);

    toolbarLayout->addWidget(m_newBtn);
    toolbarLayout->addWidget(m_editBtn);
    toolbarLayout->addWidget(m_copyBtn);
    toolbarLayout->addWidget(m_deleteBtn);
    toolbarLayout->addStretch();

    mainLayout->addLayout(toolbarLayout);

    // Connect signals
    connect(m_listWidget, &QListWidget::currentRowChanged,
            this, &TemplateConfigPage::onSelectionChanged);
    connect(m_newBtn, &QPushButton::clicked,
            this, &TemplateConfigPage::onNewTemplate);
    connect(m_editBtn, &QPushButton::clicked,
            this, &TemplateConfigPage::onEditTemplate);
    connect(m_copyBtn, &QPushButton::clicked,
            this, &TemplateConfigPage::onCopyTemplate);
    connect(m_deleteBtn, &QPushButton::clicked,
            this, &TemplateConfigPage::onDeleteTemplate);

    // Initially disable edit/copy/delete
    onSelectionChanged();
}

void TemplateConfigPage::refreshList()
{
    m_listWidget->clear();
    m_templates.clear();
    m_selectedId = -1;

    // Get templates from TemplateManager
    TemplateManager mgr;
    mgr.loadTemplates();
    m_templates = mgr.templates();

    for (const TestTemplate& tmpl : m_templates) {
        m_listWidget->addItem(QString("%1 (ID: %2)").arg(tmpl.name).arg(tmpl.templateId));
    }

    m_detailLabel->setText(tr("Select a template to view details."));
    onSelectionChanged();
}

void TemplateConfigPage::onSelectionChanged()
{
    int row = m_listWidget->currentRow();
    bool hasSelection = (row >= 0 && row < m_templates.size());

    m_editBtn->setEnabled(hasSelection);
    m_copyBtn->setEnabled(hasSelection);
    m_deleteBtn->setEnabled(hasSelection);

    if (hasSelection) {
        m_selectedId = m_templates[row].templateId;
        showTemplateDetails(m_templates[row]);
    } else {
        m_selectedId = -1;
        m_detailLabel->setText(tr("Select a template to view details."));
    }
}

void TemplateConfigPage::showTemplateDetails(const TestTemplate& tmpl)
{
    QString html;
    html += QString("<h3>%1</h3>").arg(tmpl.name);
    html += QString("<table style='margin-left: 8px;'>");
    html += QString("<tr><td><b>%1:</b></td><td>%2</td></tr>")
                .arg(tr("Template ID")).arg(tmpl.templateId);
    html += QString("<tr><td><b>%1:</b></td><td>%2</td></tr>")
                .arg(tr("Product Model")).arg(tmpl.productModel);
    html += QString("<tr><td><b>%1:</b></td><td>%2 %3</td></tr>")
                .arg(tr("Total Duration"))
                .arg(tmpl.totalDurationMinutes)
                .arg(tr("min"));
    html += "</table>";

    // Collection parameters
    html += QString("<h4>%1</h4>").arg(tr("Collection Parameters"));
    html += "<table style='margin-left: 8px;'><tr>"
            "<th>" + tr("Parameter") + "</th>"
            "<th>" + tr("Frequency (Hz)") + "</th></tr>";
    for (auto it = tmpl.collectParams.constBegin(); it != tmpl.collectParams.constEnd(); ++it) {
        html += QString("<tr><td>%1</td><td>%2</td></tr>")
                    .arg(it.key()).arg(it.value());
    }
    html += "</table>";

    // Default thresholds
    html += QString("<h4>%1</h4>").arg(tr("Default Thresholds"));
    html += "<table style='margin-left: 8px;'><tr>"
            "<th>" + tr("Parameter") + "</th>"
            "<th>" + tr("Lower Limit") + "</th>"
            "<th>" + tr("Upper Limit") + "</th>"
            "<th>" + tr("Enabled") + "</th></tr>";
    for (auto it = tmpl.defaultThresholds.constBegin(); it != tmpl.defaultThresholds.constEnd(); ++it) {
        html += QString("<tr><td>%1</td><td>%2</td><td>%3</td><td>%4</td></tr>")
                    .arg(it.key())
                    .arg(it.value().lowerLimit)
                    .arg(it.value().upperLimit)
                    .arg(it.value().enabled ? tr("Yes") : tr("No"));
    }
    html += "</table>";

    // Phases
    if (!tmpl.phases.isEmpty()) {
        html += QString("<h4>%1</h4>").arg(tr("Test Phases"));
        for (const TestPhase& phase : tmpl.phases) {
            html += QString("<h5>%1 (%2 %3)</h5>")
                        .arg(phase.name)
                        .arg(phase.durationMinutes)
                        .arg(tr("min"));
            if (!phase.thresholds.isEmpty()) {
                html += "<table style='margin-left: 8px;'><tr>"
                        "<th>" + tr("Parameter") + "</th>"
                        "<th>" + tr("Lower Limit") + "</th>"
                        "<th>" + tr("Upper Limit") + "</th>"
                        "<th>" + tr("Enabled") + "</th></tr>";
                for (auto it = phase.thresholds.constBegin(); it != phase.thresholds.constEnd(); ++it) {
                    html += QString("<tr><td>%1</td><td>%2</td><td>%3</td><td>%4</td></tr>")
                                .arg(it.key())
                                .arg(it.value().lowerLimit)
                                .arg(it.value().upperLimit)
                                .arg(it.value().enabled ? tr("Yes") : tr("No"));
                }
                html += "</table>";
            }
        }
    }

    m_detailLabel->setText(html);
}

void TemplateConfigPage::onNewTemplate()
{
    TemplateEditDialog dlg(this);
    if (dlg.exec() == QDialog::Accepted) {
        TestTemplate tmpl = dlg.getTemplate();
        TemplateManager mgr;
        int newId = mgr.saveTemplate(tmpl);
        if (newId != -1) {
            refreshList();
            // Select the new template
            for (int i = 0; i < m_templates.size(); ++i) {
                if (m_templates[i].templateId == newId) {
                    m_listWidget->setCurrentRow(i);
                    break;
                }
            }
        } else {
            QMessageBox::warning(this, tr("Error"),
                                 tr("Failed to save the new template."));
        }
    }
}

void TemplateConfigPage::onEditTemplate()
{
    if (m_selectedId == -1) return;

    TemplateManager mgr;
    TestTemplate tmpl = mgr.getTemplate(m_selectedId);
    if (tmpl.templateId == -1) {
        QMessageBox::warning(this, tr("Error"),
                             tr("Template not found."));
        return;
    }

    TemplateEditDialog dlg(this);
    dlg.setTemplate(tmpl);
    if (dlg.exec() == QDialog::Accepted) {
        TestTemplate updated = dlg.getTemplate();
        updated.templateId = m_selectedId;
        int id = mgr.saveTemplate(updated);
        if (id != -1) {
            refreshList();
        } else {
            QMessageBox::warning(this, tr("Error"),
                                 tr("Failed to update the template."));
        }
    }
}

void TemplateConfigPage::onCopyTemplate()
{
    if (m_selectedId == -1) return;

    TemplateManager mgr;
    int newId = mgr.cloneTemplate(m_selectedId);
    if (newId != -1) {
        refreshList();
        // Select the new template
        for (int i = 0; i < m_templates.size(); ++i) {
            if (m_templates[i].templateId == newId) {
                m_listWidget->setCurrentRow(i);
                break;
            }
        }
    } else {
        QMessageBox::warning(this, tr("Error"),
                             tr("Failed to copy the template."));
    }
}

void TemplateConfigPage::onDeleteTemplate()
{
    if (m_selectedId == -1) return;

    int row = m_listWidget->currentRow();
    QString name = m_templates[row].name;

    int ret = QMessageBox::question(this, tr("Confirm Delete"),
        tr("Are you sure you want to delete template \"%1\"?").arg(name),
        QMessageBox::Yes | QMessageBox::No, QMessageBox::No);

    if (ret == QMessageBox::Yes) {
        TemplateManager mgr;
        if (mgr.deleteTemplate(m_selectedId)) {
            refreshList();
        } else {
            QMessageBox::warning(this, tr("Error"),
                                 tr("Failed to delete the template."));
        }
    }
}
