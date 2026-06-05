# tests/test_database.py
import os
import pytest
from src.core.database import ExpenseDB, CategoryNotFoundError, AccountNotFoundError

def test_database_empty_categories_and_accounts_init():
    db_path = "test_temp_cats.db"
    if os.path.exists(db_path):
        os.remove(db_path)
        
    try:
        db = ExpenseDB(db_path)
        # Check that categories and accounts start completely empty
        assert len(db.get_categories()) == 0
        assert len(db.get_accounts()) == 0
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)

def test_database_account_not_found():
    db_path = "test_temp_acc_validation.db"
    if os.path.exists(db_path):
        os.remove(db_path)
        
    try:
        db = ExpenseDB(db_path)
        # Category exists but account does not
        db.add_category("food")
        
        with pytest.raises(AccountNotFoundError):
            db.add_transaction(100.0, "expense", "cash", "food", "lunch")
            
        # Add account and try again
        db.add_account("cash")
        tx_id = db.add_transaction(100.0, "expense", "cash", "food", "lunch")
        assert tx_id > 0
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)

def test_database_category_not_found():
    db_path = "test_temp_validation.db"
    if os.path.exists(db_path):
        os.remove(db_path)
        
    try:
        db = ExpenseDB(db_path)
        # Account exists but category does not
        db.add_account("cash")
        
        with pytest.raises(CategoryNotFoundError):
            db.add_transaction(100.0, "expense", "cash", "food", "lunch")
            
        # Create category and try again
        db.add_category("food")
        tx_id = db.add_transaction(100.0, "expense", "cash", "food", "lunch")
        assert tx_id > 0
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)

def test_database_undo():
    db_path = "test_temp.db"
    if os.path.exists(db_path):
        os.remove(db_path)
        
    try:
        db = ExpenseDB(db_path)
        
        # Must register accounts and categories first
        db.add_account("cash")
        db.add_account("bank")
        db.add_category("food")
        db.add_category("salary")
        
        # Add a couple of transactions (amount, type, account, category, description)
        tx1_id = db.add_transaction(100.0, "expense", "cash", "food", "lunch")
        tx2_id = db.add_transaction(200.0, "income", "bank", "salary", "bonus")
        
        # Last transaction should be tx2
        tx = db.delete_last_transaction()
        assert tx is not None
        assert tx["id"] == tx2_id
        assert tx["amount"] == 200.0
        assert tx["type"] == "income"
        assert tx["account"] == "bank"
        assert tx["category"] == "salary"
        assert tx["description"] == "bonus"
        
        # Next last transaction should be tx1
        tx = db.delete_last_transaction()
        assert tx is not None
        assert tx["id"] == tx1_id
        assert tx["amount"] == 100.0
        assert tx["account"] == "cash"
        
        # No transactions left to undo
        assert db.delete_last_transaction() is None
        
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)
