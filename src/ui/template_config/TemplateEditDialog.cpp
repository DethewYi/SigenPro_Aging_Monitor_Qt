#include "TemplateEditDialog.h"

#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QFormLayout>
#include <QGroupBox>
#include <QLineEdit>
#include <QSpinBox>
#include <QDoubleSpinBox>
#include <QTableWidget>
#include <QHeaderView>
#include <QTabWidget>
#include <QLabel>
#include <QPushButton>
#include <QCheckBox>
#include <QMessageBox>
#include <QDialogButtonBox>
#include <QScrollArea>

TemplateEditDialog::TemplateEditDialog(QWidget* parent)
    : QDialog(parent)
{
    setupUI();
    setWindowTitle(tr("Edit Template"));
    resize(700, 600);
}

void TemplateEditDialog::setupUI()
{
    QVBoxLayout* mainLayout = new QVBoxLayout(this);
    mainLayout->setSpacing(12);

    // Use a scroll area for the form content
    QScrollArea* scrollArea = new QScrollArea(this);
    scrollArea->setWidgetResizable(true);
    QWidget* scrollWidget = new QWidget(scrollArea);
    QVBoxLayout* formLayout = new QVBoxLayout(scrollWidget);
    formLayout->setSpacing(12);

    // ========== Group 1: Basic Info ==========
    QGroupBox* basicGroup = new QGroupBox(tr("Basic Information"), scrollWidget);
    QFormLayout* basicLayout = new QFormLayout(basicGroup);

    m_nameEdit = new QLineEdit(basicGroup);
    m_nameEdit->setPlaceholderText(tr("Enter template name"));
    basicLayout->addRow(tr("Name"), m_nameEdit);

    m_modelEdit = new QLineEdit(basicGroup);
    m_modelEdit->setPlaceholderText(tr("Enter product model"));
    basicLayout->addRow(tr("Product Model"), m_modelEdit);

    m_durationSpin = new QSpinBox(basicGroup);
    m_durationSpin->setRange(1, 99999);
    m_durationSpin->setSuffix(tr(" min"));
    m_durationSpin->setValue(60);
    basicLayout->addRow(tr("Total Duration"), m_durationSpin);

    formLayout->addWidget(basicGroup);

    // ========== Group 2: Collection Parameters ==========
    QGroupBox* paramGroup = new QGroupBox(tr("Collection Parameters"), scrollWidget);
    QVBoxLayout* paramLayout = new QVBoxLayout(paramGroup);

    m_paramTable = new QTableWidget(paramGroup);
    m_paramTable->setColumnCount(2);
    m_paramTable->setHorizontalHeaderLabels({
        tr("Parameter Name"),
        tr("Frequency (Hz)")
    });
    m_paramTable->horizontalHeader()->setStretchLastSection(true);
    m_paramTable->horizontalHeader()->setSectionResizeMode(QHeaderView::ResizeToContents);
    m_paramTable->setSelectionBehavior(QAbstractItemView::SelectRows);
    paramLayout->addWidget(m_paramTable);

    QHBoxLayout* paramBtnLayout = new QHBoxLayout();
    QPushButton* addParamBtn = new QPushButton(tr("Add"), paramGroup);
    QPushButton* removeParamBtn = new QPushButton(tr("Remove"), paramGroup);
    paramBtnLayout->addWidget(addParamBtn);
    paramBtnLayout->addWidget(removeParamBtn);
    paramBtnLayout->addStretch();
    paramLayout->addLayout(paramBtnLayout);

    formLayout->addWidget(paramGroup);

    connect(addParamBtn, &QPushButton::clicked, this, &TemplateEditDialog::onAddParam);
    connect(removeParamBtn, &QPushButton::clicked, this, &TemplateEditDialog::onRemoveParam);

    // ========== Group 3: Default Thresholds ==========
    QGroupBox* thresholdGroup = new QGroupBox(tr("Default Thresholds"), scrollWidget);
    QVBoxLayout* thresholdLayout = new QVBoxLayout(thresholdGroup);

    m_thresholdTable = new QTableWidget(thresholdGroup);
    m_thresholdTable->setColumnCount(4);
    m_thresholdTable->setHorizontalHeaderLabels({
        tr("Parameter Name"),
        tr("Lower Limit"),
        tr("Upper Limit"),
        tr("Enabled")
    });
    m_thresholdTable->horizontalHeader()->setStretchLastSection(true);
    m_thresholdTable->horizontalHeader()->setSectionResizeMode(QHeaderView::ResizeToContents);
    m_thresholdTable->setSelectionBehavior(QAbstractItemView::SelectRows);
    thresholdLayout->addWidget(m_thresholdTable);

    QHBoxLayout* thresholdBtnLayout = new QHBoxLayout();
    QPushButton* addThresholdBtn = new QPushButton(tr("Add"), thresholdGroup);
    QPushButton* removeThresholdBtn = new QPushButton(tr("Remove"), thresholdGroup);
    thresholdBtnLayout->addWidget(addThresholdBtn);
    thresholdBtnLayout->addWidget(removeThresholdBtn);
    thresholdBtnLayout->addStretch();
    thresholdLayout->addLayout(thresholdBtnLayout);

    formLayout->addWidget(thresholdGroup);

    connect(addThresholdBtn, &QPushButton::clicked, this, &TemplateEditDialog::onAddThreshold);
    connect(removeThresholdBtn, &QPushButton::clicked, this, &TemplateEditDialog::onRemoveThreshold);

    // ========== Group 4: Test Phases ==========
    QGroupBox* phaseGroup = new QGroupBox(tr("Test Phases"), scrollWidget);
    QVBoxLayout* phaseLayout = new QVBoxLayout(phaseGroup);

    m_phaseTabs = new QTabWidget(phaseGroup);
    phaseLayout->addWidget(m_phaseTabs);

    QHBoxLayout* phaseBtnLayout = new QHBoxLayout();
    m_addPhaseBtn = new QPushButton(tr("Add Phase"), phaseGroup);
    m_removePhaseBtn = new QPushButton(tr("Remove Phase"), phaseGroup);
    phaseBtnLayout->addWidget(m_addPhaseBtn);
    phaseBtnLayout->addWidget(m_removePhaseBtn);
    phaseBtnLayout->addStretch();
    phaseLayout->addLayout(phaseBtnLayout);

    formLayout->addWidget(phaseGroup);

    connect(m_addPhaseBtn, &QPushButton::clicked, this, &TemplateEditDialog::onAddPhase);
    connect(m_removePhaseBtn, &QPushButton::clicked, this, &TemplateEditDialog::onRemovePhase);
    connect(m_phaseTabs, &QTabWidget::currentChanged, this, &TemplateEditDialog::loadPhaseData);

    formLayout->addStretch();

    scrollArea->setWidget(scrollWidget);
    mainLayout->addWidget(scrollArea, 1);

    // ========== OK / Cancel Buttons ==========
    QDialogButtonBox* buttonBox = new QDialogButtonBox(
        QDialogButtonBox::Ok | QDialogButtonBox::Cancel, this);
    mainLayout->addWidget(buttonBox);

    connect(buttonBox, &QDialogButtonBox::accepted, this, &QDialog::accept);
    connect(buttonBox, &QDialogButtonBox::rejected, this, &QDialog::reject);
}

