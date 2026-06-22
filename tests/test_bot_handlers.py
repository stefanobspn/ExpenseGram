# tests/test_bot_handlers.py
import os
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from telegram import Update, User, Message, Chat
from telegram.ext import Application

from src.core.database import ExpenseDB
from src.telegram_bot import handlers


@pytest.fixture
def temp_db():
    db_path = "test_handlers_temp.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    db = ExpenseDB(db_path)
    # Create test items
    db.add_account("cash")
    db.add_category("food")
    yield db
    if os.path.exists(db_path):
        os.remove(db_path)


def make_mock_update_and_context(db, text="", user_id=123456):
    # Mock Update
    user = MagicMock(spec=User)
    user.id = user_id

    chat = MagicMock(spec=Chat)
    chat.id = 123456

    message = MagicMock(spec=Message)
    message.text = text
    message.reply_text = AsyncMock()
    message.reply_document = AsyncMock()

    update = MagicMock(spec=Update)
    update.effective_user = user
    update.effective_chat = chat
    update.message = message

    # Mock Context
    context = MagicMock()
    # Mock application's bot_data dictionary
    application = MagicMock(spec=Application)
    application.bot_data = {"db": db}
    context.application = application
    context.user_data = {}
    context.args = []

    return update, context


@pytest.mark.anyio
@patch("src.core.config.Config.TELEGRAM_OWNER_ID", "123456")
async def test_nuke_command_no_transactions(temp_db):
    update, context = make_mock_update_and_context(temp_db, "/nuke")
    await handlers.nuke_command(update, context)

    update.message.reply_text.assert_called_once()
    assert "No transactions found" in update.message.reply_text.call_args[0][0]
    assert not context.user_data.get("nuke_pending")


@pytest.mark.anyio
@patch("src.core.config.Config.TELEGRAM_OWNER_ID", "123456")
async def test_nuke_command_with_transactions_confirm(temp_db):
    temp_db.add_transaction(100.0, "expense", "cash", "food", "lunch")

    # Trigger /nuke
    update, context = make_mock_update_and_context(temp_db, "/nuke")
    await handlers.nuke_command(update, context)

    update.message.reply_text.assert_called_once()
    assert "WARNING: Permanent Data Loss!" in update.message.reply_text.call_args[0][0]
    assert context.user_data.get("nuke_pending") is True

    # Type "I understand"
    confirm_update, _ = make_mock_update_and_context(temp_db, "I understand")
    # Share user_data to mock session state
    confirm_context = MagicMock()
    confirm_context.application = context.application
    confirm_context.user_data = context.user_data

    await handlers.handle_transaction_message(confirm_update, confirm_context)
    confirm_update.message.reply_text.assert_called_once()
    assert "Nuke Successful!" in confirm_update.message.reply_text.call_args[0][0]
    assert confirm_context.user_data.get("nuke_pending") is False
    assert len(temp_db.get_history()) == 0


@pytest.mark.anyio
@patch("src.core.config.Config.TELEGRAM_OWNER_ID", "123456")
async def test_nuke_command_with_transactions_cancel(temp_db):
    temp_db.add_transaction(100.0, "expense", "cash", "food", "lunch")

    # Trigger /nuke
    update, context = make_mock_update_and_context(temp_db, "/nuke")
    await handlers.nuke_command(update, context)
    assert context.user_data.get("nuke_pending") is True

    # Type "no"
    cancel_update, _ = make_mock_update_and_context(temp_db, "no")
    cancel_context = MagicMock()
    cancel_context.application = context.application
    cancel_context.user_data = context.user_data

    await handlers.handle_transaction_message(cancel_update, cancel_context)
    cancel_update.message.reply_text.assert_called_once()
    assert "Nuke Cancelled" in cancel_update.message.reply_text.call_args[0][0]
    assert cancel_context.user_data.get("nuke_pending") is False
    assert len(temp_db.get_history()) == 1


@pytest.mark.anyio
@patch("src.core.config.Config.TELEGRAM_OWNER_ID", "123456")
async def test_nuke_command_cleared_by_other_command(temp_db):
    temp_db.add_transaction(100.0, "expense", "cash", "food", "lunch")

    # Trigger /nuke
    update, context = make_mock_update_and_context(temp_db, "/nuke")
    await handlers.nuke_command(update, context)
    assert context.user_data.get("nuke_pending") is True

    # Run /history
    history_update, _ = make_mock_update_and_context(temp_db, "/history")
    history_context = MagicMock()
    history_context.application = context.application
    history_context.user_data = context.user_data
    history_context.args = []

    await handlers.history_command(history_update, history_context)
    assert history_context.user_data.get("nuke_pending") is False
    assert len(temp_db.get_history()) == 1


