import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QDateEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QFileDialog, QMessageBox
)
from PyQt6.QtCore import QDate
from openpyxl import Workbook

from db_manager import DBManager, DENOM_MAPPING


class StatsWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("E-Cash Management - Statistics & Export")
        self.resize(1200, 800)

        self.db = DBManager()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # Date range pickers
        date_layout = QHBoxLayout()
        date_layout.addWidget(QLabel("From:"))
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(QDate.currentDate())
        date_layout.addWidget(self.date_from)

        date_layout.addWidget(QLabel("To:"))
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(QDate.currentDate())
        date_layout.addWidget(self.date_to)

        btn_load = QPushButton("Load Data")
        btn_load.clicked.connect(self.load_data)
        date_layout.addWidget(btn_load)

        btn_export = QPushButton("Export to Excel")
        btn_export.clicked.connect(self.export_to_excel)
        date_layout.addWidget(btn_export)

        layout.addLayout(date_layout)

        # Table to display summary data
        self.table = QTableWidget()
        layout.addWidget(QLabel("Summary Data"))
        layout.addWidget(self.table)

    def load_data(self):
        from_date = self.date_from.date().toString("yyyy-MM-dd")
        to_date = self.date_to.date().toString("yyyy-MM-dd")

        query = """
        SELECT * FROM daily_cash
        WHERE date BETWEEN ? AND ?
        ORDER BY date
        """
        data = self.db.cursor.execute(query, (from_date, to_date)).fetchall()

        if not data:
            QMessageBox.information(self, "No Data", "No records found in this date range.")
            return

        headers = [desc[0] for desc in self.db.cursor.description]
        self.table.setRowCount(len(data))
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)

        for row_idx, row in enumerate(data):
            for col_idx, value in enumerate(row):
                self.table.setItem(row_idx, col_idx, QTableWidgetItem(str(value)))

    def export_to_excel(self):
        if self.table.rowCount() == 0:
            QMessageBox.warning(self, "No Data", "Please load data first.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Excel File", "", "Excel Files (*.xlsx)"
        )
        if not file_path:
            return

        wb = Workbook()
        ws = wb.active
        ws.title = "Summary Data"

        # Write headers
        headers = [self.table.horizontalHeaderItem(i).text() for i in range(self.table.columnCount())]
        ws.append(headers)

        # Write rows
        for row_idx in range(self.table.rowCount()):
            row_data = []
            for col_idx in range(self.table.columnCount()):
                item = self.table.item(row_idx, col_idx)
                row_data.append(item.text() if item else "")
            ws.append(row_data)

        try:
            wb.save(file_path)
            QMessageBox.information(self, "Success", f"Excel file saved at {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save Excel file:\n{e}")
