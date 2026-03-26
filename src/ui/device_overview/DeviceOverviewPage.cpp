#include "DeviceOverviewPage.h"
#include "StatsBarWidget.h"
#include "DeviceCardWidget.h"

#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QGridLayout>
#include <QComboBox>
#include <QLineEdit>
#include <QScrollArea>
#include <QLabel>
#include <QEvent>

static constexpr int GRID_MIN_COLUMN_WIDTH = 280;

DeviceOverviewPage::DeviceOverviewPage(QWidget* parent)
    : QWidget(parent)
{
    setupUI();
}

void DeviceOverviewPage::setupUI()
{
    QVBoxLayout* mainLayout = new QVBoxLayout(this);
    mainLayout->setContentsMargins(24, 16, 24, 16);
    mainLayout->setSpacing(16);

    // ========== Stats Bar ==========
    m_statsBar = new StatsBarWidget(this);
    mainLayout->addWidget(m_statsBar);

    // ========== Filter Bar ==========
    QHBoxLayout* filterLayout = new QHBoxLayout();
    filterLayout->setSpacing(12);

    // Status filter
    QLabel* statusFilterLabel = new QLabel(tr("Status:"), this);
    statusFilterLabel->setStyleSheet(QStringLiteral("color: #cdd6f4;"));
    filterLayout->addWidget(statusFilterLabel);

    m_statusFilter = new QComboBox(this);
    m_statusFilter->setMinimumWidth(120);
    m_statusFilter->addItem(tr("All"), QStringLiteral("all"));
    m_statusFilter->addItem(tr("Testing"), QStringLiteral("testing"));
    m_statusFilter->addItem(tr("Idle"), QStringLiteral("idle"));
    m_statusFilter->addItem(tr("Offline"), QStringLiteral("offline"));
    m_statusFilter->addItem(tr("Alarm"), QStringLiteral("alarm"));
    m_statusFilter->addItem(tr("Completed"), QStringLiteral("completed"));
    m_statusFilter->addItem(tr("Fault"), QStringLiteral("fault"));
    filterLayout->addWidget(m_statusFilter);

    filterLayout->addSpacing(16);

    // Model filter
    QLabel* modelFilterLabel = new QLabel(tr("Model:"), this);
    modelFilterLabel->setStyleSheet(QStringLiteral("color: #cdd6f4;"));
    filterLayout->addWidget(modelFilterLabel);

    m_modelFilter = new QComboBox(this);
    m_modelFilter->setMinimumWidth(120);
    m_modelFilter->addItem(tr("All Models"), QStringLiteral("all"));
    m_modelFilter->setEditable(false);
    filterLayout->addWidget(m_modelFilter);

    filterLayout->addSpacing(16);

    // Search
    QLabel* searchLabel = new QLabel(tr("Search:"), this);
    searchLabel->setStyleSheet(QStringLiteral("color: #cdd6f4;"));
    filterLayout->addWidget(searchLabel);

    m_searchEdit = new QLineEdit(this);
    m_searchEdit->setPlaceholderText(tr("Search by name or SN..."));
    m_searchEdit->setMinimumWidth(200);
    m_searchEdit->setMaximumWidth(300);
    filterLayout->addWidget(m_searchEdit);

    filterLayout->addStretch();

    mainLayout->addLayout(filterLayout);

    // ========== Device Grid in Scroll Area ==========
    m_scrollArea = new QScrollArea(this);
    m_scrollArea->setWidgetResizable(true);
    m_scrollArea->setHorizontalScrollBarPolicy(Qt::ScrollBarAsNeeded);
    m_scrollArea->setVerticalScrollBarPolicy(Qt::ScrollBarAsNeeded);
    m_scrollArea->setStyleSheet(QStringLiteral(
        "QScrollArea {"
        "  background-color: transparent;"
        "  border: none;"
        "}"
        "QScrollBar:vertical {"
        "  background-color: #1e1e2e;"
        "  width: 10px;"
        "  border-radius: 5px;"
        "}"
        "QScrollBar::handle:vertical {"
        "  background-color: #45475a;"
        "  border-radius: 5px;"
        "  min-height: 30px;"
        "}"
        "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {"
        "  height: 0px;"
        "}"
    ));

    m_gridWidget = new QWidget(m_scrollArea);
    m_gridWidget->setStyleSheet(QStringLiteral("background-color: transparent;"));
    m_gridLayout = new QGridLayout(m_gridWidget);
    m_gridLayout->setContentsMargins(0, 0, 0, 0);
    m_gridLayout->setSpacing(12);
    m_gridLayout->setAlignment(Qt::AlignTop | Qt::AlignLeft);

    m_scrollArea->setWidget(m_gridWidget);
    mainLayout->addWidget(m_scrollArea);

    // ========== Signal Connections ==========
    connect(m_statusFilter, &QComboBox::currentIndexChanged,
            this, &DeviceOverviewPage::onFilterChanged);
    connect(m_modelFilter, &QComboBox::currentIndexChanged,
            this, &DeviceOverviewPage::onFilterChanged);
    connect(m_searchEdit, &QLineEdit::textChanged,
            this, &DeviceOverviewPage::onFilterChanged);

    // Install event filter on scroll area viewport to handle resize
    if (m_scrollArea->viewport()) {
        m_scrollArea->viewport()->installEventFilter(this);
    }
}

