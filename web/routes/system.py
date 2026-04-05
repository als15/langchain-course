"""System info page."""

import os
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from web import templates
from web.db import query_one

router = APIRouter()


@router.get("/system", response_class=HTMLResponse)
async def system_page(request: Request):
    from web.routes.dashboard import _global_stats

    # Table counts
    counts = await query_one(
        "SELECT "
        "(SELECT COUNT(*) FROM content_queue) as content_count, "
        "(SELECT COUNT(*) FROM leads) as leads_count, "
        "(SELECT COUNT(*) FROM engagement_tasks) as engagement_count, "
        "(SELECT COUNT(*) FROM run_log) as run_count, "
        "(SELECT COUNT(*) FROM analytics_snapshots) as snapshot_count, "
        "(SELECT COUNT(*) FROM post_performance) as perf_count"
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

    # Daemon log tail
    log_lines = []
    log_path = Path("data/daemon.log")
    if log_path.exists():
        try:
            with open(log_path, "r") as f:
                all_lines = f.readlines()
                log_lines = all_lines[-50:]
        except Exception:
            pass

    # Scheduler jobs
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

    stats = await _global_stats()

    return templates.TemplateResponse(request, "pages/system.html", {
        "active_page": "system",
        "stats": stats,
        "counts": counts or {},
        "token_info": token_info,
        "sys_info": sys_info,
        "log_lines": log_lines,
        "scheduler_jobs": scheduler_jobs,
    })