void TemplateEditDialog::setTemplate(const TestTemplate& tmpl)
{
    m_nameEdit->setText(tmpl.name);
    m_modelEdit->setText(tmpl.productModel);
    m_durationSpin->setValue(tmpl.totalDurationMinutes);

    // Load collection parameters
    m_paramTable->setRowCount(0);
    int row = 0;
    for (auto it = tmpl.collectParams.constBegin(); it != tmpl.collectParams.constEnd(); ++it) {
        m_paramTable->insertRow(row);
        m_paramTable->setItem(row, 0, new QTableWidgetItem(it.key()));
        m_paramTable->setItem(row, 1, new QTableWidgetItem(QString::number(it.value())));
        ++row;
    }

    // Load default thresholds
    m_thresholdTable->setRowCount(0);
    row = 0;
    for (auto it = tmpl.defaultThresholds.constBegin(); it != tmpl.defaultThresholds.constEnd(); ++it) {
        m_thresholdTable->insertRow(row);
        m_thresholdTable->setItem(row, 0, new QTableWidgetItem(it.key()));
        m_thresholdTable->setItem(row, 1, new QTableWidgetItem(QString::number(it.value().lowerLimit)));
        m_thresholdTable->setItem(row, 2, new QTableWidgetItem(QString::number(it.value().upperLimit)));

        QCheckBox* cb = new QCheckBox();
        cb->setChecked(it.value().enabled);
        m_thresholdTable->setCellWidget(row, 3, cb);
        ++row;
    }

    // Load phases
    m_phases = tmpl.phases;
    m_phaseTabs->clear();
    for (int i = 0; i < m_phases.size(); ++i) {
        onAddPhase(); // create the tab widget
        // The tab is created with defaults, now populate it
        QWidget* tabWidget = m_phaseTabs->widget(i);
        if (!tabWidget) continue;

        // Find the name and duration fields in the tab
        QLineEdit* phaseNameEdit = tabWidget->findChild<QLineEdit*>("phaseNameEdit");
        QSpinBox* phaseDurationSpin = tabWidget->findChild<QSpinBox*>("phaseDurationSpin");
        QTableWidget* phaseThresholdTable = tabWidget->findChild<QTableWidget*>("phaseThresholdTable");

        if (phaseNameEdit) phaseNameEdit->setText(m_phases[i].name);
        if (phaseDurationSpin) phaseDurationSpin->setValue(m_phases[i].durationMinutes);

        if (phaseThresholdTable) {
            phaseThresholdTable->setRowCount(0);
            int tRow = 0;
            for (auto tit = m_phases[i].thresholds.constBegin();
                 tit != m_phases[i].thresholds.constEnd(); ++tit) {
                phaseThresholdTable->insertRow(tRow);
                phaseThresholdTable->setItem(tRow, 0, new QTableWidgetItem(tit.key()));
                phaseThresholdTable->setItem(tRow, 1, new QTableWidgetItem(QString::number(tit.value().lowerLimit)));
                phaseThresholdTable->setItem(tRow, 2, new QTableWidgetItem(QString::number(tit.value().upperLimit)));

                QCheckBox* tcb = new QCheckBox();
                tcb->setChecked(tit.value().enabled);
                phaseThresholdTable->setCellWidget(tRow, 3, tcb);
                ++tRow;
            }
        }
    }
}

