# src/telegram_bot/handlers.py
import io
import csv
import calendar
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes

from src.core.config import Config
from src.core.parser import parse_transaction, parse_amount
from src.core.database import CategoryNotFoundError, AccountNotFoundError
from src.telegram_bot.middleware import owner_required

logger = logging.getLogger(__name__)


def get_db(context: ContextTypes.DEFAULT_TYPE):
    """Retrieve database instance from application context data."""
    return context.application.bot_data["db"]


@owner_required
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Welcome user and show ID setup if owner is not yet configured."""
    owner_id_str = Config.TELEGRAM_OWNER_ID
    user_id = update.effective_user.id

    if not owner_id_str:
        await update.message.reply_text(
            f"👋 Welcome to **ExpenseGram**!\n\n"
            f"To restrict this bot to you only, please configure your environment:\n"
            f"1. Open your `.env` file.\n"
            f"2. Add the following line:\n"
            f"   `TELEGRAM_OWNER_ID={user_id}`\n"
            f"3. Restart the bot container.\n\n"
            f"Your Telegram User ID is: `{user_id}`",
            parse_mode="Markdown",
        )
        return

    await update.message.reply_text(
        "👋 Welcome back to **ExpenseGram**!\n\n"
        "I am ready to track your expenses. Just type a transaction shorthand like:\n"
        "   `-15k cash food lunch` or `+3.5m bank salary bonus`\n\n"
        "Type `/help` to see all available commands.",
        parse_mode="Markdown",
    )


@owner_required
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display help information and command listings."""
    help_text = (
        "🤖 **ExpenseGram Shorthand Guide**\n\n"
        "To quickly add a transaction, send a text message in this format:\n"
        "`[sign][amount][multiplier] [account] [category] [description...]`\n\n"
        "**Rules:**\n"
        "• `[sign]`: `+` for income, `-` (or empty) for expense.\n"
        "• `[amount]`: positive number (decimals allowed).\n"
        "• `[multiplier]`: `k` (thousand), `m` (million), or leave empty.\n"
        "• `[account]`: transaction account (e.g. cash, bank, visa).\n"
        "• `[category]`: category name (auto-created if new).\n"
        "• `[description]`: optional text details.\n\n"
        "**Examples:**\n"
        "• `-15k cash food lunch` → 15,000 expense, cash account, food category, 'lunch' detail\n"
        "• `50000 card transport taxi` → 50,000 expense, card account, transport category, 'taxi' detail\n"
        "• `+3.5m bank salary June` → 3,500,000 income, bank account, salary category, 'June' detail\n\n"
        "📋 **Commands:**\n"
        "• `/accounts` - List accounts with balances\n"
        "• `/addaccount <name>` - Add account\n"
        "• `/delaccount <name>` - Delete account (only if unused)\n"
        "• `/transfer <from> <to> <amount> [desc]` - Transfer balance between accounts\n"
        "• `/categories` - List categories\n"
        "• `/addcategory <type> <name>` - Add category (type: `expense` or `income`)\n"
        "• `/delcategory <type> <name>` - Delete category (only if unused)\n"
        "• `/report [month]` - Summary (e.g. `/report`, `/report 05`, or `/report 2026-05`)\n"
        "• `/history [limit]` - Recent transactions (default: 10)\n"
        "• `/delete <id>` - Delete transaction by ID\n"
        "• `/undo` - Undo the very last transaction\n"
        "• `/export` - Download all data as CSV\n"
        "• `/nuke` - Drop all transactions (requires confirmation)\n"
        "• `/help` - Show this guide\n\n"
        f"🤖 **Version:** `{Config.VERSION}`"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")


@owner_required
async def list_categories(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List all categories separated by income and expense."""
    db = get_db(context)
    cats_by_type = db.get_categories_by_type()

    income_cats = cats_by_type.get("income", [])
    expense_cats = cats_by_type.get("expense", [])

    if not income_cats and not expense_cats:
        await update.message.reply_text("🗂️ No categories found.")
        return

    msg_lines = ["🗂️ **Available Categories:**\n"]

    if income_cats:
        msg_lines.append("🟢 **Income:**")
        msg_lines.extend(f"• {c}" for c in income_cats)
        msg_lines.append("")

    if expense_cats:
        msg_lines.append("🔻 **Expenses:**")
        msg_lines.extend(f"• {c}" for c in expense_cats)

    await update.message.reply_text("\n".join(msg_lines).strip(), parse_mode="Markdown")


@owner_required
async def add_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Manually add a new category."""
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "Usage: `/addcategory <expense|income> <category_name>`",
            parse_mode="Markdown",
        )
        return

    cat_type = context.args[0].strip().lower()
    cat_name = " ".join(context.args[1:]).strip()

    if cat_type not in ("expense", "income"):
        await update.message.reply_text(
            "❌ **Invalid type.** First argument must be `expense` or `income`.\n\n"
            "Usage: `/addcategory <expense|income> <category_name>`",
            parse_mode="Markdown",
        )
        return

    db = get_db(context)
    success = db.add_category(cat_name, cat_type)
    if success:
        await update.message.reply_text(
            f"✅ Category `{cat_name.lower()}` ({cat_type}) added.",
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text(
            f"⚠️ Category `{cat_name.lower()}` ({cat_type}) already exists or is invalid.",
            parse_mode="Markdown",
        )


@owner_required
async def del_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Manually delete an unused category."""
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "Usage: `/delcategory <expense|income> <category_name>`",
            parse_mode="Markdown",
        )
        return

    cat_type = context.args[0].strip().lower()
    cat_name = " ".join(context.args[1:]).strip()

    if cat_type not in ("expense", "income"):
        await update.message.reply_text(
            "❌ **Invalid type.** First argument must be `expense` or `income`.\n\n"
            "Usage: `/delcategory <expense|income> <category_name>`",
            parse_mode="Markdown",
        )
        return

    db = get_db(context)
    success, message = db.delete_category(cat_name, cat_type)
    if success:
        await update.message.reply_text(f"✅ {message}")
    else:
        await update.message.reply_text(f"❌ {message}")


@owner_required
async def list_accounts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List all accounts with their current balances."""
    db = get_db(context)
    balances = db.get_account_balances()
    if not balances:
        await update.message.reply_text("💳 No accounts found.")
        return

    msg_lines = ["💳 **Account Balances:**"]
    for acc in sorted(balances.keys()):
        bal = balances[acc]
        msg_lines.append(f"• {acc}: `{bal:,.2f}`")

    await update.message.reply_text("\n".join(msg_lines), parse_mode="Markdown")


@owner_required
async def add_account(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Manually add a new account."""
    if not context.args:
        await update.message.reply_text(
            "Usage: `/addaccount <account_name>`", parse_mode="Markdown"
        )
        return

    acc_name = " ".join(context.args).strip()
    db = get_db(context)
    success = db.add_account(acc_name)
    if success:
        await update.message.reply_text(
            f"✅ Account `{acc_name.lower()}` added.", parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            f"⚠️ Account `{acc_name.lower()}` already exists or is invalid.",
            parse_mode="Markdown",
        )


@owner_required
async def del_account(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Manually delete an unused account."""
    if not context.args:
        await update.message.reply_text(
            "Usage: `/delaccount <account_name>`", parse_mode="Markdown"
        )
        return

    acc_name = " ".join(context.args).strip()
    db = get_db(context)
    success, message = db.delete_account(acc_name)
    if success:
        await update.message.reply_text(f"✅ {message}")
    else:
        await update.message.reply_text(f"❌ {message}")


@owner_required
async def transfer_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Transfer an amount from one account to another."""
    if not context.args or len(context.args) < 3:
        await update.message.reply_text(
            "Usage: `/transfer <from_account> <to_account> <amount> [description...]`",
            parse_mode="Markdown",
        )
        return

    from_account = context.args[0].strip().lower()
    to_account = context.args[1].strip().lower()
    amount_str = context.args[2].strip()
    description = " ".join(context.args[3:]).strip() if len(context.args) > 3 else None

    # Parse amount (using the helper)
    amount = parse_amount(amount_str)
    if amount is None or amount <= 0:
        await update.message.reply_text(
            f"❌ **Invalid amount**: `{amount_str}`. Must be a positive number (e.g. `100`, `15k`, `2.5m`).",
            parse_mode="Markdown",
        )
        return

    db = get_db(context)
    try:
        from_id, to_id = db.add_transfer(
            from_account=from_account,
            to_account=to_account,
            amount=amount,
            description=description,
        )
        desc_str = f" ({description})" if description else ""
        await update.message.reply_text(
            f"💸 **Transfer Successful!**\n"
            f"IDs: `{from_id}` & `{to_id}`\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"💳 **From**: `{from_account}`\n"
            f"💳 **To**: `{to_account}`\n"
            f"💰 **Amount**: `{amount:,.2f}`{desc_str}",
            parse_mode="Markdown",
        )
    except AccountNotFoundError as e:
        await update.message.reply_text(
            f"❌ **Transfer Failed!**\n{str(e)}",
            parse_mode="Markdown",
        )
    except ValueError as e:
        await update.message.reply_text(
            f"❌ **Transfer Failed!**\n{str(e)}",
            parse_mode="Markdown",
        )
    except Exception:
        logger.exception("Unexpected error during transfer")
        await update.message.reply_text(
            "❌ **Transfer Failed!** An unexpected error occurred.",
            parse_mode="Markdown",
        )


@owner_required
async def report_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generate category breakdown report for a given month."""
    now = datetime.now()
    year = now.year
    month = now.month

    if context.args:
        arg = context.args[0].strip()
        # Parse YYYY-MM
        if len(arg) == 7 and arg[4] == "-":
            try:
                parts = arg.split("-")
                year = int(parts[0])
                month = int(parts[1])
            except ValueError:
                await update.message.reply_text(
                    "❌ Invalid format. Use YYYY-MM (e.g. 2026-05) or MM (e.g. 05)."
                )
                return
        else:
            # Parse MM
            try:
                m = int(arg)
                if 1 <= m <= 12:
                    month = m
                else:
                    raise ValueError
            except ValueError:
                await update.message.reply_text(
                    "❌ Invalid month. Provide 1-12 (e.g. 05) or YYYY-MM."
                )
                return

    db = get_db(context)
    rows = db.get_monthly_report(year, month)
    month_name = calendar.month_name[month]

    if not rows:
        await update.message.reply_text(
            f"📅 No transactions found for **{month_name} {year}**.",
            parse_mode="Markdown",
        )
        return

    expenses = []
    income = []
    total_exp = 0.0
    total_inc = 0.0

    for r in rows:
        cat = r["category"]
        t_type = r["type"]
        total = r["total"]
        if t_type == "expense":
            expenses.append(f"• {cat}: `{total:,.2f}`")
            total_exp += total
        elif t_type == "income":
            income.append(f"• {cat}: `{total:,.2f}`")
            total_inc += total

    net = total_inc - total_exp

    report_lines = [f"📊 **Report for {month_name} {year}**\n"]

    if expenses:
        report_lines.append("🔻 **Expenses:**")
        report_lines.extend(expenses)
        report_lines.append(f"**Total Expenses:** `{total_exp:,.2f}`\n")

    if income:
        report_lines.append("🟢 **Income:**")
        report_lines.extend(income)
        report_lines.append(f"**Total Income:** `{total_inc:,.2f}`\n")

    report_lines.append("━━━━━━━━━━━━━━━━━━━━")
    sign_char = "+" if net >= 0 else ""
    report_lines.append(f"💵 **Net Savings:** `{sign_char}{net:,.2f}`")

    await update.message.reply_text("\n".join(report_lines), parse_mode="Markdown")


@owner_required
async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Retrieve list of recent transactions."""
    limit = 10
    if context.args:
        try:
            limit = int(context.args[0])
            if limit <= 0:
                raise ValueError
        except ValueError:
            await update.message.reply_text(
                "❌ Invalid limit. Provide a positive number."
            )
            return

    db = get_db(context)
    txs = db.get_history(limit)
    if not txs:
        await update.message.reply_text("📜 No transactions found.")
        return

    msg_lines = [f"📜 **Last {len(txs)} Transactions:**\n"]
    for t in txs:
        if isinstance(t["created_at"], str):
            try:
                dt_str = t["created_at"].split(".")[0]
                date_str = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S").strftime(
                    "%Y-%m-%d %H:%M"
                )
            except Exception:
                date_str = t["created_at"]
        else:
            date_str = t["created_at"].strftime("%Y-%m-%d %H:%M")

        desc = f" ({t['description']})" if t["description"] else ""
        emoji = "🔻" if t["type"] == "expense" else "🟢"
        msg_lines.append(
            f"`ID: {t['id']}` | {emoji} `{t['amount']:,.2f}` | **{t['account']}** ➔ **{t['category']}**{desc} | _{date_str}_"
        )

    await update.message.reply_text("\n".join(msg_lines), parse_mode="Markdown")


@owner_required
async def delete_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Delete a transaction by database ID."""
    if not context.args:
        await update.message.reply_text(
            "Usage: `/delete <transaction_id>`", parse_mode="Markdown"
        )
        return

    try:
        tx_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid transaction ID. Must be an integer."
        )
        return

    db = get_db(context)
    success = db.delete_transaction(tx_id)
    if success:
        await update.message.reply_text(
            f"✅ Transaction `ID: {tx_id}` deleted successfully.", parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            f"❌ Transaction `ID: {tx_id}` not found.", parse_mode="Markdown"
        )


@owner_required
async def undo_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Undo the last logged transaction or transfer."""
    db = get_db(context)
    txs = db.delete_last_transaction()
    if not txs:
        await update.message.reply_text(
            "⏮️ No transactions found to undo.", parse_mode="Markdown"
        )
        return

    if len(txs) == 2:
        tx1, tx2 = txs[0], txs[1]
        from_acc = tx1["account"] if tx1["type"] == "transfer_out" else tx2["account"]
        to_acc = tx1["account"] if tx1["type"] == "transfer_in" else tx2["account"]
        await update.message.reply_text(
            f"⏮️ **Transfer undone successfully!**\n"
            f"Deleted Transfer IDs: `{tx1['id']}` & `{tx2['id']}`\n"
            f"💸 **Amount**: `{tx1['amount']:,.2f}`\n"
            f"💳 **From**: `{from_acc}` → 💳 **To**: `{to_acc}`",
            parse_mode="Markdown",
        )
    else:
        tx = txs[0]
        emoji = "🔻" if tx["type"] == "expense" else "🟢"
        desc_str = f" ({tx['description']})" if tx["description"] else ""
        await update.message.reply_text(
            f"⏮️ **Undone successfully!**\n"
            f"Deleted: `ID: {tx['id']}`\n"
            f"{emoji} **{tx['type'].capitalize()}**: `{tx['amount']:,.2f}`\n"
            f"💳 **Account**: `{tx['account']}`\n"
            f"🗂️ **Category**: `{tx['category']}`{desc_str}",
            parse_mode="Markdown",
        )


@owner_required
async def export_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Export all transaction data to CSV and send it."""
    db = get_db(context)
    txs = db.get_all_transactions_for_export()
    if not txs:
        await update.message.reply_text("❌ No data to export.")
        return

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        ["ID", "Amount", "Type", "Account", "Category", "Description", "Created At"]
    )
    for t in txs:
        writer.writerow(
            [
                t["id"],
                t["amount"],
                t["type"],
                t["account"],
                t["category"],
                t["description"] or "",
                t["created_at"],
            ]
        )

    csv_bytes = io.BytesIO(output.getvalue().encode("utf-8"))
    csv_bytes.name = "expensegram_export.csv"

    await update.message.reply_document(
        document=csv_bytes,
        filename="expensegram_export.csv",
        caption="📊 Here is your full transaction history export.",
    )


@owner_required
async def nuke_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Initiate database transactions nuke process."""
    db = get_db(context)
    txs = db.get_history(1)
    if not txs:
        await update.message.reply_text(
            "📭 **No transactions found.** The database is already clean.",
            parse_mode="Markdown",
        )
        return

    context.user_data["nuke_pending"] = True
    await update.message.reply_text(
        "⚠️ **WARNING: Permanent Data Loss!**\n\n"
        "This command will **DELETE ALL TRANSACTIONS** in the database. "
        "This action cannot be undone.\n\n"
        "If you are absolutely sure and want to proceed, type **exactly** `I understand`.",
        parse_mode="Markdown",
    )


@owner_required
async def handle_transaction_message(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Parse text message as shorthand transaction and record it."""
    if context.user_data and context.user_data.get("nuke_pending"):
        text = update.message.text.strip()
        if text == "I understand":
            context.user_data["nuke_pending"] = False
            db = get_db(context)
            count = db.delete_all_transactions()
            await update.message.reply_text(
                f"💥 **Nuke Successful!**\n\nDropped all {count} transactions from the database.",
                parse_mode="Markdown",
            )
        else:
            context.user_data["nuke_pending"] = False
            await update.message.reply_text(
                "❌ **Nuke Cancelled.** Confirmation mismatch. Returning to normal mode.",
                parse_mode="Markdown",
            )
        return

    text = update.message.text
    res = parse_transaction(text)

    if not res:
        await update.message.reply_text(
            "❌ **Unable to parse transaction.**\n\n"
            "Please use the format:\n"
            "`[sign][amount][multiplier] [account] [category] [description...]`\n"
            "Example: `-15k cash food lunch` or `50000 card transport taxi`\n\n"
            "Type `/help` to view details.",
            parse_mode="Markdown",
        )
        return

    db = get_db(context)
    try:
        tx_id = db.add_transaction(
            amount=res["amount"],
            tx_type=res["type"],
            account=res["account"],
            category=res["category"],
            description=res["description"],
        )
    except AccountNotFoundError:
        await update.message.reply_text(
            f"❌ **Transaction failed!**\n\n"
            f"The account `{res['account']}` does not exist.\n"
            f"Please create it first using `/addaccount {res['account']}`.",
            parse_mode="Markdown",
        )
        return
    except CategoryNotFoundError:
        await update.message.reply_text(
            f"❌ **Transaction failed!**\n\n"
            f"The category `{res['category']}` does not exist.\n"
            f"Please create it first using `/addcategory {res['category']}`.",
            parse_mode="Markdown",
        )
        return

    emoji = "🔻" if res["type"] == "expense" else "🟢"
    desc_str = f" ({res['description']})" if res["description"] else ""

    await update.message.reply_text(
        f"✅ **Saved successfully!**\n"
        f"ID: `{tx_id}`\n"
        f"{emoji} **{res['type'].capitalize()}**: `{res['amount']:,.2f}`\n"
        f"💳 **Account**: `{res['account']}`\n"
        f"🗂️ **Category**: `{res['category']}`{desc_str}",
        parse_mode="Markdown",
    )


@owner_required
async def handle_unknown_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Respond to unknown commands."""
    await update.message.reply_text(
        "❌ **Unknown command.**\n\nType `/help` to see all available commands.",
        parse_mode="Markdown",
    )
