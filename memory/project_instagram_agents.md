---
name: Instagram Agent System - Full Architecture
description: Multi-agent Instagram system with Telegram bot, Stability AI images, Railway deployment, auto token refresh
type: project
---

Fully autonomous Instagram management system for Capa & Co (@capa_ndco).

**6 Agents:** Content Strategist, Image Generator, Content Publisher, Analytics, Lead Generator, Engagement Advisor

**Key integrations:**
- Telegram bot for notifications and post approval (replaces CLI interrupt flow)
- Stability AI + imgbb for auto image generation
- APScheduler (async) for cron-like scheduling
- Meta token auto-refresh every 50 days
- LLM abstraction: Ollama locally, OpenAI gpt-4o-mini on Railway

**Content flow:** draft → image gen (Stability AI → imgbb) → pending_approval → Telegram approve → published

**Why:** User needs fully autonomous system that runs without their machine being on.
**How to apply:** Deploy to Railway with persistent volume for SQLite. All approval via Telegram.
