"""Schedule page and task trigger endpoints."""

import asyncio
import logging

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from web import templates
from web.db import query, query_one
from web.brand_switcher import get_dashboard_brand, get_brand_context

router = APIRouter()
log = logging.getLogger("capaco")

# Known schedule from daemon.py
SCHEDULE_DEFS = [
    {"task": "culinary_review", "label": "Culinary Review", "cron": "Sun 06:30"},
    {"task": "content_planning", "label": "Content Planning", "cron": "Sun 07:00"},
    {"task": "design_review", "label": "Design Review", "cron": "Sun 08:00"},
    {"task": "image_generation", "label": "Image Generation", "cron": "Sun 09:00"},
    {"task": "publish", "label": "Publish Posts", "cron": "Every 2h 06:00–20:00"},
    {"task": "publish_stories", "label": "Publish Stories", "cron": "Every 2h 06:00–20:00"},
    {"task": "analytics", "label": "Analytics", "cron": "Daily 18:00"},
    {"task": "content_review", "label": "Content Review", "cron": "Daily 19:00"},
    {"task": "lead_gen", "label": "Lead Generation", "cron": "Wed 10:00"},
    {"task": "engagement", "label": "Engagement Advisor", "cron": "Tue/Thu 10:00"},
]


@router.get("/schedule", response_class=HTMLResponse)
async def schedule_page(request: Request):
    from web.routes.dashboard import _global_stats

    brand_id = get_dashboard_brand(request)

    # Last run per task type
    last_runs = await query(
        "SELECT task_type, "
        "MAX(CASE WHEN status='completed' THEN started_at END) as last_success, "
        "MAX(CASE WHEN status='failed' THEN started_at END) as last_failure "
        "FROM run_log WHERE brand_id = ? GROUP BY task_type",
        (brand_id,),
    )
    last_run_map = {r["task_type"]: r for r in last_runs}

    # Enrich schedule defs with run info
    schedule = []
    for defn in SCHEDULE_DEFS:
        entry = dict(defn)
        run_info = last_run_map.get(defn["task"], {})
        entry["last_success"] = run_info.get("last_success")
        entry["last_failure"] = run_info.get("last_failure")
        schedule.append(entry)

    # Upcoming content
    upcoming = await query(
        "SELECT id, scheduled_date, scheduled_time, content_type, topic, status, image_url "
        "FROM content_queue "
        "WHERE brand_id = ? AND status IN ('draft', 'pending_approval', 'approved') "
        "AND scheduled_date >= CAST(date('now') AS TEXT) "
        "ORDER BY scheduled_date, scheduled_time LIMIT 14",
        (brand_id,),
    )

    # Next run times from scheduler if available
    next_runs = {}
    scheduler = request.app.state.scheduler
    if scheduler:
        for job in scheduler.get_jobs():
            next_run = job.next_run_time
            if next_run:
                next_runs[job.id] = next_run.strftime("%Y-%m-%d %H:%M")

    stats = await _global_stats(brand_id)

    return templates.TemplateResponse(request, "pages/schedule.html", {
        "active_page": "schedule",
        "stats": stats,
        "schedule": schedule,
        "upcoming": upcoming,
        "next_runs": next_runs,
        **get_brand_context(request),
    })


def _bot_for_brand(request: Request, brand_id: str):
    """Return the Telegram bot registered for this brand, falling back to the primary bot."""
    brand_bots = getattr(request.app.state, "brand_bots", {}) or {}
    return brand_bots.get(brand_id) or request.app.state.bot


@router.post("/schedule/{task_type}/run", response_class=HTMLResponse)
async def trigger_task(request: Request, task_type: str):
    safe_run = request.app.state.safe_run

    if not safe_run:
        return HTMLResponse('<span class="badge badge-failed">No runner available</span>')

    valid_tasks = {d["task"] for d in SCHEDULE_DEFS}
    if task_type not in valid_tasks:
        return HTMLResponse(f'<span class="badge badge-failed">Unknown task: {task_type}</span>')

    # Record the trigger timestamp so we can poll for a result after it
    from datetime import datetime, timezone
    trigger_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    brand_id = get_dashboard_brand(request)
    bot = _bot_for_brand(request, brand_id)
    log.info(f"Dashboard triggered task: {task_type} for brand: {brand_id}")
    asyncio.create_task(safe_run(task_type, bot, brand_id))

    return HTMLResponse(
        f'<div class="run-status" '
        f'hx-get="/schedule/{task_type}/last-run?after={trigger_ts}" '
        f'hx-trigger="every 2s" hx-swap="outerHTML">'
        f'<span class="badge badge-running">Running {task_type}...</span>'
        f'</div>'
    )


