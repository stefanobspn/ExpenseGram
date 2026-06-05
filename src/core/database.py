# src/core/database.py
import sqlite3
from datetime import datetime
from typing import List, Tuple, Dict, Any, Optional

class CategoryNotFoundError(Exception):
    """Raised when trying to log a transaction with a non-existent category."""
    pass

class AccountNotFoundError(Exception):
    """Raised when trying to log a transaction with a non-existent account."""
    pass


class ExpenseDB:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        """Initialize database tables if they do not exist."""
        with self._get_conn() as conn:
            # Create categories table (starts empty)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL
                );
            """)
            
            # Create accounts table (starts empty)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL
                );
            """)
            
            # Create transactions table including account column
            conn.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    amount REAL NOT NULL,
                    type TEXT NOT NULL,
                    account TEXT NOT NULL,
                    category TEXT NOT NULL,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # Migration check: if 'account' column is missing in transactions, alter schema
            cursor = conn.execute("PRAGMA table_info(transactions)")
            columns = [row["name"] for row in cursor.fetchall()]
            if "account" not in columns:
                conn.execute("ALTER TABLE transactions ADD COLUMN account TEXT NOT NULL DEFAULT 'cash'")
            
            # Re-sync accounts table: populate accounts table with any distinct accounts already in transactions
            conn.execute("""
                INSERT OR IGNORE INTO accounts (name)
                SELECT DISTINCT account FROM transactions;
            """)
            
            conn.commit()

    # Category operations
    def get_categories(self) -> List[str]:
        """Get all categories sorted alphabetically."""
        with self._get_conn() as conn:
            cursor = conn.execute("SELECT name FROM categories ORDER BY name ASC")
            return [row["name"] for row in cursor.fetchall()]

    def add_category(self, name: str) -> bool:
        """Add a new category. Returns True if successful, False if already exists."""
        name = name.strip().lower()
        if not name:
            return False
        try:
            with self._get_conn() as conn:
                conn.execute("INSERT INTO categories (name) VALUES (?)", (name,))
                conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def delete_category(self, name: str) -> Tuple[bool, str]:
        """Delete an unused category. Returns (success, message)."""
        name = name.strip().lower()
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) as count FROM transactions WHERE category = ?", 
                (name,)
            )
            count = cursor.fetchone()["count"]
            if count > 0:
                return False, f"Category '{name}' is in use by {count} transaction(s) and cannot be deleted."
            
            cursor = conn.execute("DELETE FROM categories WHERE name = ?", (name,))
            conn.commit()
            if cursor.rowcount > 0:
                return True, f"Category '{name}' deleted successfully."
            else:
                return False, f"Category '{name}' not found."

    # Account operations
    def get_accounts(self) -> List[str]:
        """Get all accounts sorted alphabetically."""
        with self._get_conn() as conn:
            cursor = conn.execute("SELECT name FROM accounts ORDER BY name ASC")
            return [row["name"] for row in cursor.fetchall()]

    def add_account(self, name: str) -> bool:
        """Add a new account. Returns True if successful, False if already exists."""
        name = name.strip().lower()
        if not name:
            return False
        try:
            with self._get_conn() as conn:
                conn.execute("INSERT INTO accounts (name) VALUES (?)", (name,))
                conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def delete_account(self, name: str) -> Tuple[bool, str]:
        """Delete an unused account. Returns (success, message)."""
        name = name.strip().lower()
        with self._get_conn() as conn:
            # Check if referenced in transactions
            cursor = conn.execute(
                "SELECT COUNT(*) as count FROM transactions WHERE account = ?", 
                (name,)
            )
            count = cursor.fetchone()["count"]
            if count > 0:
                return False, f"Account '{name}' is in use by {count} transaction(s) and cannot be deleted."
            
            cursor = conn.execute("DELETE FROM accounts WHERE name = ?", (name,))
            conn.commit()
            if cursor.rowcount > 0:
                return True, f"Account '{name}' deleted successfully."
            else:
                return False, f"Account '{name}' not found."

    # Transaction operations
    def add_transaction(
        self, 
        amount: float, 
        tx_type: str, 
        account: str,
        category: str, 
        description: Optional[str] = None
    ) -> int:
        """Add a transaction. If the category or account does not exist, raises appropriate exceptions."""
        category = category.strip().lower()
        tx_type = tx_type.strip().lower()
        account = account.strip().lower()
        description = description.strip() if description else None

        with self._get_conn() as conn:
            # Validate account existence
            cursor = conn.execute("SELECT 1 FROM accounts WHERE name = ?", (account,))
            if not cursor.fetchone():
                raise AccountNotFoundError(f"Account '{account}' does not exist. You must create it first.")

            # Validate category existence
            cursor = conn.execute("SELECT 1 FROM categories WHERE name = ?", (category,))
            if not cursor.fetchone():
                raise CategoryNotFoundError(f"Category '{category}' does not exist. You must create it first.")

            cursor = conn.execute(
                """
                INSERT INTO transactions (amount, type, account, category, description, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (amount, tx_type, account, category, description, datetime.now())
            )
            conn.commit()
            return cursor.lastrowid

    def delete_transaction(self, tx_id: int) -> bool:
        """Delete a transaction by ID. Returns True if a row was deleted."""
        with self._get_conn() as conn:
            cursor = conn.execute("DELETE FROM transactions WHERE id = ?", (tx_id,))
            conn.commit()
            return cursor.rowcount > 0

    def delete_last_transaction(self) -> Optional[Dict[str, Any]]:
        """Deletes the latest transaction. Returns its details if successful, or None."""
        with self._get_conn() as conn:
            # Find the most recent transaction
            cursor = conn.execute(
                "SELECT id, amount, type, account, category, description FROM transactions ORDER BY created_at DESC, id DESC LIMIT 1"
            )
            row = cursor.fetchone()
            if not row:
                return None
            
            tx = dict(row)
            conn.execute("DELETE FROM transactions WHERE id = ?", (tx["id"],))
            conn.commit()
            return tx

    def get_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent transactions."""
        with self._get_conn() as conn:
            cursor = conn.execute(
                """
                SELECT id, amount, type, account, category, description, created_at
                FROM transactions
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (limit,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_monthly_report(self, year: int, month: int) -> List[Dict[str, Any]]:
        """Get category aggregated stats for a month."""
        date_pattern = f"{year:04d}-{month:02d}%"
        with self._get_conn() as conn:
            cursor = conn.execute(
                """
                SELECT category, type, SUM(amount) as total
                FROM transactions
                WHERE created_at LIKE ?
                GROUP BY category, type
                ORDER BY type DESC, total DESC
                """,
                (date_pattern,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_all_transactions_for_export(self) -> List[Dict[str, Any]]:
        """Get all transactions sorted chronologically for exporting to CSV."""
        with self._get_conn() as conn:
            cursor = conn.execute(
                """
                SELECT id, amount, type, account, category, description, created_at
                FROM transactions
                ORDER BY created_at ASC, id ASC
                """
            )
            return [dict(row) for row in cursor.fetchall()]
