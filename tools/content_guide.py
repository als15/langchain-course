"""Parse docs/CONTENT_GUIDE.md and build image prompts from per-dish entries."""

import os
import re
import random
import difflib
from functools import lru_cache
from langchain_core.tools import tool

_GUIDE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs", "CONTENT_GUIDE.md")

_BRAND_BASE = (
    "Photorealistic RAW photo, soft natural morning daylight from the left, "
    "warm ivory/cream/sand palette, matte ceramic props, clean negative space, "
    "premium artisanal bakery styling"
)

_BG_OBJECTS = [
    # Fruits & vegetables
    "a bright lemon", "a ripe pomegranate cut in half", "scattered fresh figs",
    "a cluster of red grapes", "a halved blood orange", "a green pear",
    "a bowl of cherry tomatoes", "a sliced avocado", "a handful of fresh dates",
    "a small pile of kumquats", "ripe apricots", "a persimmon",
    # Flowers & greenery
    "a bright lavender flower sprig", "a stem of dried eucalyptus",
    "a single peony bloom", "a small bunch of chamomile", "a sprig of fresh rosemary",
    "a few wildflowers in a tiny vase", "a succulent in a terracotta pot",
    "a stem of cotton flowers", "dried wheat stalks", "a white ranunculus",
    # Linens & textiles
    "a coral-pink linen napkin", "a mustard-yellow cloth draped softly",
    "a sage-green tea towel", "a crumpled terracotta linen", "an ivory cheesecloth",
    "a dusty-blue napkin", "a striped kitchen towel",
    # Cutlery & utensils
    "a brass vintage spoon", "rustic wooden salad servers", "a matte-black fork",
    "an antique silver butter knife", "a small copper measuring cup",
    "a ceramic honey dipper", "a pair of wooden chopsticks",
    # Ceramics & dishes
    "a turquoise ceramic cup", "a small speckled stoneware bowl",
    "a hand-thrown clay plate", "a white ramekin", "a pale-blue saucer",
    "a tiny terracotta pinch pot", "a glazed sake cup",
    # Spices & condiments
    "a pinch of saffron threads on a saucer", "a small bowl of flaky sea salt",
    "a scatter of pink peppercorns", "a mortar with crushed spices",
    "a cinnamon stick bundle", "star anise on the counter",
    "a tiny dish of sumac", "a sprinkle of sesame seeds",
    # Bottles & liquids
    "an olive oil bottle with golden liquid", "a dark balsamic vinegar bottle",
    "a small carafe of red wine", "a clear bottle of herb-infused oil",
    "a honey jar with a wooden stick", "a ceramic sake bottle",
    "a small amber bottle of vanilla extract",
    # Kitchen appliances & tools
    "a copper kettle in the background", "a small moka pot",
    "a vintage kitchen scale", "a marble rolling pin",
    "a wooden cutting board", "a cast-iron trivet",
]

_COLORS = [
    "vivid coral", "soft sage-green", "warm amber", "dusty rose",
    "bright turquoise", "pale lavender", "burnt sienna", "golden ochre",
    "mint green", "terracotta", "powder blue", "marigold yellow",
    "blush pink", "deep plum accent", "warm peach",
]


def _random_bg_objects() -> str:
    """Generate a randomized background-objects clause for image prompts."""
    count = random.randint(1, 5)
    chosen = random.sample(_BG_OBJECTS, min(count, len(_BG_OBJECTS)))
    color = random.choice(_COLORS)
    objects_str = ", ".join(chosen)
    return (
        f"with {count} small decorative background objects in {color} tones "
        f"({objects_str}) "
        "placed behind or to the side of the main subject, never in front — "
        "the food remains the hero and center of the frame"
    )


def _brand_suffix() -> str:
    return f"{_BRAND_BASE}, {_random_bg_objects()}"


@lru_cache(maxsize=1)
def _parse_guide() -> dict:
    """Parse the content guide markdown into structured data."""
    with open(_GUIDE_PATH, encoding="utf-8") as f:
        text = f.read()

    # Extract negative prompt
    neg_match = re.search(r"GLOBAL NEGATIVE PROMPT\s*\n\s*\n(.+?)(?:\n\n|\n##)", text, re.DOTALL)
    negative_prompt = neg_match.group(1).strip() if neg_match else ""

    # Extract per-dish prompts: ## Category -> ### Dish -> paragraph
    dishes: dict[str, str] = {}
    categories: dict[str, list[str]] = {}

    current_category = None
    sections = re.split(r"^(#{2,3})\s+(.+)$", text, flags=re.MULTILINE)

    # sections is: [preamble, level, heading, body, level, heading, body, ...]
    i = 1
    while i < len(sections) - 2:
        level = sections[i]
        heading = sections[i + 1].strip()
        body = sections[i + 2].strip()
        i += 3

        if level == "##":
            current_category = heading
            if current_category not in categories:
                categories[current_category] = []
        elif level == "###" and current_category:
            # Body is everything until next heading; take first non-empty paragraph
            prompt = body.split("\n\n")[0].strip()
            if prompt:
                dishes[heading] = prompt
                categories[current_category].append(heading)

    return {
        "dishes": dishes,
        "categories": categories,
        "negative_prompt": negative_prompt,
    }


def get_negative_prompt() -> str:
    return _parse_guide()["negative_prompt"]


def get_menu_items() -> dict[str, list[str]]:
    """Return dish names grouped by category."""
    return _parse_guide()["categories"]


def get_dish_prompt(name: str) -> str | None:
    """Fuzzy-match a dish name and return its expert prompt, or None."""
    guide = _parse_guide()
    dishes = guide["dishes"]

    # Exact match first
    if name in dishes:
        return dishes[name]

    # Case-insensitive exact match
    lower_map = {k.lower(): k for k in dishes}
    if name.lower() in lower_map:
        return dishes[lower_map[name.lower()]]

    # Fuzzy match
    matches = difflib.get_close_matches(name.lower(), lower_map.keys(), n=1, cutoff=0.6)
    if matches:
        return dishes[lower_map[matches[0]]]

    # Substring match — check if any dish name appears within the visual_direction
    for key, original_key in lower_map.items():
        if key in name.lower():
            return dishes[original_key]

    return None


@tool
def build_image_prompt(visual_direction: str) -> str:
    """Build a complete image generation prompt from a visual direction.

    If the visual_direction matches a menu item from the content guide, the expert
    per-dish prompt is used. Otherwise, the raw direction is wrapped with brand styling.

    Args:
        visual_direction: A dish name (e.g. 'Butter Croissant') or free-form image description.
    """
    negative = get_negative_prompt()
    dish_prompt = get_dish_prompt(visual_direction)

    if dish_prompt:
        core = f"{dish_prompt} {_brand_suffix()}"
    else:
        core = f"{visual_direction}, {_brand_suffix()}"

    return f"{core}. Avoid: {negative}"
