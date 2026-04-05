"""Regenerate captions for pending posts using gpt-4o, without touching images."""

from dotenv import load_dotenv
load_dotenv()

from db.schema import init_db
from db.connection import get_db
from langchain_openai import ChatOpenAI
from tools.content_guide import get_dish_prompt

init_db()
db = get_db()
llm = ChatOpenAI(model="gpt-4o", temperature=0.8)

rows = db.execute(
    "SELECT id, topic, content_type, visual_direction, caption "
    "FROM content_queue WHERE status = 'pending_approval'"
).fetchall()

PROMPT = """You write Instagram captions for Capa & Co (קאפה אנד קו), a premium bakery in Israel.

RULES:
- Write in native Israeli Hebrew. Short, playful, warm, with personality.
- One-liner captions. Max 2 short sentences. Less is more.
- The caption MUST describe what is ACTUALLY IN THE IMAGE (see image description below).
  Do NOT mention things that aren't in the image.
- Do NOT mention food trucks, B2B, delivery, or business — this is a bakery Instagram page.
- Emojis: max one, only if natural. Don't overdo it.
- End with 3-5 hashtags, mix Hebrew and English.
- For stories: even shorter, casual, one line max.

TONE EXAMPLES:
- Butter Croissant: "אפשר להריח את החמאה דרך הטלפון :) #קאפהאנדקו #croissant #בייקרי"
- Grilled Halloumi: "כריך שהוא מעט יווני והמון ישראלי #קאפהאנדקו #halloumi #כריכים"
- Smoked Salmon: "קלאסיקה שקשה לעמוד בפניה, עם אקסטרה אהבה של קאפה אנד קו בפנים #סלמון #קאפהאנדקו #freshfood"

BAD EXAMPLES (never write like this):
- "בוקר טוב! הכריכים שלנו מוכנים למחר" ← generic corporate
- "גאווה גדולה לספק ללקוחותינו!" ← sounds translated
- "אבוקדו בצלחת" when there's no avocado in the image ← doesn't match image
- "מגישים לכם אהבה על גלגלים" when it's not a food truck ← irrelevant
- Using 3+ emojis ← too much

The image shows:
{image_description}

Content type: {content_type}

Return ONLY the caption text, nothing else."""

print(f"Regenerating captions for {len(rows)} posts...\n")

for row in rows:
    # Get the actual image description from the content guide
    dish_prompt = get_dish_prompt(row["visual_direction"])
    if dish_prompt:
        image_description = dish_prompt
    else:
        image_description = row["visual_direction"]

    prompt = PROMPT.format(
        content_type=row["content_type"],
        image_description=image_description,
    )
    result = llm.invoke(prompt)
    new_caption = result.content.strip().strip('"')

    db.execute("UPDATE content_queue SET caption = ? WHERE id = ?", (new_caption, row["id"]))
    db.commit()

    print(f"#{row['id']} [{row['content_type']}] {row['visual_direction']}")
    print(f"  IMG: {image_description[:70]}...")
    print(f"  NEW: {new_caption}")
    print()

print("Done! Run: source .venv/bin/activate; python -c \"...\" to send to Telegram.")
