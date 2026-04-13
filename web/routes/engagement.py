"""Engagement tasks page."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from web import templates
from web.db import query, query_one, execute
from web.brand_switcher import get_dashboard_brand, get_brand_context

router = APIRouter()


@router.get("/engagement", response_class=HTMLResponse)
async def engagement_page(request: Request):
    from web.routes.dashboard import _global_stats

    brand_id = get_dashboard_brand(request)
    status_filter = request.query_params.get("status", "pending")

    conditions = ["brand_id = ?"]
    params = [brand_id]
    if status_filter:
        conditions.append("status = ?")
        params.append(status_filter)

    where = "WHERE " + " AND ".join(conditions)

    tasks = await query(
        f"SELECT id, created_at, target_handle, action_type, suggested_comment, "
        f"reason, status, completed_at "
        f"FROM engagement_tasks {where} ORDER BY created_at DESC LIMIT 100",
        tuple(params),
    )

    # Summary counts
    summary_rows = await query(
        "SELECT status, COUNT(*) as count FROM engagement_tasks WHERE brand_id = ? GROUP BY status",
        (brand_id,),
    )
    summary = {r["status"]: r["count"] for r in summary_rows}

    # Completion rate last 30 days
    rate = await query_one(
        "SELECT COUNT(*) as total, "
        "SUM(CASE WHEN status='done' THEN 1 ELSE 0 END) as done, "
        "SUM(CASE WHEN status='skipped' THEN 1 ELSE 0 END) as skipped "
        "FROM engagement_tasks WHERE brand_id = ? AND created_at >= date('now', '-30 days')",
        (brand_id,),
    )

    stats = await _global_stats(brand_id)

    return templates.TemplateResponse(request, "pages/engagement.html", {
        "active_page": "leads",
        "stats": stats,
        "tasks": tasks,
        "summary": summary,
        "rate": rate or {},
        "status_filter": status_filter,
        **get_brand_context(request),
    })


@router.post("/engagement/{task_id}/done", response_class=HTMLResponse)
async def mark_done(request: Request, task_id: int):
    brand_id = get_dashboard_brand(request)
    await execute(
        "UPDATE engagement_tasks SET status = 'done', completed_at = CURRENT_TIMESTAMP WHERE id = ? AND brand_id = ?",
        (task_id, brand_id),
    )
    return HTMLResponse('<span class="badge badge-done">Done</span>')


@router.post("/engagement/{task_id}/skip", response_class=HTMLResponse)
async def mark_skipped(request: Request, task_id: int):
    brand_id = get_dashboard_brand(request)
    await execute(
        "UPDATE engagement_tasks SET status = 'skipped', completed_at = CURRENT_TIMESTAMP WHERE id = ? AND brand_id = ?",
        (task_id, brand_id),
    )
    return HTMLResponse('<span class="badge badge-skipped">Skipped</span>')
