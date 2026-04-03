# Capa & Co - Instagram Agent System

## Overview

An autonomous AI agent system that manages the Instagram presence for **Capa & Co** (קאפה אנד קו), a B2B sandwich supplier serving food trucks and small coffee places in Israel.

The system runs 6 specialized agents on an automated schedule, generates photorealistic food images, sends approval requests via Telegram, publishes to Instagram, tracks analytics, discovers leads, and suggests engagement actions — all with minimal human intervention.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    daemon.py                            │
│         (APScheduler + Telegram Bot Polling)            │
│                                                         │
│  ┌──────────────┐    ┌────────────────────────┐        │
│  │   Scheduler  │    │    Telegram Bot         │        │
│  │              │    │                         │        │
│  │  Mon  07:00  │    │  /start  /status        │        │
│  │  Every 6h    │    │  /queue  /leads          │        │
│  │  Daily 12:00 │    │  /engage                │        │
│  │  Daily 18:00 │    │  [Approve] [Reject]     │        │
│  │  Tue/Thu     │    │                         │        │
│  │  Wed  10:00  │    └────────────────────────┘        │
│  │  Every 50d   │                                       │
│  └──────┬───────┘                                       │
│         │                                               │
│         ▼                                               │
│  ┌──────────────────────────────────────────┐          │
│  │         Orchestrator (StateGraph)         │          │
│  │                                           │          │
│  │  Routes task_type → Agent node            │          │
│  └──────────────┬───────────────────────────┘          │
│                 │                                       │
│    ┌────────────┼────────────┬──────────┐              │
│    ▼            ▼            ▼          ▼              │
│ ┌──────┐  ┌──────────┐  ┌───────┐  ┌────────┐        │
│ │Strat.│  │Image Gen │  │Analyt.│  │Lead Gen│  ...    │
│ │Agent │  │  Agent   │  │ Agent │  │ Agent  │        │
│ └──┬───┘  └────┬─────┘  └──┬────┘  └───┬────┘        │
│    │           │            │           │              │
│    ▼           ▼            ▼           ▼              │
│  ┌─────────────────────────────────────────┐          │
│  │              SQLite DB                   │          │
│  │  content_queue · leads · analytics       │          │
│  │  post_performance · engagement_tasks     │          │
│  └─────────────────────────────────────────┘          │
└─────────────────────────────────────────────────────────┘
         │                            │
         ▼                            ▼
   Instagram API              FLUX (fal.ai)
   (Meta Graph)               + imgbb hosting
```

## The 6 Agents

### 1. Content Strategist
**Purpose:** Plans the weekly content calendar.

- Checks current Instagram performance and analytics history
- Researches trending topics via Tavily web search
- Creates 3-5 new posts per run with Hebrew captions and English visual directions
- Rotates through 5 content pillars: product, behind-the-scenes, customer spotlight, industry tips, social proof
- Posts are saved as drafts in the content queue

**Schedule:** Monday at 07:00

### 2. Image Generator
**Purpose:** Creates photorealistic food images for draft posts.

- Picks up drafts that don't have images yet
- Builds detailed prompts following the brand style guide
- Generates images via FLUX AI (fal.ai) — the most photorealistic model available
- Uploads images to imgbb for permanent public URLs
- Updates post status to `pending_approval` and triggers Telegram notifications

**Style:** RAW photorealistic food photography. Vegetarian sandwiches only. Artisan bread, fresh ingredients, clean minimal background, magazine-quality, 85mm lens, f/2.8.

**Schedule:** Every 6 hours

### 3. Content Publisher
**Purpose:** Publishes approved posts to Instagram.

- Picks up posts with status `approved` and a valid image URL
- Publishes via Instagram Graph API (photo or carousel)
- Updates post status to `published` with the Instagram media ID

**Schedule:** Weekdays at 12:00

### 4. Analytics Agent
**Purpose:** Tracks Instagram performance and generates insights.

- Pulls account-level metrics (followers, reach, impressions)
- Analyzes individual post performance
- Compares with historical data to identify trends
- Saves daily snapshots with 2-3 actionable recommendations
- Feeds insights back into the Content Strategist's decision-making

**Schedule:** Daily at 18:00

### 5. Lead Generator
**Purpose:** Finds potential B2B customers.

- Searches for food trucks, coffee shops, restaurants, and catering companies
- Focuses on businesses that could benefit from a sandwich supplier
- Checks for duplicates before adding new leads
- Prioritizes quality over quantity (3-5 strong leads per run)

**Schedule:** Wednesday at 10:00

### 6. Engagement Advisor
**Purpose:** Suggests engagement actions to build relationships.

- Reviews current leads — these are engagement priorities
- Creates 5-10 suggested actions: comments, likes, follows
- Drafts authentic, non-salesy comments (under 150 characters)
- Actions are queued for human execution (the system never auto-comments)

**Schedule:** Tuesday and Thursday at 10:00

## Content Flow

```
 Content Strategist          Image Generator           Human              Publisher
       │                          │                     │                    │
       │  creates draft posts     │                     │                    │
       │  (Hebrew captions,       │                     │                    │
       │   English visual dir.)   │                     │                    │
       │                          │                     │                    │
       ├─── status: draft ───────►│                     │                    │
       │                          │ generates FLUX      │                    │
       │                          │ image, uploads to   │                    │
       │                          │ imgbb               │                    │
       │                          │                     │                    │
       │                          ├── Telegram ────────►│                    │
       │                          │   notification      │                    │
       │                          │   with image +      │  taps Approve     │
       │                          │   [Approve][Reject] │  or Reject        │
       │                          │                     │                    │
       │                          │   status:           │                    │
       │                          │   pending_approval  │                    │
       │                          │                     ├── status: ────────►│
       │                          │                     │   approved         │
       │                          │                     │                    │ publishes to
       │                          │                     │                    │ Instagram
       │                          │                     │                    │
       │                          │                     │                    │ status:
       │                          │                     │                    │ published
