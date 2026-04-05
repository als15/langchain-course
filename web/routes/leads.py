"""Leads management page."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from web import templates
from web.db import query, execute

router = APIRouter()


@router.get("/leads", response_class=HTMLResponse)
async def leads_page(request: Request):
    from web.routes.dashboard import _global_stats

    status_filter = request.query_params.get("status", "")
    type_filter = request.query_params.get("type", "")

    conditions = []
    params = []
    if status_filter:
        conditions.append("status = ?")
        params.append(status_filter)
    if type_filter:
        conditions.append("business_type = ?")
        params.append(type_filter)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    leads_rows = await query(
        f"SELECT id, created_at, business_name, instagram_handle, business_type, "
        f"location, follower_count, source, status, notes "
        f"FROM leads {where} ORDER BY created_at DESC LIMIT 100",
        tuple(params),
    )

    # Funnel counts
    funnel_rows = await query(
        "SELECT status, COUNT(*) as count FROM leads GROUP BY status"
    )
    funnel = {r["status"]: r["count"] for r in funnel_rows}

    # Business types for filter
    types = await query(
        "SELECT DISTINCT business_type FROM leads WHERE business_type IS NOT NULL ORDER BY business_type"
    )

    stats = await _global_stats()

    return templates.TemplateResponse(request, "pages/leads.html", {
        "active_page": "leads",
        "stats": stats,
        "leads": leads_rows,
        "funnel": funnel,
        "business_types": [r["business_type"] for r in types],
        "status_filter": status_filter,
        "type_filter": type_filter,
    })


@router.post("/leads/{lead_id}/status", response_class=HTMLResponse)
async def update_lead_status(request: Request, lead_id: int):
    form = await request.form()
    new_status = form.get("status", "")
    valid = {"discovered", "researched", "contacted", "converted"}
    if new_status not in valid:
        return HTMLResponse('<span class="badge badge-failed">Invalid status</span>')

    await execute(
        "UPDATE leads SET status = ?, last_updated = CURRENT_TIMESTAMP WHERE id = ?",
        (new_status, lead_id),
    )
    return HTMLResponse(f'<span class="badge badge-{new_status}">{new_status}</span>')
