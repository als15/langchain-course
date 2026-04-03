"""Telegram bot for Capa & Co Instagram agent notifications and approvals."""

import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

from db.connection import get_db

log = logging.getLogger("capaco")


def _authorized(update: Update) -> bool:
    """Check if the user is authorized."""
    allowed = os.environ.get("TELEGRAM_AUTHORIZED_USERS", "")
    if not allowed:
        return True
    allowed_ids = {int(uid.strip()) for uid in allowed.split(",") if uid.strip()}
    return update.effective_user.id in allowed_ids


def _chat_id() -> str:
    return os.environ["TELEGRAM_CHAT_ID"]


# ── Command Handlers ─────────────────────────────────────────────────


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _authorized(update):
        await update.message.reply_text("Unauthorized.")
        return
    await update.message.reply_text(
        "Capa & Co Instagram Bot\n\n"
        "Commands:\n"
        "/status - Account stats & recent runs\n"
        "/queue - Content queue overview\n"
        "/leads - Recent leads\n"
        "/engage - Pending engagement tasks\n"
        f"\nYour Telegram ID: {update.effective_user.id}"
    )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _authorized(update):
        return
    db = get_db()

    # Queue stats
    counts = db.execute(
        "SELECT status, COUNT(*) as cnt FROM content_queue GROUP BY status"
    ).fetchall()
    queue_lines = [f"  {r['status']}: {r['cnt']}" for r in counts] or ["  (empty)"]

    # Recent runs
    runs = db.execute(
        "SELECT task_type, status, started_at FROM run_log ORDER BY started_at DESC LIMIT 5"
    ).fetchall()
    run_lines = [
        f"  {r['started_at'][:16]} | {r['task_type']} | {r['status']}" for r in runs
    ] or ["  (none)"]

    text = (
        "Content Queue:\n" + "\n".join(queue_lines) +
        "\n\nRecent Runs:\n" + "\n".join(run_lines)
    )
    await update.message.reply_text(text)


async def queue_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _authorized(update):
        return
    db = get_db()
    rows = db.execute(
        "SELECT id, scheduled_date, topic, status, image_url "
        "FROM content_queue WHERE status NOT IN ('published', 'rejected') "
        "ORDER BY scheduled_date LIMIT 15"
    ).fetchall()

    if not rows:
        await update.message.reply_text("Content queue is empty.")
        return

    lines = []
    for r in rows:
        img = "img" if r["image_url"] else "no-img"
        lines.append(f"[{r['id']}] {r['scheduled_date'] or '?'} | {r['status']} | {img} | {r['topic'][:35]}")

    await update.message.reply_text("Content Queue:\n" + "\n".join(lines))


async def leads_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _authorized(update):
        return
    db = get_db()
    rows = db.execute(
        "SELECT business_name, business_type, status FROM leads ORDER BY created_at DESC LIMIT 10"
    ).fetchall()

    if not rows:
        await update.message.reply_text("No leads yet.")
        return

    lines = [f"  {r['business_name']} ({r['business_type']}) - {r['status']}" for r in rows]
    await update.message.reply_text("Recent Leads:\n" + "\n".join(lines))


async def engage_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _authorized(update):
        return
    db = get_db()
    rows = db.execute(
        "SELECT target_handle, action_type, suggested_comment FROM engagement_tasks "
        "WHERE status = 'pending' ORDER BY created_at DESC LIMIT 10"
    ).fetchall()

    if not rows:
        await update.message.reply_text("No pending engagement tasks.")
        return

    lines = [
        f"  @{r['target_handle']} - {r['action_type']}: {r['suggested_comment'][:50] if r['suggested_comment'] else '(no comment)'}"
        for r in rows
    ]
    await update.message.reply_text("Pending Engagement:\n" + "\n".join(lines))


# ── Approval Callback ────────────────────────────────────────────────


async def approval_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle approve/reject button presses."""
    query = update.callback_query
    await query.answer()

    if not _authorized(update):
        await query.edit_message_caption(caption="Unauthorized.")
        return

    data = query.data  # "approve_123" or "reject_123"
    action, post_id_str = data.split("_", 1)
    post_id = int(post_id_str)

    db = get_db()
    row = db.execute("SELECT topic, status FROM content_queue WHERE id = ?", (post_id,)).fetchone()

    if not row:
        await query.edit_message_caption(caption=f"Post {post_id} not found.")
        return

    if row["status"] != "pending_approval":
        await query.edit_message_caption(
            caption=f"Post {post_id} is already '{row['status']}'."
        )
        return

    if action == "approve":
        db.execute(
            "UPDATE content_queue SET status = 'approved', approved_by = 'telegram', "
            "approved_at = CURRENT_TIMESTAMP WHERE id = ?",
            (post_id,),
        )
        db.commit()
        await query.edit_message_caption(
            caption=f"APPROVED: {row['topic']}\n\nWill be published on next publish run."
        )
        log.info(f"Post {post_id} approved via Telegram.")
    else:
        db.execute(
            "UPDATE content_queue SET status = 'rejected' WHERE id = ?",
            (post_id,),
        )
        db.commit()
        await query.edit_message_caption(caption=f"REJECTED: {row['topic']}")
        log.info(f"Post {post_id} rejected via Telegram.")


# ── Notification Senders (called by daemon) ──────────────────────────


async def notify_pending_approval(bot: Bot, post_id: int, topic: str, caption: str, image_url: str):
    """Send an image with approve/reject buttons to Telegram."""
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Approve", callback_data=f"approve_{post_id}"),
            InlineKeyboardButton("Reject", callback_data=f"reject_{post_id}"),
        ]
    ])

    preview_text = (
        f"NEW POST FOR REVIEW\n\n"
        f"Topic: {topic}\n"
        f"Caption: {caption[:300]}{'...' if len(caption) > 300 else ''}"
    )

    try:
        await bot.send_photo(
            chat_id=_chat_id(),
            photo=image_url,
            caption=preview_text[:1024],  # Telegram caption limit
            reply_markup=keyboard,
        )
    except Exception as e:
        # If image fails to load, send as text with URL
        await bot.send_message(
            chat_id=_chat_id(),
            text=f"{preview_text}\n\nImage: {image_url}",
            reply_markup=keyboard,
        )
        log.warning(f"Failed to send image for post {post_id}: {e}")


async def notify_task_complete(bot: Bot, task_type: str, summary: str):
    """Notify that a scheduled task completed."""
    text = f"Task completed: {task_type}\n\n{summary[:500]}"
    await bot.send_message(chat_id=_chat_id(), text=text)


async def notify_error(bot: Bot, task_type: str, error_msg: str):
    """Notify that a scheduled task failed."""
    text = f"TASK FAILED: {task_type}\n\nError: {error_msg[:500]}"
    await bot.send_message(chat_id=_chat_id(), text=text)


# ── Builder ──────────────────────────────────────────────────────────


def build_telegram_app() -> Application:
    """Build the Telegram Application with all handlers."""
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("queue", queue_command))
    app.add_handler(CommandHandler("leads", leads_command))
    app.add_handler(CommandHandler("engage", engage_command))
    app.add_handler(CallbackQueryHandler(approval_callback, pattern=r"^(approve|reject)_\d+$"))

    return app