TestTemplate TemplateEditDialog::getTemplate() const
{
    TestTemplate tmpl;
    tmpl.name = m_nameEdit->text().trimmed();
    tmpl.productModel = m_modelEdit->text().trimmed();
    tmpl.totalDurationMinutes = m_durationSpin->value();

    // Collect parameters
    for (int i = 0; i < m_paramTable->rowCount(); ++i) {
        QTableWidgetItem* nameItem = m_paramTable->item(i, 0);
        QTableWidgetItem* freqItem = m_paramTable->item(i, 1);
        if (nameItem && !nameItem->text().trimmed().isEmpty()) {
            double freq = 0.0;
            if (freqItem) freq = freqItem->text().toDouble();
            tmpl.collectParams.insert(nameItem->text().trimmed(), freq);
        }
    }

    // Default thresholds
    for (int i = 0; i < m_thresholdTable->rowCount(); ++i) {
        QTableWidgetItem* nameItem = m_thresholdTable->item(i, 0);
        QTableWidgetItem* lowerItem = m_thresholdTable->item(i, 1);
        QTableWidgetItem* upperItem = m_thresholdTable->item(i, 2);
        QCheckBox* cb = qobject_cast<QCheckBox*>(m_thresholdTable->cellWidget(i, 3));

        if (nameItem && !nameItem->text().trimmed().isEmpty()) {
            AlarmThreshold th;
            th.lowerLimit = lowerItem ? lowerItem->text().toDouble() : 0.0;
            th.upperLimit = upperItem ? upperItem->text().toDouble() : 0.0;
            th.enabled = cb ? cb->isChecked() : false;
            tmpl.defaultThresholds.insert(nameItem->text().trimmed(), th);
        }
    }

    // Phases - save current tab first
    int currentTab = m_phaseTabs->currentIndex();
    if (currentTab >= 0 && currentTab < m_phases.size()) {
        saveCurrentPhase(currentTab);
    }

    tmpl.phases = m_phases;

    return tmpl;
}

