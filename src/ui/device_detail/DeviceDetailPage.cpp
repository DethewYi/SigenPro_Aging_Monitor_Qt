#include "DeviceDetailPage.h"
#include "RealtimeDataPanel.h"
#include "CurveChartWidget.h"
#include "TestControlPanel.h"
#include "core/common/DeviceData.h"

#include <QSplitter>
#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QPushButton>
#include <QLabel>
#include <QFont>

DeviceDetailPage::DeviceDetailPage(QWidget* parent)
    : QWidget(parent)
{
    setupUI();
}

void DeviceDetailPage::setupUI()
{
    QVBoxLayout* mainLayout = new QVBoxLayout(this);
    mainLayout->setContentsMargins(8, 8, 8, 8);
    mainLayout->setSpacing(8);

    // Top bar: Back button + device info
    QHBoxLayout* topBar = new QHBoxLayout();

    m_backBtn = new QPushButton(tr("< Back"), this);
    m_backBtn->setFixedWidth(80);
    m_backBtn->setCursor(Qt::PointingHandCursor);
    topBar->addWidget(m_backBtn);

    m_deviceTitleLabel = new QLabel(tr("Device Detail"), this);
    QFont titleFont;
    titleFont.setPointSize(16);
    titleFont.setBold(true);
    m_deviceTitleLabel->setFont(titleFont);
    topBar->addWidget(m_deviceTitleLabel);
    topBar->addStretch();

    mainLayout->addLayout(topBar);

    // Splitter: left data panel, right chart
    QSplitter* splitter = new QSplitter(Qt::Horizontal, this);

    m_dataPanel = new RealtimeDataPanel(splitter);
    splitter->addWidget(m_dataPanel);

    m_chartWidget = new CurveChartWidget(splitter);
    splitter->addWidget(m_chartWidget);

    // Set initial sizes: 30% left, 70% right
    splitter->setSizes({300, 700});
    splitter->setStretchFactor(0, 3);
    splitter->setStretchFactor(1, 7);

    mainLayout->addWidget(splitter, 1);

    // Bottom: test control panel
    m_controlPanel = new TestControlPanel(this);
    mainLayout->addWidget(m_controlPanel);

    // Connect back button
    connect(m_backBtn, &QPushButton::clicked, this, &DeviceDetailPage::backRequested);

    // Setup default chart curves with distinct colors for common parameters
    m_chartWidget->addCurve(tr("Voltage"), QColor("#89b4fa"));    // blue
    m_chartWidget->addCurve(tr("Current"), QColor("#f38ba8"));    // red
    m_chartWidget->addCurve(tr("Temperature"), QColor("#a6e3a1")); // green
    m_chartWidget->addCurve(tr("Power"), QColor("#f9e2af"));       // yellow
}

void DeviceDetailPage::setDevice(int deviceId)
{
    m_deviceId = deviceId;
    if (deviceId >= 0) {
        m_deviceTitleLabel->setText(tr("Device #%1 Detail").arg(deviceId));
    } else {
        m_deviceTitleLabel->setText(tr("Device Detail"));
    }

    // Clear previous data when switching devices
    m_chartWidget->clearData();
    m_dataPanel->clearAll();
}

int DeviceDetailPage::currentDeviceId() const
{
    return m_deviceId;
}

void DeviceDetailPage::onDeviceDataReceived(const DeviceData& data)
{
    // Only process data for the currently selected device
    if (data.deviceId != m_deviceId) {
        return;
    }

    // Setup parameters on first data reception
    if (m_dataPanel->parameterCount() == 0 && !data.parameters.isEmpty()) {
        m_dataPanel->setupParameters(data.parameters.keys());
    }

    // Update each parameter value
    double timestamp = data.timestamp.toSecsSinceEpoch();
    for (auto it = data.parameters.begin(); it != data.parameters.end(); ++it) {
        m_dataPanel->updateParameter(it.key(), it.value());
        m_chartWidget->appendData(it.key(), timestamp, it.value());
    }
}