void DeviceOverviewPage::refreshDevices()
{
    rebuildGrid();
}

void DeviceOverviewPage::addOrUpdateDevice(int deviceId, const QString& name,
                                           const QString& model, const QString& sn,
                                           DeviceStatus status)
{
    DeviceCardWidget* card = nullptr;
    auto it = m_deviceCards.find(deviceId);
    if (it != m_deviceCards.end()) {
        card = it.value();
    } else {
        card = new DeviceCardWidget(deviceId, this);
        connect(card, &DeviceCardWidget::clicked, this, [this](int id) {
            emit deviceClicked(id);
        });
        m_deviceCards[deviceId] = card;
    }

    card->setDeviceInfo(name, model, sn);
    card->setStatus(status);

    // Update model filter combo if model is not yet listed
    if (!model.isEmpty() && m_modelFilter->findText(model) < 0) {
        m_modelFilter->addItem(model, model);
    }

    rebuildGrid();
}

void DeviceOverviewPage::removeDevice(int deviceId)
{
    auto it = m_deviceCards.find(deviceId);
    if (it != m_deviceCards.end()) {
        DeviceCardWidget* card = it.value();
        m_gridLayout->removeWidget(card);
        delete card;
        m_deviceCards.erase(it);
    }
    rebuildGrid();
}

void DeviceOverviewPage::onFilterChanged()
{
    m_currentStatusFilter = m_statusFilter->currentData().toString();
    m_currentModelFilter = m_modelFilter->currentData().toString();
    m_currentSearch = m_searchEdit->text().trimmed().toLower();
    rebuildGrid();
}

bool DeviceOverviewPage::shouldShowDevice(int deviceId) const
{
    auto it = m_deviceCards.find(deviceId);
    if (it == m_deviceCards.end()) {
        return false;
    }

    DeviceCardWidget* card = it.value();

    // Status filter
    if (m_currentStatusFilter != QLatin1String("all")) {
        QString cardStatus = card->property("status").toString();
        if (cardStatus != m_currentStatusFilter) {
            return false;
        }
    }

    // Model filter
    if (m_currentModelFilter != QLatin1String("all")) {
        QString modelText = card->property("modelFilter").toString();
        if (modelText != m_currentModelFilter) {
            return false;
        }
    }

    // Search filter
    if (!m_currentSearch.isEmpty()) {
        QString cardText = card->property("searchText").toString().toLower();
        if (!cardText.contains(m_currentSearch)) {
            return false;
        }
    }

    return true;
}

void DeviceOverviewPage::rebuildGrid()
{
    // Remove all widgets from layout
    while (m_gridLayout->count() > 0) {
        QLayoutItem* item = m_gridLayout->takeAt(0);
        item->widget()->hide();
    }

    // Calculate column count based on available width
    int availableWidth = m_scrollArea->viewport() ? m_scrollArea->viewport()->width() : 800;
    int columns = qMax(1, availableWidth / (GRID_MIN_COLUMN_WIDTH + 12));

    int row = 0;
    int col = 0;

    for (auto it = m_deviceCards.begin(); it != m_deviceCards.end(); ++it) {
        int deviceId = it.key();
        DeviceCardWidget* card = it.value();

        if (!shouldShowDevice(deviceId)) {
            card->hide();
            continue;
        }

        card->show();
        m_gridLayout->addWidget(card, row, col);

        ++col;
        if (col >= columns) {
            col = 0;
            ++row;
        }
    }

    // Set column stretch so cards distribute evenly
    for (int c = 0; c < columns; ++c) {
        m_gridLayout->setColumnStretch(c, 1);
    }
}

bool DeviceOverviewPage::eventFilter(QObject* watched, QEvent* event)
{
    if (watched == m_scrollArea->viewport() && event->type() == QEvent::Resize) {
        rebuildGrid();
    }
    return QWidget::eventFilter(watched, event);
}
