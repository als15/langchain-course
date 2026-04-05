"""Send Telegram notifications for pending posts WITHOUT starting the bot polling.
Safe to run locally while the daemon runs on Railway."""

import asyncio
from dotenv import load_dotenv
load_dotenv()

import os
from db.schema import init_db
from db.connection import get_db
from telegram import Bot

init_db()


async def main():
    bot = Bot(token=os.environ["TELEGRAM_BOT_TOKEN"])
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    db = get_db()

    rows = db.execute(
        "SELECT id, topic, caption, image_url FROM content_queue "
        "WHERE status = 'pending_approval' AND image_url IS NOT NULL"
    ).fetchall()

    if not rows:
        print("No pending posts to notify about.")
        return

    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    for row in rows:
        review_text = (
            f"📋 POST #{row['id']} FOR REVIEW\n\n"
            f"Topic: {row['topic']}\n\n"
            f"━━━ Caption (will be published) ━━━\n"
            f"{row['caption']}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        )

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Approve", callback_data=f"approve_{row['id']}"),
                InlineKeyboardButton("Regenerate", callback_data=f"regen_{row['id']}"),
            ],
            [
                InlineKeyboardButton("Edit Caption", callback_data=f"editcap_{row['id']}"),
                InlineKeyboardButton("Reject", callback_data=f"reject_{row['id']}"),
            ],
        ])

        try:
            await bot.send_photo(
                chat_id=chat_id, photo=row["image_url"],
                caption=review_text[:1024], reply_markup=keyboard,
            )
            print(f"  Sent #{row['id']}: {row['topic']}")
        except Exception as e:
            await bot.send_message(
                chat_id=chat_id,
                text=f"{review_text}\n\nImage: {row['image_url']}",
                reply_markup=keyboard,
            )
            print(f"  Sent #{row['id']} (text fallback): {row['topic']}")

    print(f"\nDone! Sent {len(rows)} notifications.")


if __name__ == "__main__":
    asyncio.run(main())
