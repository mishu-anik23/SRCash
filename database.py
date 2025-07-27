import sqlite3

def get_connection():
    return sqlite3.connect("ecash.db")

def initialize_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute('''CREATE TABLE IF NOT EXISTS daily_cash (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        daily_cash_count TEXT,
        other_sell TEXT,
        prev_day_cash TEXT,
        total_cash_sell TEXT,
        total_card_sell TEXT,
        total_daily_sell TEXT,
        next_day_cash_note TEXT,
        next_day_cash_coin TEXT,
        total_cash_taken TEXT,
        cash_taken_by TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    cur.execute('''CREATE TABLE IF NOT EXISTS daily_cash_count (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        denomination TEXT,
        quantity INTEGER,
        subtotal REAL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    cur.execute('''CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        invoice TEXT,
        amount REAL,
        status TEXT
    )''')

    cur.execute('''CREATE TABLE IF NOT EXISTS old_invoices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        invoice TEXT,
        amount REAL
    )''')

    cur.execute('''CREATE TABLE IF NOT EXISTS bio_cash (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        purpose TEXT,
        amount REAL,
        vendor TEXT,
        sold_by TEXT
    )''')

    conn.commit()
    conn.close()

if __name__ == '__main__':
    conn = get_connection()
    cur = conn.cursor()
    #cur.execute("DROP table daily_cash_count")
    cur.execute("Select * from daily_cash_count")
    print(cur.fetchall())
