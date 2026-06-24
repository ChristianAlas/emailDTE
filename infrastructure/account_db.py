import sqlite3
from datetime import datetime


class AccountDB:
    def __init__(self, db_path='accounts.db'):
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.init_db()

    def init_db(self):
        c = self.conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY,
                email TEXT UNIQUE,
                password TEXT,
                imap_server TEXT,
                imap_port INTEGER,
                use_ssl INTEGER,
                provider TEXT,
                note TEXT,
                created_at TEXT
            )
        ''')
        self.conn.commit()

    def add_account(self, email, password, imap_server, imap_port=993, use_ssl=1, provider='', note=''):
        c = self.conn.cursor()
        now = datetime.utcnow().isoformat()
        c.execute(
            'INSERT INTO accounts (email, password, imap_server, imap_port, use_ssl, provider, note, created_at) VALUES (?,?,?,?,?,?,?,?)',
            (email, password, imap_server, imap_port, int(bool(use_ssl)), provider, note, now)
        )
        self.conn.commit()
        return c.lastrowid

    def update_account(self, account_id, email, password, imap_server, imap_port=993, use_ssl=1, provider='', note=''):
        c = self.conn.cursor()
        c.execute(
            'UPDATE accounts SET email=?, password=?, imap_server=?, imap_port=?, use_ssl=?, provider=?, note=? WHERE id=?',
            (email, password, imap_server, imap_port, int(bool(use_ssl)), provider, note, account_id)
        )
        self.conn.commit()

    def delete_account(self, account_id):
        c = self.conn.cursor()
        c.execute('DELETE FROM accounts WHERE id=?', (account_id,))
        self.conn.commit()

    def list_accounts(self):
        c = self.conn.cursor()
        c.execute('SELECT * FROM accounts ORDER BY email')
        rows = c.fetchall()
        return [dict(r) for r in rows]

    def get_account(self, account_id):
        c = self.conn.cursor()
        c.execute('SELECT * FROM accounts WHERE id=?', (account_id,))
        row = c.fetchone()
        return dict(row) if row else None

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass
