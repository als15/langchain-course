"""System info page."""

import os
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from web import templates
from web.db import query_one
from web.brand_switcher import get_dashboard_brand, get_brand_context

router = APIRouter()


@router.get("/system", response_class=HTMLResponse)
async def system_page(request: Request):
    from web.routes.dashboard import _global_stats

    brand_id = get_dashboard_brand(request)

    # Table counts (filtered by brand for content tables)
    counts = await query_one(
        "SELECT "
        "(SELECT COUNT(*) FROM content_queue WHERE brand_id = ?) as content_count, "
        "(SELECT COUNT(*) FROM leads WHERE brand_id = ?) as leads_count, "
        "(SELECT COUNT(*) FROM engagement_tasks WHERE brand_id = ?) as engagement_count, "
        "(SELECT COUNT(*) FROM run_log WHERE brand_id = ?) as run_count, "
        "(SELECT COUNT(*) FROM analytics_snapshots WHERE brand_id = ?) as snapshot_count, "
        "(SELECT COUNT(*) FROM post_performance WHERE brand_id = ?) as perf_count",
        (brand_id, brand_id, brand_id, brand_id, brand_id, brand_id),
    )

    # Meta token info
    token_file = Path("data/meta_token.txt")
    token_info = {}
    if token_file.exists():
        stat = token_file.stat()
        from datetime import datetime
        mtime = datetime.fromtimestamp(stat.st_mtime)
        token_info["last_refresh"] = mtime.strftime("%Y-%m-%d %H:%M")
        days_since = (datetime.now() - mtime).days
        token_info["days_since"] = days_since
        token_info["days_remaining"] = max(0, 50 - days_since)

    # System info
    db_url = os.environ.get("DATABASE_URL", "")
    sys_info = {
        "db_type": "PostgreSQL" if db_url.startswith("postgres") else "SQLite",
        "llm_provider": os.environ.get("LLM_PROVIDER", "ollama"),
        "timezone": "Asia/Jerusalem",
    }

    # Daemon log tail (system-wide, not filtered by brand)
    log_lines = []
    log_path = Path("data/daemon.log")
    if log_path.exists():
        try:
            with open(log_path, "r") as f:
                all_lines = f.readlines()
                log_lines = all_lines[-50:]
        except Exception:
            pass

    # Scheduler jobs (system-wide, not filtered by brand)
    scheduler_jobs = []
    scheduler = request.app.state.scheduler
    if scheduler:
        for job in scheduler.get_jobs():
            next_run = job.next_run_time
            scheduler_jobs.append({
                "id": job.id,
                "trigger": str(job.trigger),
                "next_run": next_run.strftime("%Y-%m-%d %H:%M") if next_run else "—",
            })

    stats = await _global_stats(brand_id)

    return templates.TemplateResponse(request, "pages/system.html", {
        "active_page": "system",
        "stats": stats,
        "counts": counts or {},
        "token_info": token_info,
        "sys_info": sys_info,
        "log_lines": log_lines,
        "scheduler_jobs": scheduler_jobs,
        **get_brand_context(request),
    })
