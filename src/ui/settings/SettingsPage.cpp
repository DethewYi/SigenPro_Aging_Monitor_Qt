#include "SettingsPage.h"

#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QFormLayout>
#include <QGroupBox>
#include <QComboBox>
#include <QLineEdit>
#include <QSpinBox>
#include <QPushButton>
#include <QFileDialog>
#include <QSettings>
#include <QStatusBar>
#include <QMessageBox>

#include "app/ThemeManager.h"
#include "app/LanguageManager.h"

SettingsPage::SettingsPage(QWidget* parent)
    : QWidget(parent)
{
    setupUI();
    loadSettings();
}

void SettingsPage::setupUI()
{
    QVBoxLayout* mainLayout = new QVBoxLayout(this);
    mainLayout->setContentsMargins(24, 24, 24, 24);
    mainLayout->setSpacing(16);

    // ========== Section 1: Appearance ==========
    QGroupBox* appearanceGroup = new QGroupBox(tr("Appearance") + " / " + tr("\u5916\u89c2"), this);
    QFormLayout* appearanceLayout = new QFormLayout(appearanceGroup);

    m_themeCombo = new QComboBox(this);
    m_themeCombo->addItems({"Dark", "Light", "Industrial", "High Contrast"});
    appearanceLayout->addRow(tr("Theme") + " / " + tr("\u4e3b\u9898"), m_themeCombo);

    m_languageCombo = new QComboBox(this);
    m_languageCombo->addItems({QString::fromUtf8("\u4e2d\u6587"), QStringLiteral("English")});
    appearanceLayout->addRow(tr("Language") + " / " + tr("\u8bed\u8a00"), m_languageCombo);

    mainLayout->addWidget(appearanceGroup);

    // ========== Section 2: Database ==========
    QGroupBox* databaseGroup = new QGroupBox(tr("Database") + " / " + tr("\u6570\u636e\u5e93"), this);
    QFormLayout* databaseLayout = new QFormLayout(databaseGroup);

    // Local SQLite path
    m_localDbPathEdit = new QLineEdit(this);
    QPushButton* browseDbBtn = new QPushButton(tr("Browse"), this);
    QHBoxLayout* dbPathLayout = new QHBoxLayout();
    dbPathLayout->setContentsMargins(0, 0, 0, 0);
    dbPathLayout->addWidget(m_localDbPathEdit);
    dbPathLayout->addWidget(browseDbBtn);
    databaseLayout->addRow(tr("Local Database Path"), dbPathLayout);

    // Remote database type
    m_remoteDbTypeCombo = new QComboBox(this);
    m_remoteDbTypeCombo->addItems({"MySQL", "PostgreSQL"});
    databaseLayout->addRow(tr("Remote Database Type"), m_remoteDbTypeCombo);

    // Remote host
    m_remoteHostEdit = new QLineEdit(this);
    databaseLayout->addRow(tr("Remote Host"), m_remoteHostEdit);

    // Remote port
    m_remotePortSpin = new QSpinBox(this);
    m_remotePortSpin->setRange(1, 65535);
    m_remotePortSpin->setValue(3306);
    databaseLayout->addRow(tr("Remote Port"), m_remotePortSpin);

    // Remote database name
    m_remoteDbNameEdit = new QLineEdit(this);
    databaseLayout->addRow(tr("Database Name"), m_remoteDbNameEdit);

    // Remote username
    m_remoteUserEdit = new QLineEdit(this);
    databaseLayout->addRow(tr("Username"), m_remoteUserEdit);

    // Remote password
    m_remotePasswordEdit = new QLineEdit(this);
    m_remotePasswordEdit->setEchoMode(QLineEdit::Password);
    databaseLayout->addRow(tr("Password"), m_remotePasswordEdit);

    mainLayout->addWidget(databaseGroup);

    // ========== Section 3: Data Retention ==========
    QGroupBox* retentionGroup = new QGroupBox(tr("Data Retention") + " / " + tr("\u6570\u636e\u4fdd\u7559"), this);
    QFormLayout* retentionLayout = new QFormLayout(retentionGroup);

    m_retentionDaysSpin = new QSpinBox(this);
    m_retentionDaysSpin->setRange(1, 365);
    m_retentionDaysSpin->setValue(30);
    retentionLayout->addRow(tr("Local Data Retention (days)"), m_retentionDaysSpin);

    m_syncIntervalSpin = new QSpinBox(this);
    m_syncIntervalSpin->setRange(1, 1440);
    m_syncIntervalSpin->setValue(60);
    retentionLayout->addRow(tr("Sync Interval (minutes)"), m_syncIntervalSpin);

    mainLayout->addWidget(retentionGroup);

    // ========== Bottom Buttons ==========
    mainLayout->addStretch();

    QHBoxLayout* buttonLayout = new QHBoxLayout();
    buttonLayout->setSpacing(12);

    QPushButton* saveBtn = new QPushButton(tr("Save"), this);
    QPushButton* resetBtn = new QPushButton(tr("Reset"), this);

    buttonLayout->addWidget(saveBtn);
    buttonLayout->addWidget(resetBtn);

    mainLayout->addLayout(buttonLayout);

    // ========== Signal Connections ==========

    // Theme: immediately apply on change
    connect(m_themeCombo, &QComboBox::currentIndexChanged, this, [this](int index) {
        auto theme = static_cast<ThemeManager::Theme>(index);
        ThemeManager::instance().applyTheme(theme);
    });

    // Language: immediately apply on change
    connect(m_languageCombo, &QComboBox::currentIndexChanged, this, [this](int index) {
        const auto& languages = LanguageManager::instance().availableLanguages();
        if (index >= 0 && index < languages.size()) {
            LanguageManager::instance().switchLanguage(languages[index].locale);
        }
    });

    // Remote database type: adjust default port
    connect(m_remoteDbTypeCombo, &QComboBox::currentIndexChanged, this, [this](int index) {
        if (index == 0) { // MySQL
            m_remotePortSpin->setValue(3306);
        } else if (index == 1) { // PostgreSQL
            m_remotePortSpin->setValue(5432);
        }
    });

    // Browse button for local database path
    connect(browseDbBtn, &QPushButton::clicked, this, [this]() {
        QString path = QFileDialog::getOpenFileName(
            this,
            tr("Select Database File"),
            QString(),
            tr("SQLite Database (*.db *.sqlite *.sqlite3);;All Files (*)")
        );
        if (!path.isEmpty()) {
            m_localDbPathEdit->setText(path);
        }
    });

    // Save button
    connect(saveBtn, &QPushButton::clicked, this, [this]() {
        saveSettings();
        // Show success message in status bar
        if (auto* mainWindow = window()) {
            if (auto* statusBar = mainWindow->findChild<QStatusBar*>()) {
                statusBar->showMessage(tr("Settings saved successfully"), 3000);
            }
        }
    });

    // Reset button
    connect(resetBtn, &QPushButton::clicked, this, [this]() {
        resetSettings();
    });
}

