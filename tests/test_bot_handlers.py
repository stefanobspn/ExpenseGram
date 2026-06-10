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
