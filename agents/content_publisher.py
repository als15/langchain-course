"""Deterministic content publisher — no LLM involved.

Queries due approved posts, publishes them to Instagram, and updates the DB.
"""

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from db.connection import get_db
from tools.instagram import publish_photo_post, publish_story, _published_today

log = logging.getLogger("capaco")

IL_TZ = ZoneInfo("Asia/Jerusalem")

MAX_POSTS_PER_DAY = 1
MAX_STORIES_PER_DAY = 2


def publish_due_posts(content_type: str) -> str:
    """Publish all due approved posts of the given content type. Returns a summary string."""
    now = datetime.now(IL_TZ)
    today = now.strftime("%Y-%m-%d")
    now_time = now.strftime("%H:%M")

    db = get_db()

    rows = db.execute(
        "SELECT id, image_url, caption, hashtags, content_type, instagram_media_id "
        "FROM content_queue "
        "WHERE status = 'approved' AND content_type = ? AND image_url IS NOT NULL "
        "AND (scheduled_date < ? OR (scheduled_date = ? AND scheduled_time <= ?)) "
        "ORDER BY scheduled_date ASC, scheduled_time ASC",
        (content_type, today, today, now_time),
    ).fetchall()

    if not rows:
        return f"No due {content_type} posts to publish."

    max_per_day = MAX_POSTS_PER_DAY if content_type == "photo" else MAX_STORIES_PER_DAY
    already_published = _published_today(content_type)

    published = 0
    failed = 0
    skipped = 0

    for post in rows:
        # Idempotency: skip if already pushed to Instagram
        if post["instagram_media_id"]:
            skipped += 1
            continue

        # Daily limit (account for what we've published in this run too)
        if already_published + published >= max_per_day:
            log.info(f"Daily {content_type} limit reached ({max_per_day}), stopping.")
            break

        post_id = post["id"]
        try:
            if content_type == "photo":
                caption = ((post["caption"] or "") + "\n" + (post["hashtags"] or "")).strip()
                result = publish_photo_post.invoke({"image_url": post["image_url"], "caption": caption})
            else:
                result = publish_story.invoke({"image_url": post["image_url"]})

            media_id = result.get("id", "")
            db.execute(
                "UPDATE content_queue SET status = 'published', instagram_media_id = ?, "
                "published_at = CURRENT_TIMESTAMP WHERE id = ?",
                (media_id, post_id),
            )
            db.commit()
            published += 1
            log.info(f"Published {content_type} post {post_id} (media_id={media_id})")

        except Exception as e:
            db.execute(
                "UPDATE content_queue SET status = 'failed', "
                "retry_count = retry_count + 1 WHERE id = ?",
                (post_id,),
            )
            db.commit()
            failed += 1
            log.error(f"Failed to publish {content_type} post {post_id}: {e}")

    parts = []
    if published:
        parts.append(f"{published} published")
    if failed:
        parts.append(f"{failed} failed")
    if skipped:
        parts.append(f"{skipped} skipped (already on Instagram)")
    remaining = len(rows) - published - failed - skipped
    if remaining:
        parts.append(f"{remaining} deferred (daily limit)")
    return f"{content_type.title()} publish: {', '.join(parts)}." if parts else f"No {content_type} posts to publish."