```

## Lead & Engagement Flow

```
 Lead Generator         Engagement Advisor          Human
       │                       │                      │
       │ finds prospects       │                      │
       │ via web search        │                      │
       │                       │                      │
       │ status: discovered    │                      │
       │                       │                      │
       ├──────────────────────►│                      │
       │                       │ suggests comments,   │
       │                       │ follows, likes       │
       │                       │                      │
       │                       ├─────────────────────►│
       │                       │  engagement tasks    │ executes manually
       │                       │  (status: pending)   │ on Instagram
       │                       │                      │
       │                       │                      │ marks as done
       │                       │                      │ in review.py
```

## What Requires Human Intervention

| Action | How | Frequency |
|--------|-----|-----------|
| **Approve/reject posts** | Tap buttons on Telegram | When images are generated |
| **Execute engagement tasks** | Manually comment/like/follow on Instagram | 2x per week |
| **Review leads** | Check `python review.py` or `/leads` on Telegram | Weekly |
| **Add OpenAI credits** | platform.openai.com (if using OpenAI on Railway) | As needed |
| **Refresh Meta token** | Automatic (every 50 days), manual if it fails | Rare |

Everything else runs autonomously.

## Where the System Runs

### Local Development
```bash
uv run python daemon.py              # Full daemon + Telegram bot
uv run python main.py content        # Run one agent manually
uv run python main.py interactive    # Chat with an agent
uv run python review.py              # Review dashboard
```
- Uses **Ollama** (llama3.1) as the LLM — free, runs locally
- Requires your machine to be on

### Production (Railway)
- Deployed as a Docker container running `daemon.py`
- Uses **OpenAI gpt-4o-mini** as the LLM (set `LLM_PROVIDER=openai`)
- Runs 24/7 on Railway cloud (~$5-10/month)
- SQLite on a persistent volume
- All interaction via Telegram on your phone

## Schedule Summary

| Day | Time | Agent | What Happens |
|-----|------|-------|-------------|
| Mon | 07:00 | Content Strategist | Plans 3-5 posts for the week |
| Mon-Sun | Every 6h | Image Generator | Generates images, sends Telegram approvals |
| Mon-Fri | 12:00 | Content Publisher | Publishes approved posts |
| Mon-Sun | 18:00 | Analytics Agent | Tracks performance, saves insights |
| Tue | 10:00 | Engagement Advisor | Suggests engagement actions |
| Wed | 10:00 | Lead Generator | Finds new B2B prospects |
| Thu | 10:00 | Engagement Advisor | Suggests engagement actions |
| Every 50d | — | Token Refresh | Refreshes Meta API token |

## Database Tables

| Table | Purpose | Key Statuses |
|-------|---------|-------------|
| `content_queue` | Post planning & publishing pipeline | draft → pending_approval → approved → published |
| `leads` | B2B prospect tracking | discovered → researched → contacted → converted |
| `analytics_snapshots` | Daily account performance snapshots | — |
| `post_performance` | Per-post engagement metrics | — |
| `engagement_tasks` | Suggested engagement actions | pending → done / skipped |
| `run_log` | Scheduler execution history | completed / failed |

## Environment Variables

| Variable | Purpose | Required |
|----------|---------|----------|
| `LLM_PROVIDER` | `ollama` (local) or `openai` (cloud) | Yes |
| `OPENAI_API_KEY` | OpenAI API key | If openai |
| `META_ACCESS_TOKEN` | Instagram Graph API token | Yes |
| `META_APP_ID` / `META_APP_SECRET` | Facebook app credentials | Yes |
| `INSTAGRAM_ACCOUNT_ID` | Instagram Business Account ID | Yes |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token from @BotFather | Yes |
| `TELEGRAM_CHAT_ID` | Your Telegram chat ID | Yes |
| `TELEGRAM_AUTHORIZED_USERS` | Comma-separated authorized user IDs | Recommended |
| `FAL_KEY` | fal.ai API key for FLUX image generation | Yes |
| `IMGBB_API_KEY` | imgbb API key for image hosting | Yes |
| `TAVILY_API_KEY` | Tavily API key for web search | Yes |
| `LANGSMITH_API_KEY` | LangSmith observability (optional) | No |
| `DATABASE_PATH` | Custom SQLite path (default: data/capaco.db) | No |

## CLI Commands

```bash
# Run agents manually
uv run python main.py content         # Content planning
uv run python main.py images          # Image generation
uv run python main.py analytics       # Analytics
uv run python main.py leads           # Lead generation
uv run python main.py engagement      # Engagement suggestions
uv run python main.py publish         # Publish approved posts
uv run python main.py interactive     # Chat with any agent

# Management
uv run python review.py               # Review dashboard
uv run python daemon.py               # Start autonomous daemon + Telegram bot
```

## Telegram Commands

| Command | Response |
|---------|----------|
| `/start` | Welcome message + available commands |
| `/status` | Content queue counts + last 5 runs |
| `/queue` | Active posts with status and image info |
| `/leads` | Last 10 leads with type and status |
| `/engage` | Pending engagement tasks |
| **[Approve]** button | Approves a post for publishing |
| **[Reject]** button | Rejects a post |
