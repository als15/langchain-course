"""CLI for reviewing content queue, leads, and engagement tasks."""

from dotenv import load_dotenv

load_dotenv()

import json
from db.schema import init_db
from db.connection import get_db


def show_content_queue():
    db = get_db()
    rows = db.execute(
        "SELECT id, scheduled_date, scheduled_time, content_type, content_pillar, "
        "topic, status, image_url FROM content_queue ORDER BY scheduled_date"
    ).fetchall()

    if not rows:
        print("  (empty)")
        return

    for r in rows:
        img = "📷" if r["image_url"] else "❌"
        status_icon = {
            "draft": "📝", "approved": "✅", "published": "🚀", "failed": "❗"
        }.get(r["status"], "❓")
        print(
            f"  [{r['id']}] {status_icon} {r['scheduled_date']} {r['scheduled_time']} "
            f"| {r['content_type']:10s} | {r['content_pillar']:20s} | {r['topic'][:40]:40s} "
            f"| img:{img} | {r['status']}"
        )


def show_post_detail(post_id: int):
    db = get_db()
    row = db.execute("SELECT * FROM content_queue WHERE id = ?", (post_id,)).fetchone()
    if not row:
        print(f"  Post {post_id} not found.")
        return
    d = dict(row)
    print(f"\n  === Post #{d['id']} ===")
    print(f"  Date:    {d['scheduled_date']} {d['scheduled_time']}")
    print(f"  Type:    {d['content_type']} | Pillar: {d['content_pillar']}")
    print(f"  Topic:   {d['topic']}")
    print(f"  Status:  {d['status']}")
    print(f"  Image:   {d['image_url'] or '(none)'}")
    print(f"  Caption: {d['caption']}")
    print(f"  Tags:    {d['hashtags']}")
    print(f"  Visual:  {d['visual_direction']}")


def approve_post(post_id: int):
    db = get_db()
    row = db.execute("SELECT status FROM content_queue WHERE id = ?", (post_id,)).fetchone()
    if not row:
        print(f"  Post {post_id} not found.")
        return
    if row["status"] != "draft":
        print(f"  Post {post_id} is '{row['status']}', not 'draft'.")
        return

    image_url = input("  Image URL (paste publicly accessible URL): ").strip()
    if not image_url:
        print("  Skipped - no image URL provided.")
        return

    db.execute(
        "UPDATE content_queue SET status = 'approved', image_url = ?, approved_at = CURRENT_TIMESTAMP WHERE id = ?",
        (image_url, post_id),
    )
    db.commit()
    print(f"  Post {post_id} approved with image.")


def reject_post(post_id: int):
    db = get_db()
    db.execute("UPDATE content_queue SET status = 'rejected' WHERE id = ?", (post_id,))
    db.commit()
    print(f"  Post {post_id} rejected.")


def show_leads():
    db = get_db()
    rows = db.execute(
        "SELECT id, business_name, business_type, instagram_handle, location, status "
        "FROM leads ORDER BY created_at DESC LIMIT 20"
    ).fetchall()
    if not rows:
        print("  (no leads)")
        return
    for r in rows:
        handle = f"@{r['instagram_handle']}" if r["instagram_handle"] else ""
        print(
            f"  [{r['id']}] {r['business_name']:30s} | {r['business_type']:15s} "
            f"| {handle:20s} | {r['location'] or '':20s} | {r['status']}"
        )


def show_engagement_tasks():
    db = get_db()
    rows = db.execute(
        "SELECT id, target_handle, action_type, suggested_comment, reason, status "
        "FROM engagement_tasks WHERE status = 'pending' ORDER BY created_at DESC LIMIT 20"
    ).fetchall()
    if not rows:
        print("  (no pending tasks)")
        return
    for r in rows:
        comment = f'"{r["suggested_comment"][:60]}"' if r["suggested_comment"] else ""
        print(
            f"  [{r['id']}] {r['action_type']:8s} @{r['target_handle']:20s} "
            f"| {comment:60s} | {r['reason'][:40] if r['reason'] else ''}"
        )


def mark_engagement_done(task_id: int):
    db = get_db()
    db.execute(
        "UPDATE engagement_tasks SET status = 'done', completed_at = CURRENT_TIMESTAMP WHERE id = ?",
        (task_id,),
    )
    db.commit()
    print(f"  Task {task_id} marked as done.")


def show_run_log():
    db = get_db()
    rows = db.execute(
        "SELECT started_at, task_type, status, duration_seconds, summary "
        "FROM run_log ORDER BY started_at DESC LIMIT 10"
    ).fetchall()
    if not rows:
        print("  (no runs yet)")
        return
    for r in rows:
        dur = f"{r['duration_seconds']:.1f}s" if r["duration_seconds"] else "?"
        print(
            f"  {r['started_at']} | {r['task_type']:20s} | {r['status']:10s} "
            f"| {dur:8s} | {(r['summary'] or '')[:60]}"
        )


def main():
    init_db()

    print("\n=== Capa & Co - Review Dashboard ===\n")

    while True:
        print("\nCommands:")
        print("  queue     - Show content queue")
        print("  detail N  - Show post detail")
        print("  approve N - Approve a draft post (provide image URL)")
        print("  reject N  - Reject a draft post")
        print("  leads     - Show leads")
        print("  engage    - Show pending engagement tasks")
        print("  done N    - Mark engagement task as done")
        print("  log       - Show recent run log")
        print("  quit      - Exit")

        cmd = input("\n> ").strip().lower()

        if cmd == "quit" or cmd == "q":
            break
        elif cmd == "queue":
            show_content_queue()
        elif cmd.startswith("detail "):
            show_post_detail(int(cmd.split()[1]))
        elif cmd.startswith("approve "):
            approve_post(int(cmd.split()[1]))
        elif cmd.startswith("reject "):
            reject_post(int(cmd.split()[1]))
        elif cmd == "leads":
            show_leads()
        elif cmd == "engage":
            show_engagement_tasks()
        elif cmd.startswith("done "):
            mark_engagement_done(int(cmd.split()[1]))
        elif cmd == "log":
            show_run_log()
        else:
            print("  Unknown command.")


if __name__ == "__main__":
    main()
