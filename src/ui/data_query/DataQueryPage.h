#pragma once
#include <QWidget>

class QComboBox;
class QDateEdit;
class QTableWidget;
class QPushButton;

class DataQueryPage : public QWidget {
    Q_OBJECT
public:
    explicit DataQueryPage(QWidget* parent = nullptr);

signals:
    void navigateToDeviceDetail(int deviceId);
    void exportPdfRequested(int recordId);
    void exportExcelRequested(int recordId);

private slots:
    void onQuery();
    void onExportPdf();
    void onExportExcel();
    void onTableDoubleClicked(int row, int column);

private:
    void setupUI();
    void loadTestRecords();

    // Query conditions
    QComboBox* m_deviceCombo = nullptr;
    QDateEdit* m_startDate = nullptr;
    QDateEdit* m_endDate = nullptr;
    QComboBox* m_resultFilter = nullptr;
    QPushButton* m_queryBtn = nullptr;

    // Results
    QTableWidget* m_resultsTable = nullptr;
    QPushButton* m_exportPdfBtn = nullptr;
    QPushButton* m_exportExcelBtn = nullptr;
};