void SettingsPage::loadSettings()
{
    QSettings settings;

    // Appearance
    settings.beginGroup("Appearance");
    int themeIndex = settings.value("theme", 0).toInt();
    m_themeCombo->setCurrentIndex(themeIndex);

    QString locale = settings.value("language", "zh_CN").toString();
    const auto& languages = LanguageManager::instance().availableLanguages();
    for (int i = 0; i < languages.size(); ++i) {
        if (languages[i].locale == locale) {
            m_languageCombo->setCurrentIndex(i);
            break;
        }
    }
    settings.endGroup();

    // Database
    settings.beginGroup("Database");
    m_localDbPathEdit->setText(settings.value("localDbPath", QString()).toString());

    QString dbType = settings.value("remoteDbType", "MySQL").toString();
    int dbTypeIndex = m_remoteDbTypeCombo->findText(dbType);
    if (dbTypeIndex >= 0) {
        m_remoteDbTypeCombo->setCurrentIndex(dbTypeIndex);
    }

    m_remoteHostEdit->setText(settings.value("remoteHost", QString()).toString());
    m_remotePortSpin->setValue(settings.value("remotePort", 3306).toInt());
    m_remoteDbNameEdit->setText(settings.value("remoteDbName", QString()).toString());
    m_remoteUserEdit->setText(settings.value("remoteUser", QString()).toString());
    m_remotePasswordEdit->setText(settings.value("remotePassword", QString()).toString());
    settings.endGroup();

    // Data Retention
    settings.beginGroup("DataRetention");
    m_retentionDaysSpin->setValue(settings.value("retentionDays", 30).toInt());
    m_syncIntervalSpin->setValue(settings.value("syncInterval", 60).toInt());
    settings.endGroup();
}

void SettingsPage::saveSettings()
{
    QSettings settings;

    // Database
    settings.beginGroup("Database");
    settings.setValue("localDbPath", m_localDbPathEdit->text());
    settings.setValue("remoteDbType", m_remoteDbTypeCombo->currentText());
    settings.setValue("remoteHost", m_remoteHostEdit->text());
    settings.setValue("remotePort", m_remotePortSpin->value());
    settings.setValue("remoteDbName", m_remoteDbNameEdit->text());
    settings.setValue("remoteUser", m_remoteUserEdit->text());
    settings.setValue("remotePassword", m_remotePasswordEdit->text());
    settings.endGroup();

    // Data Retention
    settings.beginGroup("DataRetention");
    settings.setValue("retentionDays", m_retentionDaysSpin->value());
    settings.setValue("syncInterval", m_syncIntervalSpin->value());
    settings.endGroup();
}

void SettingsPage::resetSettings()
{
    // Appearance defaults
    m_themeCombo->setCurrentIndex(0); // Dark
    m_languageCombo->setCurrentIndex(0); // Chinese

    // Database defaults
    m_localDbPathEdit->clear();
    m_remoteDbTypeCombo->setCurrentIndex(0); // MySQL
    m_remoteHostEdit->clear();
    m_remotePortSpin->setValue(3306);
    m_remoteDbNameEdit->clear();
    m_remoteUserEdit->clear();
    m_remotePasswordEdit->clear();

    // Data Retention defaults
    m_retentionDaysSpin->setValue(30);
    m_syncIntervalSpin->setValue(60);
}
