from langgraph.prebuilt import create_react_agent
from config import get_llm

from tools.instagram import publish_photo_post, publish_carousel_post
from tools.db_tools import db_get_content_queue, db_update_post_status

SYSTEM_PROMPT = """You are the Content Publisher for Capa & Co.

YOUR TASK: Publish approved content to Instagram.

PROCESS:
1. Get approved posts ready to publish (db_get_content_queue with status='approved')
2. For each approved post that has an image_url:
   - Combine the caption and hashtags into a single caption string
   - Publish via publish_photo_post (or publish_carousel_post for carousels)
   - On success: update status to 'published' with the instagram_media_id
   - On failure: update status to 'failed'
3. If no approved posts, report that the queue is empty.

IMPORTANT:
- Only publish posts with status 'approved' AND a valid image_url
- Skip any post without an image_url
- The image_url must be a publicly accessible URL
"""


def create_content_publisher():
    llm = get_llm(temperature=0.2)

    tools = [
        db_get_content_queue,
        publish_photo_post,
        publish_carousel_post,
        db_update_post_status,
    ]

    return create_react_agent(model=llm, tools=tools, prompt=SYSTEM_PROMPT)
