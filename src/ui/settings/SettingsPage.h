#pragma once

#include <QWidget>

class QComboBox;
class QLineEdit;
class QSpinBox;
class QPushButton;
class QGroupBox;

class SettingsPage : public QWidget {
    Q_OBJECT
public:
    explicit SettingsPage(QWidget* parent = nullptr);

private:
    void setupUI();
    void loadSettings();
    void saveSettings();
    void resetSettings();

    // Appearance
    QComboBox* m_themeCombo = nullptr;
    QComboBox* m_languageCombo = nullptr;

    // Database
    QLineEdit* m_localDbPathEdit = nullptr;
    QComboBox* m_remoteDbTypeCombo = nullptr;
    QLineEdit* m_remoteHostEdit = nullptr;
    QSpinBox* m_remotePortSpin = nullptr;
    QLineEdit* m_remoteDbNameEdit = nullptr;
    QLineEdit* m_remoteUserEdit = nullptr;
    QLineEdit* m_remotePasswordEdit = nullptr;

    // Data retention
    QSpinBox* m_retentionDaysSpin = nullptr;
    QSpinBox* m_syncIntervalSpin = nullptr;
};
