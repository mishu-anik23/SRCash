import os
import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QTableWidget, QTableWidgetItem, QPushButton, QLineEdit,
    QHeaderView, QScrollArea, QSplitter, QDateEdit, QDialog,
    QMessageBox
)
from PyQt6.QtGui import QPixmap, QIcon, QIntValidator, QColor
from PyQt6.QtCore import Qt, QDate

from db_manager import DBManager, DENOM_MAPPING
from ui_stats import StatWindow   # ✅ import statistics window


class QuantityDialog(QDialog):
    def __init__(self, denom_name, denom_value, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Enter Quantity - {denom_name}")
        self.denom_name = denom_name
        self.denom_value = denom_value
        self.quantity = 0

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Enter quantity for {denom_name}:"))

        self.input = QLineEdit()
        self.input.setPlaceholderText("0")
        self.input.setValidator(QIntValidator(0, 10000, self))
        layout.addWidget(self.input)

        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def get_quantity1(self):
        try:
            return int(self.input.text()) if self.input.text() else 0
        except ValueError:
            return 0

    def get_quantity(self):
        try:
            return int(self.input.text()) if self.input.text().strip() != "" else 0
        except ValueError:
            return 0


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("E-Cash Supermarket")
        self.resize(1400, 800)

        self.db = DBManager()
        self.selected_date = QDate.currentDate().toString("yyyy-MM-dd")

        self._init_ui()

    def _init_ui(self):
        # Left panel
        left_layout = QVBoxLayout()

        self.add_logo(left_layout)
        self.set_welcome_banner(left_layout)
        #title = QLabel("Supermarket Name\n123 Market Street, City")
        #title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        #left_layout.addWidget(title)

        # Date picker
        date_layout = QHBoxLayout()
        lbl = QLabel("Date:")
        self.date_picker = QDateEdit()
        self.date_picker.setDate(QDate.currentDate())
        self.date_picker.setCalendarPopup(True)
        self.date_picker.dateChanged.connect(self._on_date_changed)
        date_layout.addWidget(lbl)
        date_layout.addWidget(self.date_picker)
        date_container = QWidget()
        date_container.setLayout(date_layout)
        left_layout.addWidget(date_container)

        # Denominations grid (2-column layout inside scroll)
        denom_layout = QVBoxLayout()
        row_layout = QHBoxLayout()
        for i, denom in enumerate(DENOM_MAPPING.keys()):
            btn = QPushButton()
            img_path = f"img/euro/{denom.replace('€','euro').replace('c','cent')}.png"
            pixmap = QPixmap(img_path)
            if not pixmap.isNull():
                pixmap = pixmap.scaled(200, 100, Qt.AspectRatioMode.KeepAspectRatio)
                btn.setIcon(QIcon(pixmap))
                btn.setIconSize(pixmap.size())
            else:
                btn.setText(denom)
            btn.clicked.connect(lambda _, d=denom: self._on_denom_click(d))
            row_layout.addWidget(btn)

            if (i + 1) % 2 == 0:
                denom_layout.addLayout(row_layout)
                row_layout = QHBoxLayout()
        if row_layout.count() > 0:
            denom_layout.addLayout(row_layout)

        denom_container = QWidget()
        denom_container.setLayout(denom_layout)
        denom_scroll = QScrollArea()
        denom_scroll.setWidgetResizable(True)
        denom_scroll.setWidget(denom_container)
        left_layout.addWidget(denom_scroll)

        # Wrap left in scroll
        left_container = QWidget()
        left_container.setLayout(left_layout)
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setWidget(left_container)

        # Right panel (tables)
        right_layout = QVBoxLayout()

        # Daily Expenses
        self.expenses_table = self._make_table(["Invoice", "Amount", "Status"])
        name_expense_table = QLabel("Daily Expenses")
        name_expense_table.setStyleSheet("font-size: 16px; font-weight: bold; padding: 2px;")
        #self.name_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        #right_layout.addWidget(QLabel("Daily Expenses"))
        right_layout.addWidget(name_expense_table)
        right_layout.addWidget(self.expenses_table)
        self._add_table_buttons(right_layout, self.save_expenses, self.cancel_expenses, self.add_expense_row)

        # Old Invoice
        self.old_invoice_table = self._make_table(["Date", "Invoice", "Amount"])
        name_old_invoice_table = QLabel("Old Invoice Payment")
        name_old_invoice_table.setStyleSheet("font-size: 16px; font-weight: bold; padding: 2px;")
        right_layout.addWidget(name_old_invoice_table)
        right_layout.addWidget(self.old_invoice_table)
        self._add_table_buttons(right_layout, self.save_old_invoices, self.cancel_old_invoices, self.add_old_invoice_row)

        # Bio Cash
        self.bio_cash_table = self._make_table(["Purpose", "Amount", "Vendor", "Sold By"])
        name_bio_cash_table = QLabel("Bio Cash Update")
        name_bio_cash_table.setStyleSheet("font-size: 16px; font-weight: bold; padding: 2px;")
        right_layout.addWidget(name_bio_cash_table)
        right_layout.addWidget(self.bio_cash_table)
        self._add_table_buttons(right_layout, self.save_bio_cash, self.cancel_bio_cash, self.add_bio_cash_row)

        # Cash Summary
        self.cash_summary_table = self._make_table([
            "Prev Day Cash", "Total Cash Sell", "Total Card Sell",
            "Next Day Cash Note", "Next Day Cash Coin",
            "Total Daily Sell", "Total Cash Taken", "Cash Taken By"
        ])
        name_cash_summery_table = QLabel("Daily Cash Summary")
        name_cash_summery_table.setStyleSheet("font-size: 16px; font-weight: bold; padding: 2px;")
        right_layout.addWidget(name_cash_summery_table)
        right_layout.addWidget(self.cash_summary_table)
        self._add_table_buttons(right_layout, self.save_cash_summary, self.cancel_cash_summary, None)

        # Right scroll
        right_container = QWidget()
        right_container.setLayout(right_layout)
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setWidget(right_container)

        # Splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_scroll)
        splitter.addWidget(right_scroll)

        # Set left side ~1/3 and right side ~2/3
        total_width = self.width()
        splitter.setSizes([total_width // 3, (total_width * 2) // 3])

        # Add Show Stats button
        btn_stats = QPushButton("Show Statistics")
        btn_stats.setStyleSheet("""
                QPushButton {
                    background-color: #445C69;
                    font-weight: bold;
                    font-size: 24px;
                    color: white;
                    padding: 10px;
                    border-radius: 5px;
                }
            """)
        btn_stats.clicked.connect(self._open_stats)

        main_layout = QVBoxLayout()
        main_layout.addWidget(splitter)
        main_layout.addWidget(btn_stats, alignment=Qt.AlignmentFlag.AlignRight)

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

    def add_logo(self, layout):
        logo_path = os.path.join('img', 'logo-sr-tmp.jpeg')
        logo_label = QLabel()
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            logo_label.setPixmap(pixmap.scaledToWidth(120))
        else:
            logo_label.setText("Logo Not Found")
            logo_label.setStyleSheet("color: red; font-size: 16px;")
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(logo_label)

    def set_welcome_banner(self, layout):
        #banner_layout = QVBoxLayout()
        #banner_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self.name_banner = QLabel("Sunrise Supermarkt")
        self.name_banner.setStyleSheet("font-size: 18px; font-weight: bold; padding: 2px;")
        self.name_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.name_banner)

        self.address_banner_street = QLabel("Schwarzwald Straße 27")
        self.address_banner_street.setStyleSheet("font-size: 10px; font-weight: bold; padding: 1px;")
        self.address_banner_street.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.address_banner_street)

        self.address_banner_city = QLabel("60528 Frankfurt am Main")
        self.address_banner_city.setStyleSheet("font-size: 10px; font-weight: bold; padding: 1px;")
        self.address_banner_city.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.address_banner_city)

        # Spacer
        spacer = QLabel("")
        spacer.setFixedHeight(10)
        layout.addWidget(spacer)

        self.welcome_banner = QLabel("SR Daily Cash Manage")
        self.welcome_banner.setStyleSheet("font-size: 18px; font-weight: bold; padding: 10px;")
        self.welcome_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.welcome_banner)

    # --------- Helpers ---------
    def _make_table(self, headers):
        table = QTableWidget(1, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        # Fix first row to use styled cells
        for col in range(len(headers)):
            table.setItem(0, col, self.make_cell(""))

        return table

    def make_cell(self, text=""):
        item = QTableWidgetItem(str(text))
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
        item.setBackground(QColor("white"))
        item.setForeground(QColor("black"))
        return item

    def _add_table_buttons(self, layout, save_fn, cancel_fn, add_fn):
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.setStyleSheet("""
                QPushButton {
                    background-color: #3E5C38;
                    font-weight: bold;
                    font-size: 16px;
                    color: white;
                    padding: 5px;
                    border-radius: 3px;
                }
            """)
        save_btn.clicked.connect(save_fn)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet("""
                QPushButton {
                    background-color: #E3A032;
                    font-weight: bold;
                    font-size: 16px;
                    color: white;
                    padding: 5px;
                    border-radius: 3px;
                }
            """)
        cancel_btn.clicked.connect(cancel_fn)
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        if add_fn:
            add_btn = QPushButton("+")
            add_btn.setStyleSheet("""
                QPushButton {
                    background-color: #535569;
                    font-weight: bold;
                    font-size: 16px;
                    color: white;
                    padding: 5px;
                    border-radius: 3px;
                }
            """)
            add_btn.clicked.connect(add_fn)
            btn_layout.addWidget(add_btn)
        layout.addLayout(btn_layout)

    # --------- Denomination click ---------
    def _on_denom_click(self, denom):
        qty_col, subtotal_col, denom_value = DENOM_MAPPING[denom]
        dialog = QuantityDialog(denom, denom_value, self)
        if dialog.exec():
            qty = dialog.get_quantity()
            self.db.upsert_denomination(self.selected_date, denom, qty)

            dcc = self.db.fetchone("SELECT total_cash FROM daily_cash_count WHERE date = ?", (self.selected_date,))
            total_cash = dcc[0] if dcc else 0
            QMessageBox.information(self, "Saved", f"{denom}: {qty} saved.\nTotal Cash: €{total_cash}")

            self._update_summary_auto()

    # --------- Auto summary update ---------

    def _update_summary_auto(self):
        # 1. Total cash from notes/coins
        dcc = self.db.fetchone("SELECT total_cash FROM daily_cash_count WHERE date = ?", (self.selected_date,))
        total_cash = dcc[0] if dcc else 0

        # 2. Prev day cash
        prev_day_item = self.cash_summary_table.item(0, 0)
        prev_day_cash = float(prev_day_item.text()) if prev_day_item else 0

        # 3. Expenses paid
        exp_sum = \
        self.db.fetchone("SELECT COALESCE(SUM(amount),0) FROM daily_expenses WHERE date=? AND status IN ('paid','p')",
                         (self.selected_date,))[0]

        # 4. Old invoices
        old_sum = \
        self.db.fetchone("SELECT COALESCE(SUM(amount),0) FROM old_invoices WHERE date=?", (self.selected_date,))[0]

        # 5. Bio cash
        #bio_sum = self.db.fetchone("SELECT COALESCE(SUM(amount),0) FROM bio_cash WHERE date=?", (self.selected_date,))[
          #  0]

        # 6. Coins
        coin_sum = self.db.fetchone("""
               SELECT COALESCE(euro2_total,0)+COALESCE(euro1_total,0)+COALESCE(cent50_total,0)+COALESCE(cent20_total,0)+
               COALESCE(cent10_total,0)
               FROM daily_cash_count WHERE date = ?
           """, (self.selected_date,))[0]

        # Final calculations
        total_cash_sell = total_cash - prev_day_cash - exp_sum - old_sum

        # Update table cells
        self.cash_summary_table.setItem(0, 1, QTableWidgetItem(str(total_cash_sell)))
        self.cash_summary_table.setItem(0, 4, QTableWidgetItem(str(coin_sum)))

    def _on_date_changed(self, qdate):
        self.selected_date = qdate.toString("yyyy-MM-dd")

    def _open_stats(self):
        self.stats_window = StatWindow(self.db)
        self.stats_window.show()

    # --------- Table actions (stubs for now) ---------
    def save_expenses(self):
        for row in range(self.expenses_table.rowCount()):
            invoice = self.expenses_table.item(row, 0)
            amount = self.expenses_table.item(row, 1)
            status = self.expenses_table.item(row, 2)
            if invoice and amount and status:
                self.db.safe_execute("""
                     INSERT INTO daily_expenses (date, invoice, amount, status)
                     VALUES (?, ?, ?, ?)
                 """, (self.selected_date, invoice.text(), float(amount.text()), status.text()))
        self.db.conn.commit()
        self._update_summary_auto()

    def cancel_expenses(self):
        row = self.expenses_table.currentRow()
        if row >= 0:
            self.expenses_table.removeRow(row)

    def add_expense_row(self):
        row = self.expenses_table.rowCount()
        self.expenses_table.insertRow(row)
        self.expenses_table.setItem(row, 0, self.make_cell(""))  # invoice
        self.expenses_table.setItem(row, 1, self.make_cell(""))  # amount
        self.expenses_table.setItem(row, 2, self.make_cell("unpaid"))  # default status

    def save_old_invoices(self):
        for row in range(self.old_invoice_table.rowCount()):
            date_item = self.old_invoice_table.item(row, 0)
            invoice = self.old_invoice_table.item(row, 1)
            amount = self.old_invoice_table.item(row, 2)
            if date_item and invoice and amount:
                self.db.safe_execute("""
                    INSERT INTO old_invoices (date, invoice, amount)
                    VALUES (?, ?, ?)
                """, (date_item.text(), invoice.text(), float(amount.text())))
        self.db.conn.commit()
        self._update_summary_auto()

    def cancel_old_invoices(self):
        row = self.old_invoice_table.currentRow()
        if row >= 0:
            self.old_invoice_table.removeRow(row)

    def add_old_invoice_row(self):
        row = self.old_invoice_table.rowCount()
        self.old_invoice_table.insertRow(row)
        self.old_invoice_table.setItem(row, 0, self.make_cell(""))
        self.old_invoice_table.setItem(row, 1, self.make_cell(""))
        self.old_invoice_table.setItem(row, 2, self.make_cell(""))

    def save_bio_cash(self):
        for row in range(self.bio_cash_table.rowCount()):
            purpose = self.bio_cash_table.item(row, 0)
            amount = self.bio_cash_table.item(row, 1)
            vendor = self.bio_cash_table.item(row, 2)
            sold_by = self.bio_cash_table.item(row, 3)
            if purpose and amount:
                self.db.safe_execute("""
                    INSERT INTO bio_cash (date, purpose, amount, vendor, sold_by)
                    VALUES (?, ?, ?, ?, ?)
                """, (self.selected_date, purpose.text(), float(amount.text() or 0),
                      vendor.text() if vendor else "", sold_by.text() if sold_by else ""))
        self.db.conn.commit()
        self._update_summary_auto()

    def cancel_bio_cash(self):
        row = self.bio_cash_table.currentRow()
        if row >= 0:
            self.bio_cash_table.removeRow(row)

    def add_bio_cash_row(self):
        row = self.bio_cash_table.rowCount()
        self.bio_cash_table.insertRow(row)
        self.bio_cash_table.rowCount()
        self.bio_cash_table.setItem(row, 0, self.make_cell(""))
        self.bio_cash_table.setItem(row, 1, self.make_cell(""))
        self.bio_cash_table.setItem(row, 2, self.make_cell(""))
        self.bio_cash_table.setItem(row, 3, self.make_cell(""))


    def save_cash_summary(self):
        prev_day = self.cash_summary_table.item(0, 0)
        total_cash_sell = self.cash_summary_table.item(0, 1)
        total_card = self.cash_summary_table.item(0, 2)
        next_day_note = self.cash_summary_table.item(0, 3)
        next_day_coin = self.cash_summary_table.item(0, 4)
        total_daily = self.cash_summary_table.item(0, 5)
        total_taken = self.cash_summary_table.item(0, 6)
        taken_by = self.cash_summary_table.item(0, 7)

        self.db.safe_execute("""
            INSERT OR REPLACE INTO daily_cash
            (date, prev_day_cash, total_cash_sell, total_card_sell,
             next_day_cash_note, next_day_cash_coin,
             total_daily_sell, total_cash_taken, cash_taken_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            self.selected_date,
            float(prev_day.text()) if prev_day else 0,
            float(total_cash_sell.text()) if total_cash_sell else 0,
            float(total_card.text()) if total_card else 0,
            float(next_day_note.text()) if next_day_note else 0,
            float(next_day_coin.text()) if next_day_coin else 0,
            float(total_daily.text()) if total_daily else 0,
            float(total_taken.text()) if total_taken else 0,
            taken_by.text() if taken_by else ""
        ))
        self.db.conn.commit()
        QMessageBox.information(self, "Saved", "Cash Summary saved successfully!")

    def cancel_cash_summary(self):
        row = self.cash_summary_table.currentRow()
        if row >= 0:
            self.cash_summary_table.removeRow(row)



if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())
