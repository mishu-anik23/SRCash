import sqlite3
from typing import Tuple, Iterable

DB_FILE = "ecash.db"

# ⚠ WARNING:
# Never use raw symbols like € or "c" directly as SQLite column names.
# Always use this mapping to SAFE names.
DENOM_MAPPING = {
    "€200": ("euro200_qty", "euro200_total", 200.0),
    "€100": ("euro100_qty", "euro100_total", 100.0),
    "€50":  ("euro50_qty",  "euro50_total",  50.0),
    "€20":  ("euro20_qty",  "euro20_total",  20.0),
    "€10":  ("euro10_qty",  "euro10_total",  10.0),
    "€5":   ("euro5_qty",   "euro5_total",    5.0),
    "€2":   ("euro2_qty",   "euro2_total",    2.0),
    "€1":   ("euro1_qty",   "euro1_total",    1.0),
    "50c":  ("cent50_qty",  "cent50_total",   0.5),
    "20c":  ("cent20_qty",  "cent20_total",   0.2),
    "10c":  ("cent10_qty",  "cent10_total",   0.1),
}

COIN_TOTAL_COLS = [DENOM_MAPPING[k][1] for k in ["€2","€1","50c","20c","10c"]]


class DBManager:
    def __init__(self, db_file: str = DB_FILE):
        self.conn = sqlite3.connect(db_file)
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.cursor = self.conn.cursor()
        self._bootstrap()
        self._migrate()

    # ---------- generic helpers ----------
    def safe_execute(self, sql: str, params: Tuple = ()):
        try:
            self.cursor.execute(sql, params)
            self.conn.commit()
            return True
        except Exception as e:
            print(f"[DB ERROR] {e}\nSQL: {sql}\nParams: {params}")
            return False

    def fetchone(self, sql: str, params: Tuple = ()):
        self.cursor.execute(sql, params)
        return self.cursor.fetchone()

    def fetchall(self, sql: str, params: Tuple = ()):
        self.cursor.execute(sql, params)
        return self.cursor.fetchall()

    def _columns(self, table: str) -> set:
        self.cursor.execute(f"PRAGMA table_info({table})")
        return {row[1] for row in self.cursor.fetchall()}

    def _ensure_column(self, table: str, col: str, decl: str):
        if col not in self._columns(table):
            self.safe_execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")

    # ---------- bootstrap (create if missing) ----------
    def _bootstrap(self):
        # Use minimalist CREATEs so we can ALTER later for existing DBs.
        self.safe_execute("""CREATE TABLE IF NOT EXISTS daily_cash_count (id INTEGER PRIMARY KEY AUTOINCREMENT)""")
        self.safe_execute("""CREATE TABLE IF NOT EXISTS daily_expenses (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                date TEXT,
                                invoice TEXT,
                                amount REAL,
                                status TEXT,
                                cash_source TEXT,
                                cash_source_date TEXT,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        self.safe_execute("""CREATE TABLE IF NOT EXISTS old_invoices (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                date TEXT,
                                invoice_date TEXT,
                                invoice TEXT,
                                amount REAL,
                                cash_source TEXT,
                                cash_source_date TEXT,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        self.safe_execute("""CREATE TABLE IF NOT EXISTS bio_cash (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                date TEXT, purpose TEXT, amount REAL, vendor TEXT, sold_by TEXT, daily_cash_surplus REAL DEFAULT 0,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
        self.safe_execute("""CREATE TABLE IF NOT EXISTS daily_cash (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                date TEXT,
                                prev_day_cash REAL DEFAULT 0,
                                total_cash_sell REAL DEFAULT 0,
                                terminal_cash REAL DEFAULT 0,
                                total_card_sell REAL DEFAULT 0,
                                next_day_cash_note REAL DEFAULT 0,
                                next_day_cash_coin REAL DEFAULT 0,
                                daily_terminal_sell REAL DEFAULT 0,
                                total_daily_sell REAL DEFAULT 0,
                                total_cash_taken REAL DEFAULT 0,
                                cash_taken_by TEXT)""")

    # ---------- migrate schemas safely ----------
    def _migrate(self):
        # daily_cash_count required columns
        self._ensure_column("daily_cash_count", "date", "TEXT")
        for _, (qty_col, total_col, _) in DENOM_MAPPING.items():
            self._ensure_column("daily_cash_count", qty_col, "INTEGER DEFAULT 0")
            self._ensure_column("daily_cash_count", total_col, "REAL DEFAULT 0")
        self._ensure_column("daily_cash_count", "total_cash", "REAL DEFAULT 0")
        # Unique index on date for UPSERT
        self.safe_execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_dcc_date ON daily_cash_count(date)")

        # daily_cash: unique date for upsert on summary too
        self._ensure_column("daily_cash", "date", "TEXT")
        self._ensure_column("daily_cash", "prev_day_cash", "REAL DEFAULT 0")
        self._ensure_column("daily_cash", "total_cash_sell", "REAL DEFAULT 0")
        self._ensure_column("daily_cash", "terminal_cash", "REAL DEFAULT 0")
        self._ensure_column("daily_cash", "total_card_sell", "REAL DEFAULT 0")
        self._ensure_column("daily_cash", "next_day_cash_note", "REAL DEFAULT 0")
        self._ensure_column("daily_cash", "next_day_cash_coin", "REAL DEFAULT 0")
        self._ensure_column("daily_cash", "daily_terminal_sell", "REAL DEFAULT 0")
        self._ensure_column("daily_cash", "total_daily_sell", "REAL DEFAULT 0")
        self._ensure_column("daily_cash", "total_cash_taken", "REAL DEFAULT 0")
        self._ensure_column("daily_cash", "cash_taken_by", "TEXT")
        self.safe_execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_dc_date ON daily_cash(date)")
        
        # bio_cash: add daily_cash_surplus column
        self._ensure_column("bio_cash", "daily_cash_surplus", "REAL DEFAULT 0")
        self._ensure_column("bio_cash", "date", "TEXT")
        self._ensure_column("bio_cash", "created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")

        # daily_expenses: add cash source tracking + created_at (persist marker like bio_cash)
        self._ensure_column("daily_expenses", "cash_source", "TEXT")
        self._ensure_column("daily_expenses", "cash_source_date", "TEXT")
        self._ensure_column("daily_expenses", "created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")

        # old_invoices: add cash source tracking + invoice_date + created_at
        self._ensure_column("old_invoices", "cash_source", "TEXT")
        self._ensure_column("old_invoices", "cash_source_date", "TEXT")
        self._ensure_column("old_invoices", "invoice_date", "TEXT")
        self._ensure_column("old_invoices", "created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        # Legacy old_invoices: date was the invoice date; copy into invoice_date for UI column 0
        self.safe_execute(
            "UPDATE old_invoices SET invoice_date = date WHERE invoice_date IS NULL OR TRIM(COALESCE(invoice_date,'')) = ''"
        )

    # ---------- business ops ----------
    def upsert_denomination(self, date_str: str, denom_display: str, qty: int):
        """UPSERT a denomination (qty & subtotal) and update total + coin sum into daily_cash."""
        if denom_display not in DENOM_MAPPING:
            raise ValueError(f"Unknown denomination: {denom_display}")
        qty_col, total_col, value = DENOM_MAPPING[denom_display]
        subtotal = float(qty) * float(value)

        # Insert or increment existing row for this date
        self.safe_execute(
            f"""
            INSERT INTO daily_cash_count (date, {qty_col}, {total_col}, total_cash)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
                {qty_col}   = COALESCE({qty_col},0) + excluded.{qty_col},
                {total_col} = COALESCE({total_col},0) + excluded.{total_col},
                total_cash  = COALESCE(total_cash,0) + excluded.{total_col}
            """,
            (date_str, qty, subtotal, subtotal)
        )

        # Recompute coin sum and write into summary
        self.update_coin_sum_in_summary(date_str)

    def update_coin_sum_in_summary(self, date_str: str):
        if not COIN_TOTAL_COLS:
            return
        cols_csv = ", ".join(COIN_TOTAL_COLS)
        row = self.fetchone(f"SELECT {cols_csv} FROM daily_cash_count WHERE date = ?", (date_str,))
        coin_sum = 0.0
        if row:
            coin_sum = sum(float(v or 0) for v in row)

        # Upsert into daily_cash
        self.safe_execute(
            """
            INSERT INTO daily_cash (date, next_day_cash_coin)
            VALUES (?, ?)
            ON CONFLICT(date) DO UPDATE SET
                next_day_cash_coin = excluded.next_day_cash_coin
            """,
            (date_str, coin_sum)
        )

    def upsert_daily_cash(self, date_str: str, data: dict):
        keys = ", ".join(data.keys())
        placeholders = ", ".join(["?"] * len(data))
        updates = ", ".join([f"{k} = excluded.{k}" for k in data.keys()])
        values = list(data.values())

        self.safe_execute(
            f"""
            INSERT INTO daily_cash (date, {keys})
            VALUES (?, {placeholders})
            ON CONFLICT(date) DO UPDATE SET {updates}
            """,
            [date_str] + values
        )

    # convenience loads
    def fetch_daily_cash_count(self, date_str: str):
        return self.fetchone("SELECT * FROM daily_cash_count WHERE date = ?", (date_str,))

    def fetch_daily_cash(self, date_str: str):
        return self.fetchone("SELECT * FROM daily_cash WHERE date = ?", (date_str,))

    def calculate_cash_surplus_and_total_daily_sell(self, date_str: str, terminal_cash: float, prev_day_cash: float, total_card_sell: float):
        """Calculate cash surplus and total daily sell based on terminal cash and other values"""
        try:
            # Get current total cash sell from daily_cash_count
            dcc = self.fetchone("SELECT total_cash FROM daily_cash_count WHERE date = ?", (date_str,))
            total_cash_from_count = float(dcc[0]) if dcc and dcc[0] is not None else 0.0
            
            # Calculate daily surplus cash: total_cash_sell - prev_day_cash - terminal_cash
            daily_surplus_cash = total_cash_from_count - prev_day_cash - terminal_cash
            
            # Calculate terminal-based daily sell: terminal cash plus card sell
            daily_terminal_sell = terminal_cash + total_card_sell
            
            # Calculate total daily sell: total cash from cash count plus card sell
            total_daily_sell = total_cash_from_count + total_card_sell
            
            # Update daily_cash with calculated values
            self.safe_execute("""
                INSERT INTO daily_cash (date, terminal_cash, total_daily_sell)
                VALUES (?, ?, ?)
                ON CONFLICT(date) DO UPDATE SET
                    terminal_cash = excluded.terminal_cash,
                    total_daily_sell = excluded.total_daily_sell
            """, (date_str, terminal_cash, total_daily_sell))
            
            return {
                'daily_surplus_cash': daily_surplus_cash,
                'daily_terminal_sell': daily_terminal_sell,
                'total_daily_sell': total_daily_sell
            }
            
        except Exception as e:
            print(f"Error in calculate_cash_surplus_and_total_daily_sell: {e}")
            return None

    def close(self):
        self.conn.close()
