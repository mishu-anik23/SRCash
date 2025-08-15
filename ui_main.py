# This is a full corrected, safe, and complete `ui_main.py` file for your PyQt6 app with all requested tables and summary logic.
import pandas as pd

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QTableWidget, QTableWidgetItem, QLabel, QScrollArea, QDialog,
    QLineEdit, QMessageBox, QDateEdit, QAbstractItemView, QFileDialog
)
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import QSize, QDate
import sys, sqlite3, os
from datetime import datetime

class QuantityDialog(QDialog):
    def __init__(self, denomination, value, parent=None):
        super().__init__(parent)

        self.setWindowTitle(f"Enter Quantity for {denomination}")
        self.denomination = denomination
        self.value = value

        layout = QVBoxLayout()
        self.qty_input = QLineEdit()
        self.qty_input.setPlaceholderText("Enter quantity")
        layout.addWidget(self.qty_input)

        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Save")
        cancel_btn = QPushButton("Cancel")
        save_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        self.setLayout(layout)

    def get_quantity(self):
        try:
            return int(self.qty_input.text())
        except ValueError:
            return 0


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.today_cash_id = None
        self.setWindowTitle("E-Cash Supermarket")
        self.conn = sqlite3.connect("ecash.db")
        self.cursor = self.conn.cursor()
        self.setup_tables()
        self.init_ui()


    def setup_tables(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_cash_count (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                euro200_qty INTEGER, euro200_total REAL,
                euro100_qty INTEGER, euro100_total REAL,
                euro50_qty INTEGER, euro50_total REAL,
                euro20_qty INTEGER, euro20_total REAL,
                euro10_qty INTEGER, euro10_total REAL,
                euro5_qty INTEGER, euro5_total REAL,
                euro2_qty INTEGER, euro2_total REAL,
                euro1_qty INTEGER, euro1_total REAL,
                cent50_qty INTEGER, cent50_total REAL,
                cent20_qty INTEGER, cent20_total REAL,
                cent10_qty INTEGER, cent10_total REAL,
                total_cash REAL
            )
        """)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice TEXT,
                amount REAL,
                status TEXT
            )
        """)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS old_invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                invoice TEXT,
                amount REAL
            )
        """)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS bio_cash (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                purpose TEXT,
                amount REAL,
                vendor TEXT,
                sold_by TEXT
            )
        """)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_cash (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                daily_cash_count REAL,
                other_sell REAL,
                prev_day_cash REAL,
                total_cash_sell REAL,
                total_card_sell REAL,
                total_daily_sell REAL,
                next_day_cash_note REAL,
                next_day_cash_coin REAL,
                total_cash_taken REAL,
                cash_taken_by TEXT
            )
        """)
        self.conn.commit()

    def init_ui(self):
        central = QWidget()
        layout = QHBoxLayout()
        central.setLayout(layout)
        self.setCentralWidget(central)

        self.note_data = {
            "euro200": [0, 0.0], "euro100": [0, 0.0], "euro50": [0, 0.0],
            "euro20": [0, 0.0], "euro10": [0, 0.0], "euro5": [0, 0.0],
            "euro2": [0, 0.0], "euro1": [0, 0.0],
            "cent50": [0, 0.0], "cent20": [0, 0.0], "cent10": [0, 0.0],
        }

        # LEFT PANEL with scrollable image buttons
        denominations = [
            ("€200", 200, "images/euro200.jpg"),
            ("€100", 100, "images/euro100.jpg"),
            ("€50", 50, "images/euro50.jpg"),
            ("€20", 20, "images/euro20.jpg"),
            ("€10", 10, "images/euro10.jpg"),
            ("€5", 5, "images/euro5.png"),
            ("€2", 2, "images/euroCoin2.jpg"),
            ("€1", 1, "images/euroCoin1.png"),
            ("50c", 0.5, "images/euroCoin50Cent.png"),
            ("20c", 0.2, "images/euroCoin20Cent.webp"),
            ("10c", 0.1, "images/euroCoin10Cent.jpg"),
        ]
        grid_widget = QWidget()
        grid_layout = QGridLayout()
        grid_widget.setLayout(grid_layout)
        for i, (name, value, path) in enumerate(denominations):
            btn = QPushButton()
            btn.setIcon(QIcon(path))
            btn.setIconSize(QSize(100, 60))
            btn.setToolTip(name)
            btn.clicked.connect(lambda _, n=name, v=value: self.open_quantity_dialog(n, v))
            grid_layout.addWidget(btn, i // 2, i % 2)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(grid_widget)

        # 📅 Date Picker for Daily Cash Count
        self.cash_count_date = QDateEdit()
        self.cash_count_date.setCalendarPopup(True)
        self.cash_count_date.setDate(QDate.currentDate())

        left_panel = QVBoxLayout()
        left_panel.addWidget(QLabel("📅 Select Date for Cash Count"))
        left_panel.addWidget(self.cash_count_date)
        left_panel.addWidget(QLabel("<b>Daily Cash Count</b>"))
        left_panel.addWidget(scroll)


        left_wrap = QWidget()
        left_wrap.setLayout(left_panel)
        layout.addWidget(left_wrap, 1)

        # RIGHT PANEL
        self.expenses_table = QTableWidget(1, 3)
        self.expenses_table.setHorizontalHeaderLabels(["Invoice", "Amount", "Status"])
        self.old_invoice_table = QTableWidget(1, 3)
        self.old_invoice_table.setHorizontalHeaderLabels(["Date", "Invoice", "Amount"])
        self.bio_cash_table = QTableWidget(1, 4)
        self.bio_cash_table.setHorizontalHeaderLabels(["Purpose", "Amount", "Vendor", "Sold By"])
        self.cash_summary_table = QTableWidget(1, 10)
        self.cash_summary_table.setHorizontalHeaderLabels([
            "daily_cash_count", "other_sell", "prev_day_cash", "total_cash_sell",
            "total_card_sell", "total_daily_sell", "next_day_cash_note",
            "next_day_cash_coin", "total_cash_taken", "cash_taken_by"
        ])

        def add_table_controls(table, save_fn, del_fn):
            ctrl = QHBoxLayout()
            btn_add = QPushButton("+")
            btn_add.clicked.connect(lambda: table.insertRow(table.rowCount()))
            btn_save = QPushButton("Save")
            btn_save.clicked.connect(save_fn)
            btn_cancel = QPushButton("Cancel")
            btn_cancel.clicked.connect(del_fn)
            ctrl.addWidget(btn_add)
            ctrl.addWidget(btn_save)
            ctrl.addWidget(btn_cancel)
            return ctrl

        right_panel = QVBoxLayout()
        right_panel.addWidget(QLabel("<b>Daily Expenses</b>"))
        right_panel.addWidget(self.expenses_table)
        right_panel.addLayout(add_table_controls(self.expenses_table, self.save_expenses, self.delete_expense))

        right_panel.addWidget(QLabel("<b>Old Invoices</b>"))
        right_panel.addWidget(self.old_invoice_table)
        right_panel.addLayout(add_table_controls(self.old_invoice_table, self.save_old_invoices, self.delete_old_invoice))

        right_panel.addWidget(QLabel("<b>Bio Cash Update</b>"))
        right_panel.addWidget(self.bio_cash_table)
        right_panel.addLayout(add_table_controls(self.bio_cash_table, self.save_bio_cash, self.delete_bio_cash))

        right_panel.addWidget(QLabel("<b>Daily Cash Management Summary</b>"))
        right_panel.addWidget(self.cash_summary_table)
        right_panel.addLayout(add_table_controls(self.cash_summary_table, self.save_cash_summary, self.cancel_app))

        right_wrap = QWidget()
        right_wrap.setLayout(right_panel)
        layout.addWidget(right_wrap, 2)

        # ⏱️ Date pickers
        self.export_from_date = QDateEdit()
        self.export_from_date.setCalendarPopup(True)
        self.export_from_date.setDate(QDate.currentDate())

        self.export_to_date = QDateEdit()
        self.export_to_date.setCalendarPopup(True)
        self.export_to_date.setDate(QDate.currentDate())

        # 🧾 Download button
        self.download_btn = QPushButton("📥 Download Summary")
        self.download_btn.clicked.connect(self.download_summary)

        # 📦 Layout
        date_layout = QHBoxLayout()
        date_layout.addWidget(QLabel("From:"))
        date_layout.addWidget(self.export_from_date)
        date_layout.addWidget(QLabel("To:"))
        date_layout.addWidget(self.export_to_date)
        date_layout.addStretch()
        date_layout.addWidget(self.download_btn)

        right_panel.addLayout(date_layout)

        # 🧾 Daily cash detail table (note/coin breakdown)
        self.detail_table = QTableWidget()
        self.detail_table.setColumnCount(28)  # date, qty+total x 13, total_cash
        # self.detail_table.setEditTriggers(QAbstractItemView.editTriggers)
        right_panel.addWidget(QLabel("💰 Daily Cash Count Details"))
        right_panel.addWidget(self.detail_table)

        # Optional: populate the table on start
        self.load_cash_count_detail()

    def update_coin_sum_in_summary(self, date_str):
        """
        Calculates the sum of all coins in daily_cash_count for the given date
        and updates next_day_cash_coin column in daily_cash table.
        """
        # List of columns for coins (suffix "_total" is used for subtotals)
        coin_columns = [
            "euro2_total", "euro1_total", "cent50_total", "cent20_total", "cent10_total"
        ]

        # Build query
        query = f"""
            SELECT {', '.join(coin_columns)}
            FROM daily_cash_count
            WHERE date = ?
        """
        self.cursor.execute(query, (date_str,))
        row = self.cursor.fetchone()
        print(row)

        if not row:
            return  # no data for date

        # Sum all coin totals
        coin_sum = sum(v or 0 for v in row)

        # Update in daily_cash table
        self.cursor.execute("""
            UPDATE daily_cash
            SET next_day_cash_coin = ?
            WHERE date = ?
        """, (coin_sum, date_str))

        self.conn.commit()

        # Optionally, update the visible summary table if it’s loaded
        #self.update_cash_summary()

    def open_quantity_dialog(self, name: str, value: float):
        dlg = QuantityDialog(name, value, self)
        if dlg.exec():
            qty = dlg.get_quantity()
            subtotal = qty * value

            # Clean up column key
            denomination_map = {
                "€200": "euro200",
                "€100": "euro100",
                "€50": "euro50",
                "€20": "euro20",
                "€10": "euro10",
                "€5": "euro5",
                "€2": "euro2",
                "€1": "euro1",
                "50c": "cent50",
                "20c": "cent20",
                "10c": "cent10"
            }
            denom_key = denomination_map.get(name)

            #denom_key = name.replace("€", "euro").replace("c", "cent").replace(".", "").replace(" ", "").lower()
            print(denom_key)

            # Validate allowed denominations
            valid_keys = {
                "euro200", "euro100", "euro50", "euro20", "euro10", "euro5",
                "euro2", "euro1", "cent50", "cent20", "cent10"
            }

            if denom_key not in valid_keys:
                QMessageBox.warning(self, "Error", f"Invalid denomination key: {denom_key}")
                return

            # 1. Get selected date
            selected_date = self.cash_count_date.date().toString("yyyy-MM-dd")

            # 2. Lookup existing row (or insert if not exists)
            self.cursor.execute("SELECT id FROM daily_cash_count WHERE date = ?", (selected_date,))
            row = self.cursor.fetchone()

            if row:
                self.today_cash_id = row[0]
            else:
                self.cursor.execute("INSERT INTO daily_cash_count (date, total_cash) VALUES (?, ?)",
                                    (selected_date, 0.0))
                self.conn.commit()
                self.today_cash_id = self.cursor.lastrowid

            # Check for or create today's record
            #date_today = datetime.now().strftime("%Y-%m-%d")
            #if not self.today_cash_id:
                #self.cursor.execute("SELECT id FROM daily_cash_count WHERE date = ?", (date_today,))
                #row = self.cursor.fetchone()
               #if row:
                   # self.today_cash_id = row[0]
               # else:
                   # self.cursor.execute(
                       # "INSERT INTO daily_cash_count (date, total_cash) VALUES (?, ?)",
                      #  (date_today, 0.0)
                  #  )
                  #  self.conn.commit()
                  #  self.today_cash_id = self.cursor.lastrowid

            # 3. Read existing qty & subtotal
            self.cursor.execute(
                f"SELECT {denom_key}_qty, {denom_key}_total FROM daily_cash_count WHERE id = ?",
                (self.today_cash_id,)
            )
            result = self.cursor.fetchone()

            existing_qty = result[0] if result[0] else 0
            existing_subtotal = result[1] if result[1] else 0.0

            new_qty = existing_qty + qty
            new_subtotal = existing_subtotal + (qty * value)

            # 4. Update with new values
            self.cursor.execute(f"""
                UPDATE daily_cash_count
                SET {denom_key}_qty = ?, {denom_key}_total = ?
                WHERE id = ?
            """, (new_qty, new_subtotal, self.today_cash_id))

            # Update qty & total for the denomination
           # try:
              #  self.cursor.execute(f"""
                #    UPDATE daily_cash_count
               #     SET {denom_key}_qty = ?, {denom_key}_total = ?
                #    WHERE id = ?
            #    """, (qty, subtotal, self.today_cash_id))
          #  except Exception as e:
            #    QMessageBox.critical(self, "Database Error", f"Column error for {denom_key}: {str(e)}")
              #  return

            # Recalculate total_cash
            self.cursor.execute("SELECT * FROM daily_cash_count WHERE id = ?", (self.today_cash_id,))
            row = self.cursor.fetchone()
            columns = [desc[0] for desc in self.cursor.description]

            self.total_cash = 0.0
            for i, col in enumerate(columns):
                if col.endswith("_total") and isinstance(row[i], (int, float)):
                    self.total_cash += float(row[i])

            self.cursor.execute(
                "UPDATE daily_cash_count SET total_cash = ? WHERE id = ?",
                (self.total_cash, self.today_cash_id)
            )
            self.conn.commit()
            self.update_coin_sum_in_summary(selected_date)

            QMessageBox.information(self, "Saved", f"{name} updated. Total: €{self.total_cash:.2f}")

    def save_daily_cash_count(self):
        total_cash = sum(sub[1] for sub in self.note_data.values())
        columns = []
        values = []

        for key, (qty, total) in self.note_data.items():
            columns.extend([f"{key}_qty", f"{key}_total"])
            values.extend([qty, total])

        columns.extend(["date", "total_cash"])
        values.extend([datetime.now().strftime("%Y-%m-%d"), total_cash])

        placeholders = ", ".join(["?"] * len(values))
        sql = f"INSERT INTO daily_cash_count ({', '.join(columns)}) VALUES ({placeholders})"
        self.cursor.execute(sql, values)
        self.conn.commit()
        QMessageBox.information(self, "Saved", "Daily cash count saved successfully.")

    def save_expenses(self):
        for row in range(self.expenses_table.rowCount()):
            invoice = self.expenses_table.item(row, 0)
            amount = self.expenses_table.item(row, 1)
            status = self.expenses_table.item(row, 2)
            if invoice and amount and status:
                self.cursor.execute("INSERT INTO daily_expenses (invoice, amount, status) VALUES (?, ?, ?)",
                                    (invoice.text(), amount.text(), status.text()))
        self.conn.commit()
        self.update_cash_summary()

    def save_old_invoices(self):
        for row in range(self.old_invoice_table.rowCount()):
            date = self.old_invoice_table.item(row, 0)
            invoice = self.old_invoice_table.item(row, 1)
            amount = self.old_invoice_table.item(row, 2)
            if date and invoice and amount:
                self.cursor.execute("INSERT INTO old_invoices (date, invoice, amount) VALUES (?, ?, ?)",
                                    (date.text(), invoice.text(), float(amount.text())))
        self.conn.commit()
        self.update_cash_summary()

    def save_bio_cash(self):
        for row in range(self.bio_cash_table.rowCount()):
            p, a, v, s = [self.bio_cash_table.item(row, col) for col in range(4)]
            if p and a and v and s:
                self.cursor.execute("INSERT INTO bio_cash (purpose, amount, vendor, sold_by) VALUES (?, ?, ?, ?)",
                                    (p.text(), float(a.text()), v.text(), s.text()))
        self.conn.commit()
        self.update_cash_summary()

    def delete_expense(self):
        r = self.expenses_table.currentRow()
        if r >= 0: self.expenses_table.removeRow(r)

    def delete_old_invoice(self):
        r = self.old_invoice_table.currentRow()
        if r >= 0: self.old_invoice_table.removeRow(r)

    def delete_bio_cash(self):
        r = self.bio_cash_table.currentRow()
        if r >= 0: self.bio_cash_table.removeRow(r)

    def show_stats(self, title, period):
        self.stats_window = StatsWindow(title, period)
        self.stats_window.show()



    def save_cash_summary(self):
        vals = [self.cash_summary_table.item(0, i).text() if self.cash_summary_table.item(0, i) else "" for i in range(10)]
        self.cursor.execute("""
            INSERT INTO daily_cash (
                daily_cash_count, other_sell, prev_day_cash, total_cash_sell,
                total_card_sell, total_daily_sell, next_day_cash_note,
                next_day_cash_coin, total_cash_taken, cash_taken_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", vals)
        self.conn.commit()
        QMessageBox.information(self, "Saved", "Summary saved.")

    def load_cash_count_detail(self):
        self.cursor.execute("PRAGMA table_info(daily_cash_count)")
        columns = [col[1] for col in self.cursor.fetchall()]

        self.cursor.execute("SELECT * FROM daily_cash_count ORDER BY date DESC")
        rows = self.cursor.fetchall()

        self.detail_table.setRowCount(len(rows))
        self.detail_table.setColumnCount(len(columns))
        self.detail_table.setHorizontalHeaderLabels(columns)

        for row_idx, row_data in enumerate(rows):
            for col_idx, value in enumerate(row_data):
                item = QTableWidgetItem(str(value))
                self.detail_table.setItem(row_idx, col_idx, item)

    def update_cash_summary(self):
        def sum_col(table, idx):
            total = 0.0
            for row in range(table.rowCount()):
                item = table.item(row, idx)
                if item:
                    try:
                        total += float(item.text())
                    except ValueError:
                        pass
            return total

        daily_exp = sum_col(self.expenses_table, 1)
        old_inv = sum_col(self.old_invoice_table, 2)
        bio_total = sum_col(self.bio_cash_table, 1)
        total_cash_sell = daily_exp + old_inv
        total_card_sell = 0  # Manual or calculated if needed
        total_daily_sell = total_cash_sell + total_card_sell
        if old_inv:
            self.cash_summary_table.setItem(0, 0, QTableWidgetItem(str(self.total_cash - old_inv)))
        elif daily_exp:
            self.cash_summary_table.setItem(0, 0, QTableWidgetItem(str(self.total_cash - daily_exp)))
        elif old_inv and daily_exp:
            self.cash_summary_table.setItem(0, 0, QTableWidgetItem(str(self.total_cash - daily_exp - old_inv)))
        else:
            self.cash_summary_table.setItem(0, 0, QTableWidgetItem(str(self.total_cash)))

        #self.cash_summary_table.setItem(0, 0, QTableWidgetItem(str(self.total_cash)))
        self.cash_summary_table.setItem(0, 1, QTableWidgetItem(str(bio_total)))
        self.cash_summary_table.setItem(0, 3, QTableWidgetItem(str(total_cash_sell)))
        self.cash_summary_table.setItem(0, 4, QTableWidgetItem(str(total_card_sell)))
        self.cash_summary_table.setItem(0, 5, QTableWidgetItem(str(total_daily_sell)))
        self.cash_summary_table.setItem(0, 9, QTableWidgetItem("Manager"))

    def download_summary(self):
        from_date = self.export_from_date.date().toString("yyyy-MM-dd")
        to_date = self.export_to_date.date().toString("yyyy-MM-dd")

        # Query
        self.cursor.execute("""
            SELECT * FROM daily_cash_count
            WHERE date BETWEEN ? AND ?
            ORDER BY date
        """, (from_date, to_date))
        rows = self.cursor.fetchall()

        self.cursor.execute("PRAGMA table_info(daily_cash_count)")
        columns = [col[1] for col in self.cursor.fetchall()]

        if not rows:
            QMessageBox.information(self, "No Data", "No entries found in selected date range.")
            return

        # Convert to DataFrame
        df = pd.DataFrame(rows, columns=columns)

        # Ask where to save
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Excel File", "", "Excel Files (*.xlsx)")
        if not file_path:
            return

        try:
            df.to_excel(file_path, index=False, engine='openpyxl')
            QMessageBox.information(self, "Success", f"Summary exported to:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export Excel: {str(e)}")

    def load_old_cash_data(self):
        selected_date = self.cash_count_date.date().toString("yyyy-MM-dd")

        # Load from daily_cash_count
        self.cursor.execute("SELECT * FROM daily_cash_count WHERE date = ?", (selected_date,))
        row = self.cursor.fetchone()

        if not row:
            QMessageBox.information(self, "Not Found", "No cash count data found for this date.")
            return

        columns = [desc[0] for desc in self.cursor.description]
        row_dict = dict(zip(columns, row))
        self.today_cash_id = row_dict["id"]

        # Repopulate Cash Summary Table (assuming 1 row, 10 columns)
        cash_fields = [
            "daily_cash_count", "other_sell", "prev_day_cash", "total_cash_sell",
            "total_card_sell", "total_daily_sell", "next_day_cash_note", "next_day_cash_coin",
            "total_cash_taken", "cash_taken_by"
        ]

        self.cursor.execute("SELECT * FROM daily_cash WHERE date = ?", (selected_date,))
        cash_row = self.cursor.fetchone()

        if cash_row:
            cash_cols = [desc[0] for desc in self.cursor.description]
            cash_data = dict(zip(cash_cols, cash_row))

            self.cash_management_table.setRowCount(1)
            for col_idx, field in enumerate(cash_fields):
                value = str(cash_data.get(field, ""))
                self.cash_management_table.setItem(0, col_idx, QTableWidgetItem(value))
        else:
            # If no daily_cash row, clear it
            self.cash_management_table.setRowCount(1)
            for col in range(self.cash_management_table.columnCount()):
                self.cash_management_table.setItem(0, col, QTableWidgetItem(""))

        QMessageBox.information(self, "Loaded", f"Values loaded for {selected_date}.")

    def cancel_app(self):
        self.close()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())

