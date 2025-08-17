from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QFileDialog, QDateEdit, QHBoxLayout, QTableWidget, QTableWidgetItem
from PyQt6.QtCore import QDate
import pandas as pd
from db_manager import DENOM_MAPPING

class StatWindow(QWidget):
    def __init__(self, db):
        super().__init__()
        self.db = db
        self.setWindowTitle("Statistics")
        self.resize(1000, 700)

        layout = QVBoxLayout(self)

        # Date pickers
        date_layout = QHBoxLayout()
        self.start_date = QDateEdit(calendarPopup=True)
        self.start_date.setDate(QDate.currentDate())
        self.end_date = QDateEdit(calendarPopup=True)
        self.end_date.setDate(QDate.currentDate())
        date_layout.addWidget(QLabel("From:"))
        date_layout.addWidget(self.start_date)
        date_layout.addWidget(QLabel("To:"))
        date_layout.addWidget(self.end_date)
        layout.addLayout(date_layout)

        # Buttons
        self.export_btn = QPushButton("Export Excel")
        self.export_btn.clicked.connect(self.export_excel)
        layout.addWidget(self.export_btn)

        # Tables
        self.summary_table = QTableWidget()
        layout.addWidget(QLabel("Daily Cash Summary"))
        layout.addWidget(self.summary_table)

        self.cash_count_table = QTableWidget()
        layout.addWidget(QLabel("Daily Cash Count"))
        layout.addWidget(self.cash_count_table)

    def export_excel(self):
        file, _ = QFileDialog.getSaveFileName(self, "Save Excel", "", "Excel Files (*.xlsx)")
        if not file: return

        # Fetch data from db
        rows_summary = self.db.fetchall("SELECT * FROM daily_cash WHERE date BETWEEN ? AND ?", (self.start_date.date().toString("yyyy-MM-dd"), self.end_date.date().toString("yyyy-MM-dd")))
        rows_count = self.db.fetchall("SELECT * FROM daily_cash_count WHERE date BETWEEN ? AND ?", (self.start_date.date().toString("yyyy-MM-dd"), self.end_date.date().toString("yyyy-MM-dd")))

        df1 = pd.DataFrame(rows_summary, columns=[d[1] for d in self.db.cursor.execute("PRAGMA table_info(daily_cash)")])
        df2 = pd.DataFrame(rows_count, columns=[d[1] for d in self.db.cursor.execute("PRAGMA table_info(daily_cash_count)")])

        with pd.ExcelWriter(file) as writer:
            df1.to_excel(writer, sheet_name="DailyCash", index=False)
            df2.to_excel(writer, sheet_name="CashCount", index=False)