void TemplateEditDialog::saveCurrentPhase(int index)
{
    if (index < 0 || index >= m_phaseTabs->count()) return;

    QWidget* tabWidget = m_phaseTabs->widget(index);
    if (!tabWidget) return;

    QLineEdit* phaseNameEdit = tabWidget->findChild<QLineEdit*>("phaseNameEdit");
    QSpinBox* phaseDurationSpin = tabWidget->findChild<QSpinBox*>("phaseDurationSpin");
    QTableWidget* phaseThresholdTable = tabWidget->findChild<QTableWidget*>("phaseThresholdTable");

    TestPhase phase;
    if (phaseNameEdit) phase.name = phaseNameEdit->text().trimmed();
    if (phaseDurationSpin) phase.durationMinutes = phaseDurationSpin->value();

    if (phaseThresholdTable) {
        for (int i = 0; i < phaseThresholdTable->rowCount(); ++i) {
            QTableWidgetItem* nameItem = phaseThresholdTable->item(i, 0);
            QTableWidgetItem* lowerItem = phaseThresholdTable->item(i, 1);
            QTableWidgetItem* upperItem = phaseThresholdTable->item(i, 2);
            QCheckBox* cb = qobject_cast<QCheckBox*>(phaseThresholdTable->cellWidget(i, 3));

            if (nameItem && !nameItem->text().trimmed().isEmpty()) {
                AlarmThreshold th;
                th.lowerLimit = lowerItem ? lowerItem->text().toDouble() : 0.0;
                th.upperLimit = upperItem ? upperItem->text().toDouble() : 0.0;
                th.enabled = cb ? cb->isChecked() : false;
                phase.thresholds.insert(nameItem->text().trimmed(), th);
            }
        }
    }

    if (index < m_phases.size()) {
        m_phases[index] = phase;
    }
}

void TemplateEditDialog::onAddParam()
{
    int row = m_paramTable->rowCount();
    m_paramTable->insertRow(row);
    m_paramTable->setItem(row, 0, new QTableWidgetItem());
    m_paramTable->setItem(row, 1, new QTableWidgetItem("1.0"));
    m_paramTable->setCurrentCell(row, 0);
    m_paramTable->editItem(m_paramTable->item(row, 0));
}

void TemplateEditDialog::onRemoveParam()
{
    int row = m_paramTable->currentRow();
    if (row >= 0) {
        m_paramTable->removeRow(row);
    }
}

void TemplateEditDialog::onAddThreshold()
{
    int row = m_thresholdTable->rowCount();
    m_thresholdTable->insertRow(row);
    m_thresholdTable->setItem(row, 0, new QTableWidgetItem());
    m_thresholdTable->setItem(row, 1, new QTableWidgetItem("0.0"));
    m_thresholdTable->setItem(row, 2, new QTableWidgetItem("0.0"));

    QCheckBox* cb = new QCheckBox();
    cb->setChecked(true);
    m_thresholdTable->setCellWidget(row, 3, cb);

    m_thresholdTable->setCurrentCell(row, 0);
    m_thresholdTable->editItem(m_thresholdTable->item(row, 0));
}

void TemplateEditDialog::onRemoveThreshold()
{
    int row = m_thresholdTable->currentRow();
    if (row >= 0) {
        m_thresholdTable->removeRow(row);
    }
}