@pytest.mark.anyio
@patch("src.core.config.Config.TELEGRAM_OWNER_ID", "123456")
async def test_category_command_handlers(temp_db):
    # Test list categories empty
    update, context = make_mock_update_and_context(temp_db, "/categories")
    # Clean database first by removing defaults
    temp_db.delete_category("food", "expense")
    await handlers.list_categories(update, context)
    update.message.reply_text.assert_called_once_with("🗂️ No categories found.")

    # Test add category usage
    update, context = make_mock_update_and_context(temp_db, "/addcategory")
    await handlers.add_category(update, context)
    assert "Usage: `/addcategory" in update.message.reply_text.call_args[0][0]

    # Test add category invalid type
    update, context = make_mock_update_and_context(temp_db, "/addcategory invalid food")
    context.args = ["invalid", "food"]
    await handlers.add_category(update, context)
    assert "Invalid type" in update.message.reply_text.call_args[0][0]

    # Test add category success (expense)
    update, context = make_mock_update_and_context(temp_db, "/addcategory expense food")
    context.args = ["expense", "food"]
    await handlers.add_category(update, context)
    assert "added" in update.message.reply_text.call_args[0][0]
    assert "food" in temp_db.get_categories("expense")

    # Test add category success (income)
    update, context = make_mock_update_and_context(
        temp_db, "/addcategory income salary"
    )
    context.args = ["income", "salary"]
    await handlers.add_category(update, context)
    assert "added" in update.message.reply_text.call_args[0][0]
    assert "salary" in temp_db.get_categories("income")

    # Test list categories
    update, context = make_mock_update_and_context(temp_db, "/categories")
    await handlers.list_categories(update, context)
    reply = update.message.reply_text.call_args[0][0]
    assert "Income" in reply
    assert "Expenses" in reply
    assert "salary" in reply
    assert "food" in reply

    # Test del category usage
    update, context = make_mock_update_and_context(temp_db, "/delcategory")
    await handlers.del_category(update, context)
    assert "Usage: `/delcategory" in update.message.reply_text.call_args[0][0]

    # Test del category success
    update, context = make_mock_update_and_context(temp_db, "/delcategory expense food")
    context.args = ["expense", "food"]
    await handlers.del_category(update, context)
    assert "deleted successfully" in update.message.reply_text.call_args[0][0]
    assert "food" not in temp_db.get_categories("expense")


@pytest.mark.anyio
@patch("src.core.config.Config.TELEGRAM_OWNER_ID", "123456")
async def test_report_command_with_transfer(temp_db):
    # Add another account
    temp_db.add_account("bank")
    # Add an income category
    temp_db.add_category("salary", "income")

    # Add income transaction
    temp_db.add_transaction(1000000.0, "income", "bank", "salary")

    # Add expense transaction
    temp_db.add_transaction(200000.0, "expense", "cash", "food")

    # Add transfer transaction (cash -> bank)
    temp_db.add_transfer("cash", "bank", 100000.0, "transfer deposit")

    update, context = make_mock_update_and_context(temp_db, "/report")
    await handlers.report_command(update, context)

    update.message.reply_text.assert_called_once()
    reply = update.message.reply_text.call_args[0][0]

    assert "**Total Income:** `1,000,000.00`" in reply
    assert "**Total Expenses:** `200,000.00`" in reply
    assert "Net Savings:** `+800,000.00`" in reply
    assert "💳 **Account Balances:**" in reply
    assert "• bank: `1,100,000.00`" in reply
    assert "• cash: `-300,000.00`" in reply
    # "transfer" should only appear in account names/description but not as a category in report
    # Wait, the category 'transfer' is in the DB but shouldn't be listed in the category breakdowns
    # The string `• transfer: ` or category name breakdowns shouldn't exist.
    # To avoid matching "transfer deposit" or general transfer words, we can check that it's not listed as a category breakdown
    assert "• transfer:" not in reply.lower()
