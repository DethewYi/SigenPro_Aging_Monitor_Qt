#pragma once

#include <QDialog>
#include "core/common/TestTemplate.h"

class QLineEdit;
class QSpinBox;
class QTableWidget;
class QPushButton;
class QTabWidget;

class TemplateEditDialog : public QDialog {
    Q_OBJECT
public:
    explicit TemplateEditDialog(QWidget* parent = nullptr);

    void setTemplate(const TestTemplate& tmpl);
    TestTemplate getTemplate() const;

private slots:
    void onAddParam();
    void onRemoveParam();
    void onAddThreshold();
    void onRemoveThreshold();
    void onAddPhase();
    void onRemovePhase();

private:
    void setupUI();
    void loadPhaseData(int index);
    void saveCurrentPhase(int index);

    // Basic info
    QLineEdit* m_nameEdit = nullptr;
    QLineEdit* m_modelEdit = nullptr;
    QSpinBox* m_durationSpin = nullptr;

    // Collection parameters table
    QTableWidget* m_paramTable = nullptr;  // columns: Param Name, Frequency (Hz)

    // Default thresholds table
    QTableWidget* m_thresholdTable = nullptr;  // columns: Param Name, Lower Limit, Upper Limit, Enabled

    // Phases
    QPushButton* m_addPhaseBtn = nullptr;
    QPushButton* m_removePhaseBtn = nullptr;
    QTabWidget* m_phaseTabs = nullptr;
    QVector<TestPhase> m_phases;
};
