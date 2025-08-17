import sys
import os
from datetime import datetime
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTableWidget, QTableWidgetItem, QScrollArea, QLabel,
    QDateEdit, QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QPixmap, QIcon

from db_manager import DBManager, DENOM_MAPPING

# Image folder — adjust to your setup
IMG_DIR = "img/euro"

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.db = DBManager()
        self.setWindowTitle("E-Cash Management - Supermarket")
        self.resize(1600, 900)

        self.selected_date = datetime.today().strftime("%Y-%m-%d")
        self.init_ui()

    def init_ui(self):
        main_layout = QHBoxLayout()
        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

        # LEFT PANEL
        left_panel = QVBoxLayout()

        # Date picker
        date_picker = QDateEdit()
        date_picker.setDate(QDate.currentDate())
        date_picker.setCalendarPopup(True)
        date_picker.dateChanged.connect(self.on_date_changed)
        left_panel.addWidget(QLabel("Select Date:"))
        left_panel.addWidget(date_picker)

        # Load Old Value Button
        btn_load = QPushButton("Load Old Value")
        btn_load.clicked.connect(self.load_old_value)
        left_panel.addWidget(btn_load)

        # Scroll area for denominations
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_widget = QWidget()
        denom_layout = QHBoxLayout()
        denom_layout.setSpacing(10)

        col1 = QVBoxLayout()
        col2 = QVBoxLayout()

        for i, (display_name, (qty_col, total_col, value)) in enumerate(DENOM_MAPPING.items()):
            img_path = os.path.join(IMG_DIR, f"{display_name.replace('€','euro').replace('c','cent')}.png")
            #print(img_path)
            btn = QPushButton()
            btn.setFixedSize(100, 60)
            if os.path.exists(img_path):
                pixmap = QPixmap(img_path).scaled(120, 60, Qt.AspectRatioMode.KeepAspectRatio)
                btn.setIcon(QIcon(pixmap))
                btn.setIconSize(pixmap.size())
            else:
                btn.setText(display_name)
            btn.clicked.connect(lambda checked, dn=display_name: self.open_quantity_dialog(dn))
            if i % 2 == 0:
                col1.addWidget(btn)
            else:
                col2.addWidget(btn)

        denom_layout.addLayout(col1)
        denom_layout.addLayout(col2)

        scroll_widget.setLayout(denom_layout)
        scroll_area.setWidget(scroll_widget)
        left_panel.addWidget(scroll_area)

        # Show Stats Button
        btn_stats = QPushButton("Show Stats")
        btn_stats.clicked.connect(self.show_stats_window)
        left_panel.addWidget(btn_stats)

        # Add left panel to main layout
        main_layout.addLayout(left_panel, 1)

        # RIGHT PANEL
        right_panel = QVBoxLayout()

        # Daily Expenses Table
        self.expenses_table = self.create_table(["Invoice", "Amount", "Status"])
        right_panel.addWidget(QLabel("Daily Expenses"))
        right_panel.addWidget(self.expenses_table)
        self.add_table_buttons(right_panel, self.expenses_table, self.save_expenses, self.delete_selected_row)

        # Old Invoice Table
        self.old_invoice_table = self.create_table(["Date", "Invoice", "Amount"])
        right_panel.addWidget(QLabel("Old Invoice Payment"))
        right_panel.addWidget(self.old_invoice_table)
        self.add_table_buttons(right_panel, self.old_invoice_table, self.save_old_invoice, self.delete_selected_row)

        # Bio Cash Table
        self.bio_cash_table = self.create_table(["Purpose", "Amount", "Vendor", "Sold By"])
        right_panel.addWidget(QLabel("Bio Cash Update"))
        right_panel.addWidget(self.bio_cash_table)
        self.add_table_buttons(right_panel, self.bio_cash_table, self.save_bio_cash, self.delete_selected_row)

        main_layout.addLayout(right_panel, 3)

    def create_table(self, headers):
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.horizontalHeader().setStretchLastSection(True)
        table.verticalHeader().setVisible(False)
        return table

    def add_table_buttons(self, layout, table, save_func, cancel_func):
        btn_layout = QHBoxLayout()
        btn_save = QPushButton("Save")
        btn_save.clicked.connect(save_func)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(lambda: cancel_func(table))
        btn_add = QPushButton("+")
        btn_add.clicked.connect(lambda: table.insertRow(table.rowCount()))
        btn_layout.addWidget(btn_save)
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_add)
        layout.addLayout(btn_layout)

    def open_quantity_dialog(self, denom_display: str):
        """
        Open a safe quantity input dialog for a denomination.
        Validates input, updates DB, and recalculates total cash in real time.
        """
        from PyQt6.QtWidgets import QInputDialog, QMessageBox

        # Make sure denomination is mapped
        if denom_display not in DENOM_MAPPING:
            QMessageBox.critical(self, "Error", f"Unknown denomination: {denom_display}")
            return

        qty_col, total_col, value = DENOM_MAPPING[denom_display]

        # Ask for quantity
        qty, ok = QInputDialog.getInt(
            self,
            "Enter Quantity",
            f"Quantity for {denom_display}:",
            0,  # default
            0,  # min
            10000  # max
        )

        if not ok:
            return  # user cancelled

        try:
            # Calculate subtotal
            subtotal = qty * value

            # Save into DB
            #self.db.cursor.execute(
             #   f"""
              #  INSERT INTO daily_cash_count (date, {qty_col}, {total_col}, total_cash)
               # VALUES (?, ?, ?, ?)
                #ON CONFLICT(date) DO UPDATE SET
                 # {qty_col} = excluded.{qty_col},
                  #{total_col} = excluded.{total_col},
                  #total_cash = (
                   # COALESCE(daily_cash_count.total_cash,0)
                    #- COALESCE(daily_cash_count.{total_col},0)
                    #+ excluded.{total_col}
                 # )
                #""",
                #(self.selected_date, qty, subtotal, subtotal)
            #)
            self.db.upsert_denomination(self.selected_date, denom_display, qty)

            self.db.conn.commit()

            # Inform user
            QMessageBox.information(
                self,
                "Saved",
                f"{denom_display}: {qty} × {value} = {subtotal:.2f} saved for {self.selected_date}"
            )

        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"Failed to save {denom_display}:\n{e}")

    def on_date_changed(self, qdate):
        self.selected_date = qdate.toString("yyyy-MM-dd")

    def load_old_value(self):
        data = self.db.fetch_daily_cash_count(self.selected_date)
        if not data:
            QMessageBox.warning(self, "Not Found", "No records found for selected date.")
            return
        QMessageBox.information(self, "Data Loaded", f"Loaded saved data for {self.selected_date}")

    def delete_selected_row(self, table):
        selected = table.currentRow()
        if selected >= 0:
            table.removeRow(selected)

    def save_expenses(self):
        for row in range(self.expenses_table.rowCount()):
            inv_item = self.expenses_table.item(row, 0)
            amt_item = self.expenses_table.item(row, 1)
            status_item = self.expenses_table.item(row, 2)
            if inv_item and amt_item and status_item:
                try:
                    amount = float(amt_item.text())
                except (ValueError, AttributeError):
                    continue
                self.db.cursor.execute(
                    "INSERT INTO daily_expenses (date, invoice, amount, status) VALUES (?, ?, ?, ?)",
                    (self.selected_date, inv_item.text(), amount, status_item.text())
                )
        self.db.conn.commit()

    def save_old_invoice(self):
        for row in range(self.old_invoice_table.rowCount()):
            date_item = self.old_invoice_table.item(row, 0)
            inv_item = self.old_invoice_table.item(row, 1)
            amt_item = self.old_invoice_table.item(row, 2)
            if date_item and inv_item and amt_item:
                try:
                    amount = float(amt_item.text())
                except (ValueError, AttributeError):
                    continue
                self.db.cursor.execute(
                    "INSERT INTO old_invoice (date, invoice, amount) VALUES (?, ?, ?)",
                    (date_item.text(), inv_item.text(), amount)
                )
        self.db.conn.commit()

    def save_bio_cash(self):
        for row in range(self.bio_cash_table.rowCount()):
            purpose_item = self.bio_cash_table.item(row, 0)
            amt_item = self.bio_cash_table.item(row, 1)
            vendor_item = self.bio_cash_table.item(row, 2)
            sold_by_item = self.bio_cash_table.item(row, 3)
            if purpose_item and amt_item:
                try:
                    amount = float(amt_item.text())
                except (ValueError, AttributeError):
                    continue
                self.db.cursor.execute(
                    "INSERT INTO bio_cash (date, purpose, amount, vendor, sold_by) VALUES (?, ?, ?, ?, ?)",
                    (self.selected_date, purpose_item.text(), amount,
                     vendor_item.text() if vendor_item else "",
                     sold_by_item.text() if sold_by_item else "")
                )
        self.db.conn.commit()

    def show_stats_window(self):
        from ui_stats import StatsWindow
        self.stats_window = StatsWindow()
        self.stats_window.show()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
