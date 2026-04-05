"""Dashboard overview page."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from web import templates
from web.db import query, query_one

router = APIRouter()


async def _global_stats() -> dict:
    row = await query_one(
        "SELECT "
        "(SELECT COUNT(*) FROM content_queue WHERE status = 'pending_approval') as pending_count, "
        "(SELECT COUNT(*) FROM content_queue WHERE status = 'approved') as approved_count, "
        "(SELECT follower_count FROM analytics_snapshots ORDER BY snapshot_date DESC LIMIT 1) as followers"
    )
    last_run = await query_one(
        "SELECT started_at, task_type, status FROM run_log ORDER BY started_at DESC LIMIT 1"
    )
    stats = dict(row) if row else {}
    if last_run:
        ts = str(last_run["started_at"] or "")
        stats["last_run_short"] = ts[5:16] if len(ts) >= 16 else ts
    return stats


@router.get("/partials/global-stats", response_class=HTMLResponse)
async def global_stats_partial(request: Request):
    stats = await _global_stats()
    return templates.TemplateResponse(request, "components/global_stats.html", {"stats": stats})


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    stats = await _global_stats()

    # Pipeline counts
    pipeline_rows = await query(
        "SELECT status, COUNT(*) as count FROM content_queue GROUP BY status"
    )
    pipeline = {r["status"]: r["count"] for r in pipeline_rows}

    # Recent runs
    recent_runs = await query(
        "SELECT id, started_at, task_type, status, duration_seconds, "
        "COALESCE(summary, error) as detail "
        "FROM run_log ORDER BY started_at DESC LIMIT 10"
    )

    # This week published
    published_week = await query_one(
        "SELECT COUNT(*) as count FROM content_queue "
        "WHERE status = 'published' AND published_at >= date('now', '-7 days')"
    )

    # Latest analytics
    latest_analytics = await query_one(
        "SELECT * FROM analytics_snapshots ORDER BY snapshot_date DESC LIMIT 1"
    )

    # Failure rate last 7 days
    fail_stats = await query_one(
        "SELECT COUNT(*) as total, "
        "SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) as failures "
        "FROM run_log WHERE started_at >= date('now', '-7 days')"
    )

    return templates.TemplateResponse(request, "pages/dashboard.html", {
        "active_page": "dashboard",
        "stats": stats,
        "pipeline": pipeline,
        "recent_runs": recent_runs,
        "published_week": (published_week or {}).get("count", 0),
        "analytics": latest_analytics or {},
        "fail_stats": fail_stats or {},
    })
