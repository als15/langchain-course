"""Analytics page."""

import json

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from web import templates
from web.db import query, query_one

router = APIRouter()


@router.get("/analytics", response_class=HTMLResponse)
async def analytics_page(request: Request):
    from web.routes.dashboard import _global_stats

    days = int(request.query_params.get("days", "30"))

    # Snapshots time series
    snapshots = await query(
        "SELECT snapshot_date, follower_count, avg_engagement_rate, "
        "total_impressions, total_reach "
        "FROM analytics_snapshots ORDER BY snapshot_date DESC LIMIT ?",
        (days,),
    )
    snapshots.reverse()  # Chronological

    # Latest snapshot
    latest = await query_one(
        "SELECT * FROM analytics_snapshots ORDER BY snapshot_date DESC LIMIT 1"
    )

    # 7-day-ago snapshot for deltas
    prev = await query_one(
        "SELECT follower_count, avg_engagement_rate, total_impressions, total_reach "
        "FROM analytics_snapshots ORDER BY snapshot_date DESC LIMIT 1 OFFSET 7"
    )

    # Performance by pillar
    by_pillar = await query(
        "SELECT cq.content_pillar, COUNT(*) as post_count, "
        "AVG(pp.engagement) as avg_engagement, "
        "AVG(pp.impressions) as avg_impressions "
        "FROM post_performance pp "
        "JOIN content_queue cq ON cq.id = pp.content_queue_id "
        "GROUP BY cq.content_pillar"
    )

    # Top performing posts
    top_posts = await query(
        "SELECT pp.*, cq.topic, cq.content_pillar, cq.image_url, cq.content_type "
        "FROM post_performance pp "
        "JOIN content_queue cq ON cq.id = pp.content_queue_id "
        "ORDER BY pp.engagement DESC LIMIT 10"
    )

    # Latest AI recommendations
    reco = await query_one(
        "SELECT snapshot_date, recommendations FROM analytics_snapshots "
        "WHERE recommendations IS NOT NULL AND recommendations != '' "
        "ORDER BY snapshot_date DESC LIMIT 1"
    )

    stats = await _global_stats()

    return templates.TemplateResponse(request, "pages/analytics.html", {
        "active_page": "analytics",
        "stats": stats,
        "snapshots": snapshots,
        "snapshots_json": json.dumps(snapshots),
        "latest": latest or {},
        "prev": prev or {},
        "by_pillar": by_pillar,
        "by_pillar_json": json.dumps(by_pillar),
        "top_posts": top_posts,
        "reco": reco,
        "days": days,
    })