void TemplateEditDialog::onAddPhase()
{
    // Save current phase data before adding a new one
    int currentTab = m_phaseTabs->currentIndex();
    if (currentTab >= 0 && currentTab < m_phases.size()) {
        saveCurrentPhase(currentTab);
    }

    TestPhase phase;
    phase.name = tr("Phase %1").arg(m_phases.size() + 1);
    phase.durationMinutes = 10;
    m_phases.append(phase);

    // Create tab widget
    QWidget* phaseTab = new QWidget(m_phaseTabs);
    QVBoxLayout* tabLayout = new QVBoxLayout(phaseTab);

    QFormLayout* phaseInfoLayout = new QFormLayout();
    QLineEdit* phaseNameEdit = new QLineEdit(phase.name, phaseTab);
    phaseNameEdit->setObjectName("phaseNameEdit");

    QSpinBox* phaseDurationSpin = new QSpinBox(phaseTab);
    phaseDurationSpin->setRange(1, 99999);
    phaseDurationSpin->setSuffix(tr(" min"));
    phaseDurationSpin->setValue(phase.durationMinutes);
    phaseDurationSpin->setObjectName("phaseDurationSpin");

    phaseInfoLayout->addRow(tr("Phase Name"), phaseNameEdit);
    phaseInfoLayout->addRow(tr("Duration"), phaseDurationSpin);
    tabLayout->addLayout(phaseInfoLayout);

    // Phase thresholds table
    QLabel* threshLabel = new QLabel(tr("Phase Thresholds"), phaseTab);
    threshLabel->setStyleSheet("font-weight: bold;");
    tabLayout->addWidget(threshLabel);

    QTableWidget* phaseThresholdTable = new QTableWidget(phaseTab);
    phaseThresholdTable->setObjectName("phaseThresholdTable");
    phaseThresholdTable->setColumnCount(4);
    phaseThresholdTable->setHorizontalHeaderLabels({
        tr("Parameter Name"),
        tr("Lower Limit"),
        tr("Upper Limit"),
        tr("Enabled")
    });
    phaseThresholdTable->horizontalHeader()->setStretchLastSection(true);
    phaseThresholdTable->horizontalHeader()->setSectionResizeMode(QHeaderView::ResizeToContents);
    phaseThresholdTable->setSelectionBehavior(QAbstractItemView::SelectRows);
    tabLayout->addWidget(phaseThresholdTable);

    QHBoxLayout* pThreshBtnLayout = new QHBoxLayout();
    QPushButton* addPThreshBtn = new QPushButton(tr("Add"), phaseTab);
    QPushButton* removePThreshBtn = new QPushButton(tr("Remove"), phaseTab);
    pThreshBtnLayout->addWidget(addPThreshBtn);
    pThreshBtnLayout->addWidget(removePThreshBtn);
    pThreshBtnLayout->addStretch();
    tabLayout->addLayout(pThreshBtnLayout);

    // Connect phase threshold add/remove buttons
    int phaseIndex = m_phases.size() - 1;
    connect(addPThreshBtn, &QPushButton::clicked, phaseThresholdTable, [this, phaseThresholdTable]() {
        int r = phaseThresholdTable->rowCount();
        phaseThresholdTable->insertRow(r);
        phaseThresholdTable->setItem(r, 0, new QTableWidgetItem());
        phaseThresholdTable->setItem(r, 1, new QTableWidgetItem("0.0"));
        phaseThresholdTable->setItem(r, 2, new QTableWidgetItem("0.0"));
        QCheckBox* cb = new QCheckBox();
        cb->setChecked(true);
        phaseThresholdTable->setCellWidget(r, 3, cb);
        phaseThresholdTable->setCurrentCell(r, 0);
        phaseThresholdTable->editItem(phaseThresholdTable->item(r, 0));
    });

    connect(removePThreshBtn, &QPushButton::clicked, phaseThresholdTable, [phaseThresholdTable]() {
        int r = phaseThresholdTable->currentRow();
        if (r >= 0) {
            phaseThresholdTable->removeRow(r);
        }
    });

    // Connect name changes to update tab title
    connect(phaseNameEdit, &QLineEdit::textChanged, this,
            [this, phaseIndex](const QString& text) {
                if (phaseIndex < m_phaseTabs->count()) {
                    m_phaseTabs->setTabText(phaseIndex, text.isEmpty()
                        ? tr("Phase %1").arg(phaseIndex + 1) : text);
                }
            });

    m_phaseTabs->addTab(phaseTab, phase.name);
    m_phaseTabs->setCurrentIndex(m_phaseTabs->count() - 1);
}

void TemplateEditDialog::onRemovePhase()
{
    int index = m_phaseTabs->currentIndex();
    if (index < 0) return;

    QString phaseName = m_phases[index].name;
    int ret = QMessageBox::question(this, tr("Confirm Remove"),
        tr("Are you sure you want to remove phase \"%1\"?").arg(phaseName),
        QMessageBox::Yes | QMessageBox::No, QMessageBox::No);

    if (ret == QMessageBox::Yes) {
        m_phases.removeAt(index);
        m_phaseTabs->removeTab(index);
    }
}

void TemplateEditDialog::loadPhaseData(int index)
{
    // Save the previous tab's data before switching
    // (This is handled by saveCurrentPhase being called elsewhere when needed)
}
