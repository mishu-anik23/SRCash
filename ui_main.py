import os
import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QTableWidget, QTableWidgetItem, QPushButton, QLineEdit,
    QHeaderView, QScrollArea, QSplitter, QDateEdit, QDialog,
    QMessageBox, QComboBox, QCalendarWidget, QDialogButtonBox
)
from PyQt6.QtGui import QPixmap, QIcon, QIntValidator, QColor
from PyQt6.QtCore import Qt, QDate

from db_manager import DBManager, DENOM_MAPPING
from ui_stats import StatWindow   # ✅ import statistics window

# Default first row in Bio Cash table (legacy DB rows may use the older label)
DAILY_SURPLUS_PURPOSE = "Daily Surplus Cash"
DAILY_SURPLUS_PURPOSE_LEGACY = "Daily Cash Surplus"


def _is_daily_surplus_purpose(text: str | None) -> bool:
    if not text:
        return False
    p = text.strip()
    return p in (DAILY_SURPLUS_PURPOSE, DAILY_SURPLUS_PURPOSE_LEGACY)


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
        self._updating_cells = False  # Flag to prevent infinite loops during auto-calculation

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
        self.expenses_table = self._make_table(["Invoice", "Amount", "Status", "Cash Source"])
        name_expense_table = QLabel("Daily Expenses")
        name_expense_table.setStyleSheet("font-size: 16px; font-weight: bold; padding: 2px;")
        #self.name_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        #right_layout.addWidget(QLabel("Daily Expenses"))
        right_layout.addWidget(name_expense_table)
        right_layout.addWidget(self.expenses_table)
        self._add_table_buttons(right_layout, self.save_expenses, self.cancel_expenses, self.add_expense_row)

        # Old Invoice
        self.old_invoice_table = self._make_table(["Date", "Invoice", "Amount", "Cash Source"])
        name_old_invoice_table = QLabel("Old Invoice Payment")
        name_old_invoice_table.setStyleSheet("font-size: 16px; font-weight: bold; padding: 2px;")
        right_layout.addWidget(name_old_invoice_table)
        right_layout.addWidget(self.old_invoice_table)
        self._add_table_buttons(right_layout, self.save_old_invoices, self.cancel_old_invoices, self.add_old_invoice_row)

        # Initialize default Cash Source widgets for the first row of each table
        self._setup_cash_source_cell(self.expenses_table, 0, 3)
        self._setup_cash_source_cell(self.old_invoice_table, 0, 3)

        # Cash summary table (created before Bio so surplus / totals can reference it)
        self.cash_summary_table = self._make_table([
            "Prev Day Cash", "Total Cash Sell", "Terminal Cash", "Total Card Sell",
            "Next Day Cash Note", "Next Day Cash Coin", "Daily Terminal Sell",
            "Total Daily Sell", "Total Cash Taken", "Cash Taken By"
        ])
        self.cash_summary_table.cellChanged.connect(self._on_cash_summary_cell_changed)

        # Bio Cash
        self.bio_cash_table = self._make_table(["Purpose", "Amount", "Vendor", "Sold By", "Created At"])
        self.bio_cash_table.cellChanged.connect(self._on_bio_cash_cell_changed)
        name_bio_cash_table = QLabel("Bio Cash Update")
        name_bio_cash_table.setStyleSheet("font-size: 16px; font-weight: bold; padding: 2px;")
        right_layout.addWidget(name_bio_cash_table)
        right_layout.addWidget(self.bio_cash_table)
        self._add_table_buttons(right_layout, self.save_bio_cash, self.cancel_bio_cash, self.add_bio_cash_row)

        bio_total_row = QHBoxLayout()
        bio_total_row.addWidget(QLabel("Total Bio Cash (selected day):"))
        self.btn_total_bio_cash = QPushButton("€ 0.00")
        self.btn_total_bio_cash.setEnabled(False)
        self.btn_total_bio_cash.setStyleSheet("""
            QPushButton {
                background-color: #2E4A3E;
                color: white;
                font-weight: bold;
                font-size: 14px;
                padding: 8px 14px;
                border-radius: 4px;
            }
        """)
        bio_total_row.addWidget(self.btn_total_bio_cash)
        bio_total_row.addStretch()
        right_layout.addLayout(bio_total_row)

        self._init_bio_cash_default_table_state()

        # Cash Summary (widgets created above; add to layout here)
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

        # Add buttons layout
        buttons_layout = QHBoxLayout()
        
        # Add Load Data button
        btn_load_data = QPushButton("Load Data")
        btn_load_data.setStyleSheet("""
                QPushButton {
                    background-color: #445C69;
                    font-weight: bold;
                    font-size: 16px;
                    color: white;
                    padding: 10px;
                    border-radius: 5px;
                }
            """)
        btn_load_data.clicked.connect(lambda: self._load_data_for_date())
        
        # Add Show Stats button
        btn_stats = QPushButton("Show Statistics")
        btn_stats.setStyleSheet("""
                QPushButton {
                    background-color: #445C69;
                    font-weight: bold;
                    font-size: 16px;
                    color: white;
                    padding: 10px;
                    border-radius: 5px;
                }
            """)
        btn_stats.clicked.connect(self._open_stats)
        
        buttons_layout.addWidget(btn_load_data)
        buttons_layout.addWidget(btn_stats)
        buttons_layout.addStretch()  # Push buttons to the right

        main_layout = QVBoxLayout()
        main_layout.addWidget(splitter)
        main_layout.addLayout(buttons_layout)

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

    # --------- Bio Cash: default row & totals ---------
    def _fetch_saved_daily_surplus_from_db(self):
        """Return saved Daily Surplus amount for selected date, or None if not stored."""
        try:
            row = self.db.fetchone(
                """
                SELECT amount FROM bio_cash
                WHERE date = ? AND purpose IN (?, ?)
                ORDER BY id DESC LIMIT 1
                """,
                (self.selected_date, DAILY_SURPLUS_PURPOSE, DAILY_SURPLUS_PURPOSE_LEGACY),
            )
            if row and row[0] is not None:
                return float(row[0])
        except Exception:
            pass
        return None

    def _init_bio_cash_default_table_state(self):
        """First row: Daily Surplus Cash — amount from DB for this date, else calculated, else 0."""
        saved = self._fetch_saved_daily_surplus_from_db()
        if saved is not None:
            surplus = saved
        else:
            surplus = self._calculate_daily_surplus_cash()
            if surplus is None:
                surplus = 0.0

        self.bio_cash_table.setRowCount(max(1, self.bio_cash_table.rowCount()))
        self.bio_cash_table.setItem(0, 0, self.make_cell(DAILY_SURPLUS_PURPOSE))
        daily_surplus_item = self.make_cell(f"{surplus:.2f}")
        daily_surplus_item.setFlags(daily_surplus_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.bio_cash_table.setItem(0, 1, daily_surplus_item)
        self.bio_cash_table.setItem(0, 2, self.make_cell(""))
        self.bio_cash_table.setItem(0, 3, self.make_cell(""))
        created_item = self.make_cell("")
        created_item.setFlags(created_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.bio_cash_table.setItem(0, 4, created_item)
        self._update_bio_cash_total_display()

    def _table_cell_float(self, item, default=0.0) -> float:
        if item and item.text().strip():
            try:
                return float(item.text())
            except ValueError:
                return default
        return default

    def _table_bio_surplus_amount(self) -> float:
        item = self.bio_cash_table.item(0, 1)
        return self._table_cell_float(item, 0.0)

    def _table_bio_extra_amount_sum(self) -> float:
        """Sum of Amount column for user rows (row > 0), excluding surplus purpose rows."""
        total = 0.0
        for row in range(1, self.bio_cash_table.rowCount()):
            purpose_item = self.bio_cash_table.item(row, 0)
            purpose = purpose_item.text().strip() if purpose_item else ""
            if _is_daily_surplus_purpose(purpose):
                continue
            amount_item = self.bio_cash_table.item(row, 1)
            total += self._table_cell_float(amount_item, 0.0)
        return total

    def _table_total_bio_cash(self) -> float:
        """Daily surplus (row 0) + sum of other row amounts (real-time from table)."""
        return self._table_bio_surplus_amount() + self._table_bio_extra_amount_sum()

    # --------- Cash Source helpers ---------
    def _ask_old_cash_date(self):
        """Show a calendar dialog and return selected date as yyyy-MM-dd, or None if cancelled."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Select Old Cash Date")
        layout = QVBoxLayout(dialog)

        calendar = QCalendarWidget()
        calendar.setSelectedDate(QDate.currentDate())
        layout.addWidget(calendar)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        layout.addWidget(buttons)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)

        if dialog.exec():
            date = calendar.selectedDate()
            return date.toString("yyyy-MM-dd")
        return None

    def _on_cash_source_changed(self, combo: QComboBox, index: int):
        """Handle selection changes for the Cash Source combo box."""
        # Index 0 -> Current Day, Index 1 -> Old Cash (requires date)
        if index == 1:  # Old Cash selected
            # Ask user for the old cash date
            date_str = self._ask_old_cash_date()
            if date_str:
                combo.setProperty("cash_date", date_str)
                combo.setItemText(1, f"Old Cash ({date_str})")
            else:
                # User cancelled date selection, revert to Current Day
                combo.blockSignals(True)
                combo.setCurrentIndex(0)
                combo.blockSignals(False)
                combo.setProperty("cash_date", None)
                combo.setItemText(1, "Old Cash")
        else:
            # Reset to Current Day, clear any stored date
            combo.setProperty("cash_date", None)
            combo.setItemText(1, "Old Cash")

    def _setup_cash_source_cell(self, table: QTableWidget, row: int, col: int,
                                existing_source: str | None = None,
                                existing_date: str | None = None):
        """Create and attach a Cash Source combo box to the given cell."""
        combo = QComboBox()
        combo.addItem("Current Day")
        combo.addItem("Old Cash")
        combo.setProperty("cash_date", None)

        # Restore previous value if provided
        if existing_source == "Old Cash":
            combo.setCurrentIndex(1)
            if existing_date:
                combo.setProperty("cash_date", existing_date)
                combo.setItemText(1, f"Old Cash ({existing_date})")
        else:
            combo.setCurrentIndex(0)

        combo.currentIndexChanged.connect(lambda idx, cb=combo: self._on_cash_source_changed(cb, idx))
        table.setCellWidget(row, col, combo)

    # --------- Denomination click ---------
    def _on_denom_click(self, denom):
        try:
            qty_col, subtotal_col, denom_value = DENOM_MAPPING[denom]
            dialog = QuantityDialog(denom, denom_value, self)
            if dialog.exec():
                qty = dialog.get_quantity()
                self.db.upsert_denomination(self.selected_date, denom, qty)

                dcc = self.db.fetchone("SELECT total_cash FROM daily_cash_count WHERE date = ?", (self.selected_date,))
                total_cash = float(dcc[0]) if dcc and dcc[0] is not None else 0.0
                QMessageBox.information(self, "Saved", f"{denom}: {qty} saved.\nTotal Cash: €{total_cash}")

                self._update_summary_auto()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error saving denomination: {e}")
            print(f"Error in _on_denom_click: {e}")
            import traceback
            traceback.print_exc()

    # --------- Auto summary update ---------

    def _update_summary_auto(self):
        try:
            # 1. Total cash from notes/coins
            dcc = self.db.fetchone("SELECT total_cash FROM daily_cash_count WHERE date = ?", (self.selected_date,))
            total_cash = float(dcc[0]) if dcc and dcc[0] is not None else 0.0

            # 2. Prev day cash
            prev_day_item = self.cash_summary_table.item(0, 0)
            prev_day_cash = 0.0
            if prev_day_item and prev_day_item.text().strip():
                try:
                    prev_day_cash = float(prev_day_item.text())
                except ValueError:
                    prev_day_cash = 0.0

            # 3. Expenses paid
            exp_result = self.db.fetchone("SELECT COALESCE(SUM(amount),0) FROM daily_expenses WHERE date=? AND status IN ('paid','p')",
                                         (self.selected_date,))
            exp_sum = float(exp_result[0]) if exp_result and exp_result[0] is not None else 0.0

            # 4. Old invoices
            old_result = self.db.fetchone("SELECT COALESCE(SUM(amount),0) FROM old_invoices WHERE date=?", (self.selected_date,))
            old_sum = float(old_result[0]) if old_result and old_result[0] is not None else 0.0

            # 5. Bio cash
            #bio_sum = self.db.fetchone("SELECT COALESCE(SUM(amount),0) FROM bio_cash WHERE date=?", (self.selected_date,))[
              #  0]

            # 6. Coins
            coin_result = self.db.fetchone("""
                   SELECT COALESCE(euro2_total,0)+COALESCE(euro1_total,0)+COALESCE(cent50_total,0)+COALESCE(cent20_total,0)+
                   COALESCE(cent10_total,0)
                   FROM daily_cash_count WHERE date = ?
               """, (self.selected_date,))
            coin_sum = float(coin_result[0]) if coin_result and coin_result[0] is not None else 0.0

            # Final calculations
            total_cash_sell = total_cash - prev_day_cash - exp_sum - old_sum

            # Update table cells - ensure table has enough rows
            if self.cash_summary_table.rowCount() == 0:
                self.cash_summary_table.insertRow(0)
            
            # Ensure we have the required columns
            if self.cash_summary_table.columnCount() < 6:
                return
                
            self.cash_summary_table.setItem(0, 1, self.make_cell(str(total_cash_sell)))
            self.cash_summary_table.setItem(0, 5, self.make_cell(str(coin_sum)))

            self._update_bio_cash_total_display()
            
        except Exception as e:
            print(f"Error in _update_summary_auto: {e}")
            import traceback
            traceback.print_exc()

    def _on_date_changed(self, qdate):
        self.selected_date = qdate.toString("yyyy-MM-dd")
    
    def _calculate_daily_surplus_cash(self):
        try:
            dcc = self.db.fetchone("SELECT total_cash FROM daily_cash_count WHERE date = ?", (self.selected_date,))
            total_cash = float(dcc[0]) if dcc and dcc[0] is not None else 0.0
            cash_summary = self.db.fetchone("SELECT prev_day_cash, terminal_cash FROM daily_cash WHERE date = ?", (self.selected_date,))
            prev_day_cash = float(cash_summary[0]) if cash_summary and cash_summary[0] is not None else 0.0
            terminal_cash = float(cash_summary[1]) if cash_summary and cash_summary[1] is not None else 0.0
            return total_cash - prev_day_cash - terminal_cash
        except Exception:
            return 0.0

    def _calculate_bio_cash_sum(self):
        try:
            result = self.db.fetchone(
                """
                SELECT COALESCE(SUM(amount), 0) FROM bio_cash
                WHERE date = ? AND purpose NOT IN (?, ?)
                """,
                (self.selected_date, DAILY_SURPLUS_PURPOSE, DAILY_SURPLUS_PURPOSE_LEGACY),
            )
            return float(result[0]) if result and result[0] is not None else 0.0
        except Exception:
            return 0.0

    def _update_bio_cash_total_display(self):
        try:
            prev_day_item = self.cash_summary_table.item(0, 0)
            total_cash_sell_item = self.cash_summary_table.item(0, 1)
            total_card_item = self.cash_summary_table.item(0, 3)

            def safe_float(item, default=0.0):
                if item and item.text().strip():
                    try:
                        return float(item.text())
                    except ValueError:
                        return default
                return default

            base_total_daily = (safe_float(total_cash_sell_item) - safe_float(prev_day_item)) + safe_float(total_card_item)
            # Real-time: use table amounts for extra bio rows (not only DB-saved rows)
            extra_sum = self._table_bio_extra_amount_sum()
            total_with_bio = base_total_daily + extra_sum
            total_bio = self._table_total_bio_cash()

            if hasattr(self, "btn_total_bio_cash"):
                self.btn_total_bio_cash.setText(f"€ {total_bio:.2f}")

            if self.cash_summary_table.rowCount() == 0:
                self.cash_summary_table.insertRow(0)
            self._updating_cells = True
            self.cash_summary_table.setItem(0, 7, self.make_cell(f"{total_with_bio:.2f}"))
            self._updating_cells = False
        except Exception as e:
            self._updating_cells = False
            print(f"Error updating bio cash total display: {e}")

    def _on_bio_cash_cell_changed(self, row, column):
        # Row 0 surplus is not user-editable; still refresh totals if structure changes elsewhere
        self._update_bio_cash_total_display()

    def _on_cash_summary_cell_changed(self, row, column):
        """Handle real-time auto-calculation when cash summary cells change"""
        try:
            # Prevent infinite loops during auto-calculation
            if self._updating_cells:
                return
                
            # Only process if we have data in row 0
            if row != 0:
                return
                
            # Get current values from the table
            prev_day_item = self.cash_summary_table.item(0, 0)  # Prev Day Cash
            total_cash_sell_item = self.cash_summary_table.item(0, 1)  # Total Cash Sell
            terminal_cash_item = self.cash_summary_table.item(0, 2)  # Terminal Cash
            total_card_sell_item = self.cash_summary_table.item(0, 3)  # Total Card Sell
            next_day_note_item = self.cash_summary_table.item(0, 4)  # Next Day Cash Note
            next_day_coin_item = self.cash_summary_table.item(0, 5)  # Next Day Cash Coin
            
            # Helper function to safely get float value
            def get_float_value(item, default=0.0):
                if item and item.text().strip():
                    try:
                        return float(item.text())
                    except ValueError:
                        return default
                return default
            
            # Get values
            prev_day_cash = get_float_value(prev_day_item)
            total_cash_sell = get_float_value(total_cash_sell_item)
            terminal_cash = get_float_value(terminal_cash_item)
            total_card_sell = get_float_value(total_card_sell_item)
            next_day_note = get_float_value(next_day_note_item)
            next_day_coin = get_float_value(next_day_coin_item)

            # If both next day note and coin are present, auto-populate Prev Day Cash = note + coin
            # This runs when user edits either column 4 or 5
            if column in (4, 5):
                if (next_day_note_item and next_day_note_item.text().strip() != "") and \
                   (next_day_coin_item and next_day_coin_item.text().strip() != ""):
                    combined_prev = next_day_note + next_day_coin
                    self._updating_cells = True
                    self.cash_summary_table.setItem(0, 0, self.make_cell(f"{combined_prev:.2f}"))
                    self._updating_cells = False
                    prev_day_cash = combined_prev
            
            # Only calculate if we have the required values
            if total_cash_sell > 0:
                # Calculate daily surplus cash: total_cash_sell - prev_day_cash - terminal_cash
                daily_surplus_cash = total_cash_sell - prev_day_cash - terminal_cash

                # Calculate total daily sell: (total_cash_sell - prev_day_cash) + total_card_sell
                total_daily_sell = (total_cash_sell - prev_day_cash) + total_card_sell
                daily_terminal_sell = terminal_cash + total_card_sell

                self._updating_cells = True

                self.cash_summary_table.setItem(0, 6, self.make_cell(f"{daily_terminal_sell:.2f}"))

                self._updating_cells = False

                print(f"Auto-calculated: Daily Surplus Cash: €{daily_surplus_cash:.2f}, Total Daily Sell: €{total_daily_sell:.2f}")

            self._update_bio_cash_total_display()
        except Exception as e:
            print(f"Error in auto-calculation: {e}")
            self._updating_cells = False  # Reset flag on error
    
    def _update_bio_cash_surplus(self, cash_surplus):
        """Update bio cash table with daily cash surplus"""
        try:
            existing_row = -1
            for row in range(self.bio_cash_table.rowCount()):
                purpose_item = self.bio_cash_table.item(row, 0)
                if purpose_item and _is_daily_surplus_purpose(purpose_item.text().strip()):
                    existing_row = row
                    break

            if existing_row >= 0:
                self.bio_cash_table.setItem(existing_row, 0, self.make_cell(DAILY_SURPLUS_PURPOSE))
                self.bio_cash_table.setItem(existing_row, 1, self.make_cell(f"{cash_surplus:.2f}"))
                amt = self.bio_cash_table.item(existing_row, 1)
                if amt:
                    amt.setFlags(amt.flags() & ~Qt.ItemFlag.ItemIsEditable)
            else:
                row = self.bio_cash_table.rowCount()
                self.bio_cash_table.insertRow(row)
                self.bio_cash_table.setItem(row, 0, self.make_cell(DAILY_SURPLUS_PURPOSE))
                surplus_item = self.make_cell(f"{cash_surplus:.2f}")
                surplus_item.setFlags(surplus_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.bio_cash_table.setItem(row, 1, surplus_item)
                self.bio_cash_table.setItem(row, 2, self.make_cell(""))
                self.bio_cash_table.setItem(row, 3, self.make_cell(""))
                created_item = self.make_cell("")
                created_item.setFlags(created_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.bio_cash_table.setItem(row, 4, created_item)

            self._update_bio_cash_total_display()
        except Exception as e:
            print(f"Error updating bio cash surplus: {e}")

    def _open_stats(self):
        self.stats_window = StatWindow(self.db)
        self.stats_window.show()
    
    def _load_data_for_date(self, silent=False):
        """Load all saved data for the selected date. If silent=True, do not show summary message boxes."""
        try:
            has_data = False
            
            # Load Daily Expenses (try both table names for compatibility)
            expenses_data = None
            try:
                expenses_data = self.db.fetchall("""
                    SELECT invoice, amount, status, cash_source, cash_source_date FROM daily_expenses 
                    WHERE date = ? ORDER BY id
                """, (self.selected_date,))
            except:
                # Fallback to original expenses table (without date filter)
                try:
                    expenses_data = self.db.fetchall("""
                        SELECT invoice, amount, status FROM expenses 
                        ORDER BY id
                    """)
                except:
                    expenses_data = []
            
            if expenses_data:
                has_data = True
                self.expenses_table.setRowCount(len(expenses_data))
                for row, data_row in enumerate(expenses_data):
                    # Support both new (with cash source) and legacy (without) schemas
                    if len(data_row) >= 5:
                        invoice, amount, status, cash_source, cash_date = data_row
                    else:
                        invoice, amount, status = data_row
                        cash_source, cash_date = "Current Day", None

                    self.expenses_table.setItem(row, 0, self.make_cell(invoice))
                    self.expenses_table.setItem(row, 1, self.make_cell(str(amount)))
                    self.expenses_table.setItem(row, 2, self.make_cell(status))
                    # Ensure we have a Cash Source widget for this row
                    self._setup_cash_source_cell(self.expenses_table, row, 3, cash_source, cash_date)
            else:
                self.expenses_table.setRowCount(1)
                for col in range(3):
                    self.expenses_table.setItem(0, col, self.make_cell(""))
                # Default Cash Source for the initial empty row
                self._setup_cash_source_cell(self.expenses_table, 0, 3)
            
            # Load Old Invoices
            old_invoices_data = self.db.fetchall("""
                SELECT date, invoice, amount, cash_source, cash_source_date FROM old_invoices 
                WHERE date = ? ORDER BY id
            """, (self.selected_date,))
            
            if old_invoices_data:
                has_data = True
                self.old_invoice_table.setRowCount(len(old_invoices_data))
                for row, data_row in enumerate(old_invoices_data):
                    # Support both new (with cash source) and legacy (without) schemas
                    if len(data_row) >= 5:
                        date, invoice, amount, cash_source, cash_date = data_row
                    else:
                        date, invoice, amount = data_row
                        cash_source, cash_date = "Current Day", None

                    self.old_invoice_table.setItem(row, 0, self.make_cell(date))
                    self.old_invoice_table.setItem(row, 1, self.make_cell(invoice))
                    self.old_invoice_table.setItem(row, 2, self.make_cell(str(amount)))
                    # Ensure we have a Cash Source widget for this row
                    self._setup_cash_source_cell(self.old_invoice_table, row, 3, cash_source, cash_date)
            else:
                self.old_invoice_table.setRowCount(1)
                for col in range(3):
                    self.old_invoice_table.setItem(0, col, self.make_cell(""))
                # Default Cash Source for the initial empty row
                self._setup_cash_source_cell(self.old_invoice_table, 0, 3)

            # Load Cash Summary first so daily surplus can use prev_day / terminal from DB
            cash_summary_data = None
            try:
                cash_summary_data = self.db.fetchone("""
                    SELECT prev_day_cash, total_cash_sell, terminal_cash, total_card_sell,
                           next_day_cash_note, next_day_cash_coin, daily_terminal_sell,
                           total_daily_sell, total_cash_taken, cash_taken_by FROM daily_cash 
                    WHERE date = ?
                """, (self.selected_date,))
            except Exception:
                try:
                    cash_summary_data = self.db.fetchone("""
                        SELECT prev_day_cash, total_cash_sell, total_card_sell,
                               next_day_cash_note, next_day_cash_coin, total_daily_sell,
                               total_cash_taken, cash_taken_by FROM daily_cash 
                        ORDER BY id DESC LIMIT 1
                    """)
                    if cash_summary_data:
                        cash_list = list(cash_summary_data)
                        if len(cash_list) == 8:
                            cash_list.insert(2, 0.0)
                            cash_list.insert(6, 0.0)
                        elif len(cash_list) == 9:
                            cash_list.insert(6, 0.0)
                        cash_summary_data = tuple(cash_list)
                except Exception:
                    cash_summary_data = None

            if cash_summary_data:
                has_data = True
                self.cash_summary_table.setRowCount(1)
                self._updating_cells = True
                for col, value in enumerate(cash_summary_data):
                    if col < 10:
                        self.cash_summary_table.setItem(0, col, self.make_cell(str(value) if value is not None else ""))
                self._updating_cells = False
            else:
                self.cash_summary_table.setRowCount(1)
                self._updating_cells = True
                for col in range(10):
                    self.cash_summary_table.setItem(0, col, self.make_cell(""))
                self._updating_cells = False

            # Load Bio Cash entries (excluding the default daily surplus row)
            bio_cash_data = None
            try:
                bio_cash_data = self.db.fetchall("""
                    SELECT purpose, amount, vendor, sold_by, created_at FROM bio_cash
                    WHERE date = ? AND purpose NOT IN (?, ?) ORDER BY id
                """, (self.selected_date, DAILY_SURPLUS_PURPOSE, DAILY_SURPLUS_PURPOSE_LEGACY))
            except Exception:
                try:
                    bio_cash_data = self.db.fetchall("""
                        SELECT purpose, amount, vendor, sold_by FROM bio_cash
                        ORDER BY id
                    """)
                except Exception:
                    bio_cash_data = []

            saved_surplus = self._fetch_saved_daily_surplus_from_db()
            if saved_surplus is not None:
                surplus_cash = saved_surplus
            else:
                surplus_cash = self._calculate_daily_surplus_cash()
                if surplus_cash is None:
                    surplus_cash = 0.0

            rows = []
            if bio_cash_data:
                has_data = True
                for data_row in bio_cash_data:
                    if len(data_row) >= 5:
                        purpose, amount, vendor, sold_by, created_at = data_row
                    else:
                        purpose, amount, vendor, sold_by = data_row
                        created_at = ""
                    if _is_daily_surplus_purpose(str(purpose)):
                        continue
                    rows.append((purpose, amount, vendor or "", sold_by or "", str(created_at) if created_at else ""))

            self.bio_cash_table.setRowCount(max(1, 1 + len(rows)))

            self.bio_cash_table.setItem(0, 0, self.make_cell(DAILY_SURPLUS_PURPOSE))
            daily_surplus_item = self.make_cell(f"{surplus_cash:.2f}")
            daily_surplus_item.setFlags(daily_surplus_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.bio_cash_table.setItem(0, 1, daily_surplus_item)
            self.bio_cash_table.setItem(0, 2, self.make_cell(""))
            self.bio_cash_table.setItem(0, 3, self.make_cell(""))
            created_item = self.make_cell("")
            created_item.setFlags(created_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.bio_cash_table.setItem(0, 4, created_item)

            for idx, row_data in enumerate(rows, start=1):
                purpose, amount, vendor, sold_by, created_at = row_data
                self.bio_cash_table.setItem(idx, 0, self.make_cell(purpose))
                self.bio_cash_table.setItem(idx, 1, self.make_cell(str(amount)))
                self.bio_cash_table.setItem(idx, 2, self.make_cell(vendor))
                self.bio_cash_table.setItem(idx, 3, self.make_cell(sold_by))
                created_item_r = self.make_cell(created_at)
                created_item_r.setFlags(created_item_r.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.bio_cash_table.setItem(idx, 4, created_item_r)

            self._update_bio_cash_total_display()

            # Show appropriate message
            if not silent:
                if has_data:
                    QMessageBox.information(self, "Data Loaded",
                        f"Successfully loaded all saved data for {self.selected_date}")
                else:
                    QMessageBox.information(self, "No Data Found",
                        f"No Prior Data is Saved on {self.selected_date}")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error loading data: {e}")
            print(f"Error in _load_data_for_date: {e}")
            import traceback
            traceback.print_exc()

    # --------- Table actions (stubs for now) ---------
    def save_expenses(self):
        try:
            for row in range(self.expenses_table.rowCount()):
                invoice = self.expenses_table.item(row, 0)
                amount = self.expenses_table.item(row, 1)
                status = self.expenses_table.item(row, 2)
                cash_widget = self.expenses_table.cellWidget(row, 3)

                if invoice and amount and status and invoice.text().strip() and amount.text().strip():
                    try:
                        amount_value = float(amount.text())
                        # Determine cash source info
                        if isinstance(cash_widget, QComboBox):
                            source_type = "Old Cash" if cash_widget.currentIndex() == 1 else "Current Day"
                            source_date = cash_widget.property("cash_date")
                            if source_type == "Old Cash" and not source_date:
                                # If user picked Old Cash but no date stored, fall back to current selected date
                                source_date = self.selected_date
                        else:
                            source_type = "Current Day"
                            source_date = None

                        self.db.safe_execute("""
                             INSERT INTO daily_expenses (date, invoice, amount, status, cash_source, cash_source_date)
                             VALUES (?, ?, ?, ?, ?, ?)
                         """, (
                             self.selected_date,
                             invoice.text().strip(),
                             amount_value,
                             status.text().strip(),
                             source_type,
                             source_date if source_date else None
                         ))
                    except ValueError:
                        QMessageBox.warning(self, "Invalid Amount", f"Invalid amount in row {row + 1}: {amount.text()}")
                        return
            self.db.conn.commit()
            self._update_summary_auto()
            QMessageBox.information(self, "Saved", "Expenses saved successfully!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error saving expenses: {e}")
            print(f"Error in save_expenses: {e}")
            import traceback
            traceback.print_exc()

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
        # Default Cash Source for new row
        self._setup_cash_source_cell(self.expenses_table, row, 3)

    def save_old_invoices(self):
        try:
            for row in range(self.old_invoice_table.rowCount()):
                date_item = self.old_invoice_table.item(row, 0)
                invoice = self.old_invoice_table.item(row, 1)
                amount = self.old_invoice_table.item(row, 2)
                cash_widget = self.old_invoice_table.cellWidget(row, 3)

                if date_item and invoice and amount and date_item.text().strip() and invoice.text().strip() and amount.text().strip():
                    try:
                        amount_value = float(amount.text())
                        # Determine cash source info
                        if isinstance(cash_widget, QComboBox):
                            source_type = "Old Cash" if cash_widget.currentIndex() == 1 else "Current Day"
                            source_date = cash_widget.property("cash_date")
                            if source_type == "Old Cash" and not source_date:
                                # If user picked Old Cash but no date stored, fall back to selected date in row/date column
                                source_date = date_item.text().strip()
                        else:
                            source_type = "Current Day"
                            source_date = None

                        self.db.safe_execute("""
                            INSERT INTO old_invoices (date, invoice, amount, cash_source, cash_source_date)
                            VALUES (?, ?, ?, ?, ?)
                        """, (
                            date_item.text().strip(),
                            invoice.text().strip(),
                            amount_value,
                            source_type,
                            source_date if source_date else None
                        ))
                    except ValueError:
                        QMessageBox.warning(self, "Invalid Amount", f"Invalid amount in row {row + 1}: {amount.text()}")
                        return
            self.db.conn.commit()
            self._update_summary_auto()
            QMessageBox.information(self, "Saved", "Old invoices saved successfully!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error saving old invoices: {e}")
            print(f"Error in save_old_invoices: {e}")
            import traceback
            traceback.print_exc()

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
        # Default Cash Source for new row
        self._setup_cash_source_cell(self.old_invoice_table, row, 3)

    def save_bio_cash(self):
        try:
            # Persist default daily surplus row for this date (single canonical row)
            surplus_item = self.bio_cash_table.item(0, 1)
            surplus_val = 0.0
            if surplus_item and surplus_item.text().strip():
                try:
                    surplus_val = float(surplus_item.text())
                except ValueError:
                    surplus_val = 0.0
            self.db.safe_execute(
                "DELETE FROM bio_cash WHERE date = ? AND purpose IN (?, ?)",
                (self.selected_date, DAILY_SURPLUS_PURPOSE, DAILY_SURPLUS_PURPOSE_LEGACY),
            )
            self.db.safe_execute(
                """
                INSERT INTO bio_cash (date, purpose, amount, vendor, sold_by)
                VALUES (?, ?, ?, '', '')
                """,
                (self.selected_date, DAILY_SURPLUS_PURPOSE, surplus_val),
            )

            for row in range(self.bio_cash_table.rowCount()):
                purpose = self.bio_cash_table.item(row, 0)
                amount = self.bio_cash_table.item(row, 1)
                vendor = self.bio_cash_table.item(row, 2)
                sold_by = self.bio_cash_table.item(row, 3)
                created_at_item = self.bio_cash_table.item(row, 4)

                if purpose and _is_daily_surplus_purpose(purpose.text().strip()):
                    continue

                if created_at_item and created_at_item.text().strip():
                    continue

                if purpose and amount and purpose.text().strip() and amount.text().strip():
                    try:
                        amount_value = float(amount.text())
                        self.db.safe_execute("""
                            INSERT INTO bio_cash (date, purpose, amount, vendor, sold_by)
                            VALUES (?, ?, ?, ?, ?)
                        """, (
                            self.selected_date,
                            purpose.text().strip(),
                            amount_value,
                            vendor.text().strip() if vendor else "",
                            sold_by.text().strip() if sold_by else ""
                        ))
                    except ValueError:
                        QMessageBox.warning(self, "Invalid Amount", f"Invalid amount in row {row + 1}: {amount.text()}")
                        return

            self.db.conn.commit()

            td_item = self.cash_summary_table.item(0, 7)
            if td_item and td_item.text().strip():
                try:
                    td_val = float(td_item.text())
                    self.db.safe_execute("""
                        INSERT INTO daily_cash (date, total_daily_sell)
                        VALUES (?, ?)
                        ON CONFLICT(date) DO UPDATE SET total_daily_sell = excluded.total_daily_sell
                    """, (self.selected_date, td_val))
                    self.db.conn.commit()
                except ValueError:
                    pass

            self._load_data_for_date(silent=True)
            self._update_bio_cash_total_display()
            QMessageBox.information(self, "Saved", "Bio cash saved successfully!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error saving bio cash: {e}")
            print(f"Error in save_bio_cash: {e}")
            import traceback
            traceback.print_exc()

    def cancel_bio_cash(self):
        row = self.bio_cash_table.currentRow()
        if row <= 0:
            return
        if row >= 0:
            self.bio_cash_table.removeRow(row)
            self._update_bio_cash_total_display()

    def add_bio_cash_row(self):
        if self.bio_cash_table.rowCount() < 1:
            self._init_bio_cash_default_table_state()
        row = self.bio_cash_table.rowCount()
        self.bio_cash_table.insertRow(row)
        self.bio_cash_table.setItem(row, 0, self.make_cell(""))
        self.bio_cash_table.setItem(row, 1, self.make_cell(""))
        self.bio_cash_table.setItem(row, 2, self.make_cell(""))
        self.bio_cash_table.setItem(row, 3, self.make_cell(""))
        self.bio_cash_table.setItem(row, 4, self.make_cell(""))
        self._update_bio_cash_total_display()


    def save_cash_summary(self):
        try:
            # Ensure we have at least one row
            if self.cash_summary_table.rowCount() == 0:
                self.cash_summary_table.insertRow(0)
            
            prev_day = self.cash_summary_table.item(0, 0)
            total_cash_sell = self.cash_summary_table.item(0, 1)
            terminal_cash = self.cash_summary_table.item(0, 2)
            total_card = self.cash_summary_table.item(0, 3)
            next_day_note = self.cash_summary_table.item(0, 4)
            next_day_coin = self.cash_summary_table.item(0, 5)
            daily_terminal_sell = self.cash_summary_table.item(0, 6)
            total_daily = self.cash_summary_table.item(0, 7)
            total_taken = self.cash_summary_table.item(0, 8)
            taken_by = self.cash_summary_table.item(0, 9)

            # Helper function to safely convert to float
            def safe_float(item, default=0.0):
                if item and item.text().strip():
                    try:
                        return float(item.text())
                    except ValueError:
                        return default
                return default

            # Get values
            prev_day_cash = safe_float(prev_day)
            terminal_cash_value = safe_float(terminal_cash)
            total_card_sell = safe_float(total_card)
            
            # Calculate cash surplus, daily terminal sell, and total daily sell automatically
            calculation_result = self.db.calculate_cash_surplus_and_total_daily_sell(
                self.selected_date, terminal_cash_value, prev_day_cash, total_card_sell
            )
            
            if calculation_result:
                # Update the UI with calculated values
                self.cash_summary_table.setItem(0, 6, self.make_cell(str(calculation_result['daily_terminal_sell'])))
                base_total = calculation_result['total_daily_sell']
                bio_sum = self._calculate_bio_cash_sum()
                total_with_bio = base_total + bio_sum
                self.cash_summary_table.setItem(0, 7, self.make_cell(str(total_with_bio)))
                
                # Show the daily surplus cash in a message
                QMessageBox.information(self, "Calculated Values", 
                    f"Daily Surplus Cash: €{calculation_result['daily_surplus_cash']:.2f}\n"
                    f"Daily Terminal Sell: €{calculation_result['daily_terminal_sell']:.2f}\n"
                    f"Total Daily Sell: €{total_with_bio:.2f}")

            # Save all other values to database
            daily_terminal_sell_value = terminal_cash_value + total_card_sell
            total_with_bio = None
            if calculation_result:
                bio_sum = self._calculate_bio_cash_sum()
                total_with_bio = calculation_result['total_daily_sell'] + bio_sum
            self.db.safe_execute("""
                INSERT OR REPLACE INTO daily_cash
                (date, prev_day_cash, total_cash_sell, terminal_cash, total_card_sell,
                 next_day_cash_note, next_day_cash_coin, daily_terminal_sell,
                 total_daily_sell, total_cash_taken, cash_taken_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                self.selected_date,
                prev_day_cash,
                safe_float(total_cash_sell),
                terminal_cash_value,
                total_card_sell,
                safe_float(next_day_note),
                safe_float(next_day_coin),
                daily_terminal_sell_value,
                total_with_bio if total_with_bio is not None else (calculation_result['total_daily_sell'] if calculation_result else safe_float(total_daily)),
                safe_float(total_taken),
                taken_by.text().strip() if taken_by else ""
            ))
            self.db.conn.commit()
            QMessageBox.information(self, "Saved", "Cash Summary saved successfully!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error saving cash summary: {e}")
            print(f"Error in save_cash_summary: {e}")
            import traceback
            traceback.print_exc()

    def cancel_cash_summary(self):
        row = self.cash_summary_table.currentRow()
        if row >= 0:
            self.cash_summary_table.removeRow(row)



if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())
