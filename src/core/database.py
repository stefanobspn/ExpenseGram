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
            # Create/migrate categories table
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='categories'"
            )
            table_exists = cursor.fetchone() is not None

            if table_exists:
                cursor = conn.execute("PRAGMA table_info(categories)")
                columns = [row["name"] for row in cursor.fetchall()]
                if "type" not in columns:
                    conn.execute("ALTER TABLE categories RENAME TO categories_old;")
                    conn.execute("""
                        CREATE TABLE categories (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            name TEXT NOT NULL,
                            type TEXT NOT NULL DEFAULT 'expense',
                            UNIQUE (name, type)
                        );
                    """)
                    conn.execute("""
                        INSERT INTO categories (id, name, type)
                        SELECT id, name, 'expense' FROM categories_old;
                    """)
                    conn.execute("DROP TABLE categories_old;")

                    # Update category type based on existing transactions:
                    conn.execute("""
                        UPDATE categories SET type = 'income'
                        WHERE name IN (
                            SELECT category FROM transactions WHERE type = 'income'
                            EXCEPT
                            SELECT category FROM transactions WHERE type = 'expense'
                        );
                    """)
            else:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS categories (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        type TEXT NOT NULL DEFAULT 'expense',
                        UNIQUE (name, type)
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
                conn.execute(
                    "ALTER TABLE transactions ADD COLUMN account TEXT NOT NULL DEFAULT 'cash'"
                )

            # Re-sync accounts table: populate accounts table with any distinct accounts already in transactions
            conn.execute("""
                INSERT OR IGNORE INTO accounts (name)
                SELECT DISTINCT account FROM transactions;
            """)

            conn.commit()

    # Category operations
    def get_categories(self, tx_type: Optional[str] = None) -> List[str]:
        """Get all categories sorted alphabetically, optionally filtered by type."""
        with self._get_conn() as conn:
            if tx_type:
                cursor = conn.execute(
                    "SELECT name FROM categories WHERE type = ? ORDER BY name ASC",
                    (tx_type,),
                )
            else:
                cursor = conn.execute(
                    "SELECT DISTINCT name FROM categories ORDER BY name ASC"
                )
            return [row["name"] for row in cursor.fetchall()]

    def get_categories_by_type(self) -> Dict[str, List[str]]:
        """Get all categories grouped by their type."""
        categories = {"income": [], "expense": []}
        with self._get_conn() as conn:
            cursor = conn.execute("SELECT name, type FROM categories ORDER BY name ASC")
            for row in cursor.fetchall():
                t = row["type"]
                if t in categories:
                    categories[t].append(row["name"])
        return categories

    def add_category(self, name: str, cat_type: str = "expense") -> bool:
        """Add a new category. Returns True if successful, False if already exists."""
        name = name.strip().lower()
        cat_type = cat_type.strip().lower()
        if not name or cat_type not in ("expense", "income"):
            return False
        try:
            with self._get_conn() as conn:
                conn.execute(
                    "INSERT INTO categories (name, type) VALUES (?, ?)",
                    (name, cat_type),
                )
                conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def delete_category(self, name: str, cat_type: str = "expense") -> Tuple[bool, str]:
        """Delete an unused category. Returns (success, message)."""
        name = name.strip().lower()
        cat_type = cat_type.strip().lower()
        with self._get_conn() as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) as count FROM transactions WHERE category = ? AND type = ?",
                (name, cat_type),
            )
            count = cursor.fetchone()["count"]
            if count > 0:
                return (
                    False,
                    f"Category '{name}' ({cat_type}) is in use by {count} transaction(s) and cannot be deleted.",
                )

            cursor = conn.execute(
                "DELETE FROM categories WHERE name = ? AND type = ?", (name, cat_type)
            )
            conn.commit()
            if cursor.rowcount > 0:
                return True, f"Category '{name}' ({cat_type}) deleted successfully."
            else:
                return False, f"Category '{name}' ({cat_type}) not found."

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
                "SELECT COUNT(*) as count FROM transactions WHERE account = ?", (name,)
            )
            count = cursor.fetchone()["count"]
            if count > 0:
                return (
                    False,
                    f"Account '{name}' is in use by {count} transaction(s) and cannot be deleted.",
                )

            cursor = conn.execute("DELETE FROM accounts WHERE name = ?", (name,))
            conn.commit()
            if cursor.rowcount > 0:
                return True, f"Account '{name}' deleted successfully."
            else:
                return False, f"Account '{name}' not found."

    def get_account_balances(self) -> Dict[str, float]:
        """Calculate the current balance for all accounts."""
        balances = {}
        with self._get_conn() as conn:
            # First, initialize all existing accounts with 0.0 balance
            cursor = conn.execute("SELECT name FROM accounts")
            for row in cursor.fetchall():
                balances[row["name"]] = 0.0

            # Calculate sum of income / transfer_in
            cursor = conn.execute("""
                SELECT account, SUM(amount) as total
                FROM transactions
                WHERE type IN ('income', 'transfer_in')
                GROUP BY account
            """)
            for row in cursor.fetchall():
                acc = row["account"]
                balances[acc] = balances.get(acc, 0.0) + row["total"]

            # Subtract sum of expense / transfer_out
            cursor = conn.execute("""
                SELECT account, SUM(amount) as total
                FROM transactions
                WHERE type IN ('expense', 'transfer_out')
                GROUP BY account
            """)
            for row in cursor.fetchall():
                acc = row["account"]
                balances[acc] = balances.get(acc, 0.0) - row["total"]

        return balances

    # Transaction operations
    def add_transaction(
        self,
        amount: float,
        tx_type: str,
        account: str,
        category: str,
        description: Optional[str] = None,
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
                raise AccountNotFoundError(
                    f"Account '{account}' does not exist. You must create it first."
                )

            # Validate category existence and type
            if tx_type in ("income", "expense"):
                cursor = conn.execute(
                    "SELECT type FROM categories WHERE name = ?", (category,)
                )
                rows = cursor.fetchall()
                if not rows:
                    raise CategoryNotFoundError(
                        f"Category '{category}' does not exist. You must create it first."
                    )
                types = [r["type"] for r in rows]
                if tx_type not in types:
                    raise CategoryNotFoundError(
                        f"Category '{category}' is not registered as an '{tx_type}' category (it is registered as '{types[0]}')."
                    )
            else:
                # Fallback/validation for other transaction types (e.g. transfers)
                cursor = conn.execute(
                    "SELECT 1 FROM categories WHERE name = ?", (category,)
                )
                if not cursor.fetchone():
                    raise CategoryNotFoundError(
                        f"Category '{category}' does not exist. You must create it first."
                    )

            cursor = conn.execute(
                """
                INSERT INTO transactions (amount, type, account, category, description, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (amount, tx_type, account, category, description, datetime.now()),
            )
            conn.commit()
            return cursor.lastrowid

    def add_transfer(
        self,
        from_account: str,
        to_account: str,
        amount: float,
        description: Optional[str] = None,
    ) -> Tuple[int, int]:
        """
        Record a transfer from one account to another.
        Creates two linked transactions under a single DB transaction.
        Returns the IDs of the two created transactions (from_id, to_id).
        """
        from_account = from_account.strip().lower()
        to_account = to_account.strip().lower()
        description = description.strip() if description else None

        if from_account == to_account:
            raise ValueError("Source and destination accounts must be different.")

        if amount <= 0:
            raise ValueError("Transfer amount must be greater than zero.")

        with self._get_conn() as conn:
            # Validate source account existence
            cursor = conn.execute(
                "SELECT 1 FROM accounts WHERE name = ?", (from_account,)
            )
            if not cursor.fetchone():
                raise AccountNotFoundError(
                    f"Source account '{from_account}' does not exist."
                )

            # Validate destination account existence
            cursor = conn.execute(
                "SELECT 1 FROM accounts WHERE name = ?", (to_account,)
            )
            if not cursor.fetchone():
                raise AccountNotFoundError(
                    f"Destination account '{to_account}' does not exist."
                )

            # Automatically ensure the 'transfer' category exists
            conn.execute("INSERT OR IGNORE INTO categories (name) VALUES ('transfer')")

            now = datetime.now()

            # 1. Outflow from source account
            desc_from = f"Transfer to {to_account}"
            if description:
                desc_from += f": {description}"
            cursor = conn.execute(
                """
                INSERT INTO transactions (amount, type, account, category, description, created_at)
                VALUES (?, 'transfer_out', ?, 'transfer', ?, ?)
                """,
                (amount, from_account, desc_from, now),
            )
            from_id = cursor.lastrowid

            # 2. Inflow to destination account
            desc_to = f"Transfer from {from_account}"
            if description:
                desc_to += f": {description}"
            cursor = conn.execute(
                """
                INSERT INTO transactions (amount, type, account, category, description, created_at)
                VALUES (?, 'transfer_in', ?, 'transfer', ?, ?)
                """,
                (amount, to_account, desc_to, now),
            )
            to_id = cursor.lastrowid

            conn.commit()
            return from_id, to_id

    def delete_transaction(self, tx_id: int) -> bool:
        """Delete a transaction by ID. If it is a transfer, also deletes its counterpart."""
        with self._get_conn() as conn:
            # Check if this transaction is a transfer
            cursor = conn.execute(
                "SELECT amount, type, created_at FROM transactions WHERE id = ?",
                (tx_id,),
            )
            row = cursor.fetchone()
            if not row:
                return False

            tx_type = row["type"]
            amount = row["amount"]
            created_at = row["created_at"]

            # Delete target transaction
            conn.execute("DELETE FROM transactions WHERE id = ?", (tx_id,))

            # If it's a transfer, also delete counterpart
            if tx_type in ("transfer_in", "transfer_out"):
                other_type = (
                    "transfer_out" if tx_type == "transfer_in" else "transfer_in"
                )
                conn.execute(
                    """
                    DELETE FROM transactions 
                    WHERE type = ? AND amount = ? AND created_at = ? AND id != ?
                    """,
                    (other_type, amount, created_at, tx_id),
                )
            conn.commit()
            return True

    def delete_last_transaction(self) -> Optional[List[Dict[str, Any]]]:
        """Deletes the latest transaction (or transaction pair if it was a transfer). Returns details."""
        with self._get_conn() as conn:
            # Find the most recent transaction
            cursor = conn.execute(
                "SELECT id, amount, type, account, category, description, created_at FROM transactions ORDER BY created_at DESC, id DESC LIMIT 1"
            )
            row = cursor.fetchone()
            if not row:
                return None

            tx1 = dict(row)
            deleted_txs = [tx1]

            # If it's a transfer, delete counterpart as well
            if tx1["type"] in ("transfer_in", "transfer_out"):
                other_type = (
                    "transfer_out" if tx1["type"] == "transfer_in" else "transfer_in"
                )
                cursor = conn.execute(
                    """
                    SELECT id, amount, type, account, category, description, created_at 
                    FROM transactions 
                    WHERE type = ? AND amount = ? AND created_at = ? AND id != ?
                    """,
                    (other_type, tx1["amount"], tx1["created_at"], tx1["id"]),
                )
                row2 = cursor.fetchone()
                if row2:
                    tx2 = dict(row2)
                    deleted_txs.append(tx2)

            # Delete all collected transaction IDs
            ids_to_delete = [tx["id"] for tx in deleted_txs]
            placeholders = ",".join("?" for _ in ids_to_delete)
            conn.execute(
                f"DELETE FROM transactions WHERE id IN ({placeholders})", ids_to_delete
            )
            conn.commit()

            return deleted_txs

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
                (limit,),
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
                (date_pattern,),
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

    def delete_all_transactions(self) -> int:
        """Delete all transactions from the database. Returns the number of deleted rows."""
        with self._get_conn() as conn:
            cursor = conn.execute("DELETE FROM transactions")
            count = cursor.rowcount
            conn.commit()
            return count
