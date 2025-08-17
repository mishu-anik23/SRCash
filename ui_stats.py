from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QDateEdit, QTableWidget, QTableWidgetItem, QMessageBox
)
from PyQt6.QtCore import QDate
import xlsxwriter
import os


class StatWindow(QWidget):
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.setWindowTitle("Statistics & Export")
        self.resize(1000, 700)

        layout = QVBoxLayout(self)

        # ---- Date pickers + buttons ----
        control_layout = QHBoxLayout()
        control_layout.addWidget(QLabel("From:"))
        self.from_date = QDateEdit(QDate.currentDate())
        self.from_date.setCalendarPopup(True)
        control_layout.addWidget(self.from_date)

        control_layout.addWidget(QLabel("To:"))
        self.to_date = QDateEdit(QDate.currentDate())
        self.to_date.setCalendarPopup(True)
        control_layout.addWidget(self.to_date)

        self.load_button = QPushButton("Load Data")
        self.load_button.clicked.connect(self.load_data)
        control_layout.addWidget(self.load_button)

        self.export_button = QPushButton("Export to Excel")
        self.export_button.clicked.connect(self.export_excel)
        control_layout.addWidget(self.export_button)

        layout.addLayout(control_layout)

        # ---- Daily Cash Count Table ----
        self.dcc_table = QTableWidget()
        layout.addWidget(QLabel("Daily Cash Count"))
        layout.addWidget(self.dcc_table)

        # ---- Cash Summary Table ----
        self.summary_table = QTableWidget()
        layout.addWidget(QLabel("Cash Summary"))
        layout.addWidget(self.summary_table)

    # ---- Load data for selected date range ----
    def load_data(self):
        from_date = self.from_date.date().toString("yyyy-MM-dd")
        to_date = self.to_date.date().toString("yyyy-MM-dd")

        # 1. Daily Cash Count
        dcc_rows = self.db.fetchall("""
            SELECT * FROM daily_cash_count 
            WHERE date BETWEEN ? AND ?
            ORDER BY date
        """, (from_date, to_date))

        if dcc_rows:
            headers = [col[0] for col in self.db.cursor.description]
            self.dcc_table.setColumnCount(len(headers))
            self.dcc_table.setHorizontalHeaderLabels(headers)
            self.dcc_table.setRowCount(len(dcc_rows))
            for r, row in enumerate(dcc_rows):
                for c, val in enumerate(row):
                    self.dcc_table.setItem(r, c, QTableWidgetItem(str(val)))
        else:
            self.dcc_table.setRowCount(0)
            QMessageBox.information(self, "No Data", "No Daily Cash Count found.")

        # 2. Cash Summary
        summary_rows = self.db.fetchall("""
            SELECT * FROM daily_cash
            WHERE date BETWEEN ? AND ?
            ORDER BY date
        """, (from_date, to_date))

        if summary_rows:
            headers = [col[0] for col in self.db.cursor.description]
            self.summary_table.setColumnCount(len(headers))
            self.summary_table.setHorizontalHeaderLabels(headers)
            self.summary_table.setRowCount(len(summary_rows))
            for r, row in enumerate(summary_rows):
                for c, val in enumerate(row):
                    self.summary_table.setItem(r, c, QTableWidgetItem(str(val)))
        else:
            self.summary_table.setRowCount(0)
            QMessageBox.information(self, "No Data", "No Cash Summary found.")

    # ---- Export both tables into Excel ----
    def export_excel(self):
        from_date = self.from_date.date().toString("yyyy-MM-dd")
        to_date = self.to_date.date().toString("yyyy-MM-dd")
        filename = f"cash_stats_{from_date}_to_{to_date}.xlsx"

        workbook = xlsxwriter.Workbook(filename)

        # Daily Cash Count sheet
        ws1 = workbook.add_worksheet("DailyCashCount")
        for col in range(self.dcc_table.columnCount()):
            ws1.write(0, col, self.dcc_table.horizontalHeaderItem(col).text())
        for row in range(self.dcc_table.rowCount()):
            for col in range(self.dcc_table.columnCount()):
                item = self.dcc_table.item(row, col)
                if item:
                    ws1.write(row + 1, col, item.text())

        # Cash Summary sheet
        ws2 = workbook.add_worksheet("CashSummary")
        for col in range(self.summary_table.columnCount()):
            ws2.write(0, col, self.summary_table.horizontalHeaderItem(col).text())
        for row in range(self.summary_table.rowCount()):
            for col in range(self.summary_table.columnCount()):
                item = self.summary_table.item(row, col)
                if item:
                    ws2.write(row + 1, col, item.text())

        workbook.close()

        QMessageBox.information(self, "Exported", f"Excel file saved as {os.path.abspath(filename)}")
