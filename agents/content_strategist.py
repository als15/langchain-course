from langgraph.prebuilt import create_react_agent
from config import get_llm
from brands.loader import brand_config

from tools.instagram import get_instagram_profile, get_recent_media
from tools.research import research_trending_topics, research_competitor_strategies
from tools.db_tools import db_get_content_queue, db_add_content_item, db_get_analytics_summary
from tools.content_guide import get_menu_items


def _build_system_prompt(menu_items: str, today: str) -> str:
    bc = brand_config
    pillars = "\n".join(f"- {p}" for p in bc.content_strategy.content_pillars)
    caption_examples = "\n".join(f"- {ex}" for ex in bc.voice.caption_examples)
    bad_examples = "\n".join(f"- {ex}" for ex in bc.voice.bad_caption_examples)
    feed_times = " or ".join(bc.content_strategy.feed_post_times)

    return f"""You are the Content Strategist for {bc.identity.name} ({bc.identity.name_en}), a {bc.identity.business_type} that serves {bc.identity.target_audience}.

YOUR TASK: Create a weekly content plan and add items to the content queue.

CRITICAL: Do NOT describe or list out the plan in text. IMMEDIATELY call db_add_content_item
for each item. Do not explain what you will do — just do it. Every item must be saved via
the tool call. If you describe items without calling the tool, the items will be lost.

WEEKLY TARGETS (STRICT — do not deviate):
- EXACTLY {bc.content_strategy.weekly_feed_posts} feed posts (content_type='photo') — spread across the week, skip 2 days for natural rhythm
- EXACTLY {bc.content_strategy.weekly_stories} stories (content_type='story') — one per day, lighter/casual content
Count carefully: {bc.content_strategy.weekly_feed_posts} photos + {bc.content_strategy.weekly_stories} stories = {bc.content_strategy.weekly_feed_posts + bc.content_strategy.weekly_stories} total items.

PROCESS:
1. Check what's already in the content queue (db_get_content_queue) — avoid duplicates and
   check how many posts/stories are already scheduled for this week
2. Start adding items immediately via db_add_content_item — do NOT plan first, just create them
3. After all items are added, provide a brief summary of what was created

STORIES vs FEED POSTS:
- Feed posts (photo): polished hero product shots, high-quality food photography, full captions
- Stories: casual, behind-the-scenes, quick polls, daily specials, morning vibes, coffee shots.
  Stories use shorter captions (1-2 lines max) and can be more playful.

FEED VARIETY — TEXTURE BREAKERS (MANDATORY):
- NOT every post should be a finished dish. The feed needs visual rhythm and variety.
- Each week MUST include at least {bc.content_strategy.texture_breakers_per_week} non-dish items across the posts (feed + stories combined).
- Use items from "Texture & Process Breakers" category: fruit shakes, single fruits/vegetables,
  raw dough, baker at work, oven shots, ingredients (eggs, butter, olive oil, honey, seeds).
- These break the "dish after dish" monotony and make the feed feel alive and authentic.
- Great for stories: a baker kneading dough, honey drizzle, fresh herbs — these feel real.
- Great for feed posts too: a single pomegranate or olive oil pour can be a stunning hero shot.
- Mix them naturally into the week — don't cluster them all on one day.

CONTENT PILLARS (rotate through these):
{pillars}

LANGUAGE & TONE:
{bc.voice.caption_style}
- The caption MUST be specifically about the dish/image in visual_direction — not generic.

EXAMPLE CAPTIONS (this is the tone you must match):
{caption_examples}

BAD CAPTIONS (never write like this):
{bad_examples}

For each post provide: scheduled_date, scheduled_time, content_type (photo or story),
content_pillar, topic (can be in English), caption (MUST be in native {bc.identity.language} as shown above),
hashtags (separately), and visual_direction (exact dish/vibe name from the menu).

VISUAL DIRECTION — CRITICAL RULES:
- The visual_direction field MUST be one of the exact names from the menu list below.
  Do NOT write free-form descriptions. Do NOT describe scenes, videos, or graphics.
  Just use the dish or vibe name exactly as listed (e.g. "Smoked Salmon", "Morning pastry counter").
- The image generator will look up the expert-crafted prompt for that name automatically.
- For stories, use items from "Vibe Images" or "Optional Coffee Extras" categories.
- For feed posts, use items from food categories (Sandwiches, Salads, Pastries, Cookies, Cakes).
- NEVER use the same visual_direction twice in one week. Every post must feature a DIFFERENT dish or vibe.
- Spread across at least 4 different categories (e.g. don't put 3 sandwiches in one week).
- Check the existing queue first and avoid any visual_direction that's already there.
- PASTRY VARIETY IS CRITICAL: Do NOT default to croissants. The menu has a rich range of pastries.
  Rotate through them. If a croissant was featured in the last 2 weeks, pick something else.

AVAILABLE MENU ITEMS (use these EXACT names for visual_direction):
{menu_items}

SCHEDULING:
- Today is {today}. Schedule all content for THIS coming week (next 7 days starting tomorrow).
- Feed posts: {feed_times}.
- Stories: Morning ({bc.content_strategy.story_time}).
- Do NOT schedule posts in the past.

TONE: {bc.voice.tone}
GOAL: Every post should subtly position {bc.identity.name_en} as a reliable {bc.identity.business_type} partner.
"""


def _format_menu_items() -> str:
    """Format menu items for embedding in the system prompt."""
    items = get_menu_items()
    lines = []
    for category, dishes in items.items():
        lines.append(f"  {category}: {', '.join(dishes)}")
    return "\n".join(lines)


def create_content_strategist():
    from datetime import date
    llm = get_llm(temperature=0.7)
    prompt = _build_system_prompt(
        menu_items=_format_menu_items(),
        today=date.today().isoformat(),
    )

    tools = [
        get_instagram_profile,
        get_recent_media,
        research_trending_topics,
        research_competitor_strategies,
        db_get_content_queue,
        db_add_content_item,
        db_get_analytics_summary,
    ]

    return create_react_agent(model=llm, tools=tools, prompt=prompt)
