import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QTableWidget, QTableWidgetItem, QPushButton, QLineEdit,
    QHeaderView, QScrollArea, QSplitter, QDateEdit, QDialog,
    QMessageBox
)
from PyQt6.QtGui import QPixmap, QIcon, QIntValidator
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

    def get_quantity(self):
        try:
            return int(self.input.text()) if self.input.text() else 0
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

        title = QLabel("Supermarket Name\n123 Market Street, City")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_layout.addWidget(title)

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
                pixmap = pixmap.scaled(100, 70, Qt.AspectRatioMode.KeepAspectRatio)
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
        right_layout.addWidget(QLabel("Daily Expenses"))
        right_layout.addWidget(self.expenses_table)
        self._add_table_buttons(right_layout, self.save_expenses, self.cancel_expenses, self.add_expense_row)

        # Old Invoice
        self.old_invoice_table = self._make_table(["Date", "Invoice", "Amount"])
        right_layout.addWidget(QLabel("Old Invoice Payment"))
        right_layout.addWidget(self.old_invoice_table)
        self._add_table_buttons(right_layout, self.save_old_invoices, self.cancel_old_invoices, self.add_old_invoice_row)

        # Bio Cash
        self.bio_cash_table = self._make_table(["Purpose", "Amount", "Vendor", "Sold By"])
        right_layout.addWidget(QLabel("Bio Cash Update"))
        right_layout.addWidget(self.bio_cash_table)
        self._add_table_buttons(right_layout, self.save_bio_cash, self.cancel_bio_cash, self.add_bio_cash_row)

        # Cash Summary
        self.cash_summary_table = self._make_table([
            "Prev Day Cash", "Total Cash Sell", "Total Card Sell",
            "Next Day Cash Note", "Next Day Cash Coin",
            "Total Daily Sell", "Total Cash Taken", "Cash Taken By"
        ])
        right_layout.addWidget(QLabel("Cash Summary"))
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
        btn_stats = QPushButton("Show Stats")
        btn_stats.clicked.connect(self._open_stats)

        main_layout = QVBoxLayout()
        main_layout.addWidget(splitter)
        main_layout.addWidget(btn_stats, alignment=Qt.AlignmentFlag.AlignRight)

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

    # --------- Helpers ---------
    def _make_table(self, headers):
        table = QTableWidget(1, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        return table

    def _add_table_buttons(self, layout, save_fn, cancel_fn, add_fn):
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(save_fn)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(cancel_fn)
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        if add_fn:
            add_btn = QPushButton("+")
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
        dcc = self.db.fetchone("SELECT total_cash FROM daily_cash_count WHERE date = ?", (self.selected_date,))
        total_cash = dcc[0] if dcc else 0
        coin_sum = self.db.fetchone("""
            SELECT COALESCE(cent50_total,0)+COALESCE(cent20_total,0)+COALESCE(cent10_total,0)
            FROM daily_cash_count WHERE date = ?
        """, (self.selected_date,))
        coin_sum = coin_sum[0] if coin_sum else 0

        self.cash_summary_table.setItem(0, 1, QTableWidgetItem(str(total_cash)))
        self.cash_summary_table.setItem(0, 4, QTableWidgetItem(str(coin_sum)))

    def _on_date_changed(self, qdate):
        self.selected_date = qdate.toString("yyyy-MM-dd")

    def _open_stats(self):
        self.stats_window = StatWindow(self.db)
        self.stats_window.show()

    # --------- Table actions (stubs for now) ---------
    def save_expenses(self): pass
    def cancel_expenses(self): pass
    def add_expense_row(self): self.expenses_table.insertRow(self.expenses_table.rowCount())

    def save_old_invoices(self): pass
    def cancel_old_invoices(self): pass
    def add_old_invoice_row(self): self.old_invoice_table.insertRow(self.old_invoice_table.rowCount())

    def save_bio_cash(self): pass
    def cancel_bio_cash(self): pass
    def add_bio_cash_row(self): self.bio_cash_table.insertRow(self.bio_cash_table.rowCount())

    def save_cash_summary(self): pass
    def cancel_cash_summary(self): pass


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())
