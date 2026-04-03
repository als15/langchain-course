"""CLI for approving Instagram post publishing via LangGraph interrupt resumption."""

from dotenv import load_dotenv

load_dotenv()

from db.schema import init_db
from db.connection import get_db
from graph.orchestrator import build_orchestrator


def main():
    init_db()
    app = build_orchestrator()

    print("\n=== Capa & Co - Publish Approval ===\n")
    print("This tool runs the Content Publisher agent.")
    print("It will pause for your approval before each post.\n")

    # Show approved posts ready to publish
    db = get_db()
    posts = db.execute(
        "SELECT id, scheduled_date, topic, caption, image_url FROM content_queue "
        "WHERE status = 'approved' AND image_url IS NOT NULL AND image_url != ''"
    ).fetchall()

    if not posts:
        print("No approved posts with images ready to publish.")
        print("Use 'python review.py' to approve drafts and add image URLs first.")
        return

    print(f"Found {len(posts)} approved post(s) ready to publish:")
    for p in posts:
        print(f"  [{p['id']}] {p['scheduled_date']} - {p['topic']}")
        print(f"       Caption: {p['caption'][:80]}...")
        print(f"       Image: {p['image_url'][:60]}...")
        print()

    proceed = input("Start publishing flow? (yes/no): ").strip().lower()
    if proceed != "yes":
        print("Cancelled.")
        return

    import time

    thread_id = f"publish_{int(time.time())}"
    config = {"configurable": {"thread_id": thread_id}}

    # Run the publisher - it will hit interrupt() for each post
    print("\nStarting publisher agent...\n")

    from langgraph.types import Command

    # Initial invoke
    result = app.invoke(
        {"task_type": "publish", "messages": [], "result_summary": ""},
        config=config,
    )

    # Check for interrupts
    state = app.get_state(config)
    while state.next:  # There are pending nodes (interrupted)
        # Get interrupt data
        interrupts = state.tasks
        for task in interrupts:
            if hasattr(task, "interrupts") and task.interrupts:
                for intr in task.interrupts:
                    print("\n--- APPROVAL REQUIRED ---")
                    data = intr.value
                    if isinstance(data, dict):
                        print(f"  Post ID: {data.get('post_id')}")
                        print(f"  Caption: {data.get('caption')}")
                        print(f"  Image:   {data.get('image_url')}")
                        print(f"  {data.get('message', '')}")
                    else:
                        print(f"  {data}")

                    decision = input("\n  Your decision (approve/reject): ").strip().lower()
                    response = "approve" if decision == "approve" else "reject"

        # Resume with the decision
        result = app.invoke(Command(resume=response), config=config)
        state = app.get_state(config)

    print("\n--- Publishing complete ---")
    print(f"Result: {result.get('result_summary', 'Done.')}")


if __name__ == "__main__":
    main()
