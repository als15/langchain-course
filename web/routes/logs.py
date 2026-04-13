"""Run history page."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from web import templates
from web.db import query
from web.brand_switcher import get_dashboard_brand, get_brand_context

router = APIRouter()


@router.get("/logs", response_class=HTMLResponse)
async def logs_page(request: Request):
    from web.routes.dashboard import _global_stats

    brand_id = get_dashboard_brand(request)
    task_filter = request.query_params.get("task", "")
    status_filter = request.query_params.get("status", "")

    conditions = ["brand_id = ?"]
    params = [brand_id]
    if task_filter:
        conditions.append("task_type = ?")
        params.append(task_filter)
    if status_filter:
        conditions.append("status = ?")
        params.append(status_filter)

    where = "WHERE " + " AND ".join(conditions)

    runs = await query(
        f"SELECT id, started_at, task_type, status, duration_seconds, summary, error "
        f"FROM run_log {where} ORDER BY started_at DESC LIMIT 100",
        tuple(params),
    )

    # Agent health: per-task stats
    agent_stats = await query(
        "SELECT task_type, COUNT(*) as total, "
        "SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) as successes, "
        "SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) as failures, "
        "AVG(duration_seconds) as avg_duration, "
        "MAX(started_at) as last_run "
        "FROM run_log WHERE brand_id = ? AND started_at >= date('now', '-30 days') "
        "GROUP BY task_type ORDER BY last_run DESC",
        (brand_id,),
    )

    # Daily chart data (14 days)
    daily = await query(
        "SELECT date(started_at) as run_date, "
        "SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) as successes, "
        "SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) as failures "
        "FROM run_log WHERE brand_id = ? AND started_at >= date('now', '-14 days') "
        "GROUP BY date(started_at) ORDER BY run_date",
        (brand_id,),
    )

    # Task types for filter dropdown
    task_types = await query(
        "SELECT DISTINCT task_type FROM run_log WHERE brand_id = ? ORDER BY task_type",
        (brand_id,),
    )

    stats = await _global_stats(brand_id)

    return templates.TemplateResponse(request, "pages/logs.html", {
        "active_page": "logs",
        "stats": stats,
        "runs": runs,
        "agent_stats": agent_stats,
        "daily": daily,
        "task_types": [r["task_type"] for r in task_types],
        "task_filter": task_filter,
        "status_filter": status_filter,
        **get_brand_context(request),
    })


@router.get("/partials/recent-runs", response_class=HTMLResponse)
async def recent_runs_partial(request: Request):
    brand_id = get_dashboard_brand(request)
    recent_runs = await query(
        "SELECT id, started_at, task_type, status, duration_seconds, "
        "COALESCE(summary, error) as detail "
        "FROM run_log WHERE brand_id = ? ORDER BY started_at DESC LIMIT 10",
        (brand_id,),
    )
    return templates.TemplateResponse(request, "components/recent_runs.html", {
        "recent_runs": recent_runs,
        **get_brand_context(request),
    })