PLANNING_CASCADE = ("culinary_review", "content_planning", "design_review", "image_generation")


@router.post("/schedule/run-planning-cascade", response_class=HTMLResponse)
async def trigger_planning_cascade(request: Request):
    """Run the full Sunday planning pipeline on demand for the selected brand."""
    safe_run = request.app.state.safe_run
    if not safe_run:
        return HTMLResponse('<span class="badge badge-failed">No runner available</span>')

    from datetime import datetime, timezone
    trigger_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    brand_id = get_dashboard_brand(request)
    bot = _bot_for_brand(request, brand_id)
    log.info(f"Dashboard triggered planning cascade for brand: {brand_id}")

    async def _cascade():
        for task in PLANNING_CASCADE:
            await safe_run(task, bot, brand_id)

    asyncio.create_task(_cascade())

    return HTMLResponse(
        f'<div class="run-status" '
        f'hx-get="/schedule/cascade/last-run?after={trigger_ts}" '
        f'hx-trigger="every 3s" hx-swap="outerHTML">'
        f'<span class="badge badge-running">Running planning cascade...</span>'
        f'</div>'
    )


@router.get("/schedule/cascade/last-run", response_class=HTMLResponse)
async def cascade_status(request: Request):
    """Poll endpoint for the planning cascade: reports progress task-by-task."""
    after = request.query_params.get("after", "")
    brand_id = get_dashboard_brand(request)

    rows = await query(
        "SELECT task_type, status, summary, error, duration_seconds, started_at "
        "FROM run_log WHERE task_type IN (?, ?, ?, ?) "
        "AND started_at >= ? AND brand_id = ? ORDER BY started_at",
        (*PLANNING_CASCADE, after, brand_id),
    )

    done_map = {r["task_type"]: r for r in rows}
    # Cascade is finished when the last stage has a terminal status
    last = done_map.get(PLANNING_CASCADE[-1])
    finished = last and last["status"] in ("completed", "failed", "skipped", "timeout")

    parts = []
    for task in PLANNING_CASCADE:
        r = done_map.get(task)
        if not r:
            parts.append(f'<span class="badge badge-running">{task}…</span>')
        else:
            parts.append(f'<span class="badge badge-{r["status"]}">{task}</span>')

    if finished:
        return HTMLResponse(
            '<div class="run-status">'
            + " ".join(parts)
            + "</div>"
        )
    return HTMLResponse(
        f'<div class="run-status" '
        f'hx-get="/schedule/cascade/last-run?after={after}" '
        f'hx-trigger="every 3s" hx-swap="outerHTML">'
        + " ".join(parts)
        + "</div>"
    )


@router.get("/schedule/{task_type}/last-run", response_class=HTMLResponse)
async def last_run_status(request: Request, task_type: str):
    """Poll endpoint: returns the latest run_log entry after the given timestamp."""
    after = request.query_params.get("after", "")
    brand_id = get_dashboard_brand(request)

    row = await query_one(
        "SELECT status, summary, error, duration_seconds FROM run_log "
        "WHERE task_type = ? AND started_at >= ? AND brand_id = ? ORDER BY started_at DESC LIMIT 1",
        (task_type, after, brand_id),
    )

    if not row:
        # Still running — keep polling
        return HTMLResponse(
            f'<div class="run-status" '
            f'hx-get="/schedule/{task_type}/last-run?after={after}" '
            f'hx-trigger="every 2s" hx-swap="outerHTML">'
            f'<span class="badge badge-running">Running {task_type}...</span>'
            f'</div>'
        )

    status = row["status"]
    detail = row.get("summary") or row.get("error") or ""
    duration = row.get("duration_seconds") or 0

    return HTMLResponse(
        f'<div class="run-status">'
        f'<span class="badge badge-{status}">{status}</span>'
        f'<span class="text-xs opacity-50 ml-2">{duration:.1f}s</span>'
        f'<div class="text-xs opacity-50 mt-1">{detail[:200]}</div>'
        f'</div>'
    )
