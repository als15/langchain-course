import os
import base64
import requests
import fal_client
from langchain_core.tools import tool
from db.connection import get_db


def _generate_flux_image(prompt: str) -> str:
    """Call FLUX via fal.ai to generate an image. Returns the image URL directly."""
    os.environ["FAL_KEY"] = os.environ.get("FAL_KEY", "")

    result = fal_client.subscribe(
        "fal-ai/flux/dev",
        arguments={
            "prompt": prompt,
            "image_size": "square",
            "num_images": 1,
            "enable_safety_checker": False,
            "num_inference_steps": 28,
            "guidance_scale": 3.5,
        },
    )
    return result["images"][0]["url"]


def _upload_to_imgbb(image_bytes: bytes) -> str:
    """Upload image bytes to imgbb and return the public URL."""
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    resp = requests.post(
        "https://api.imgbb.com/1/upload",
        data={
            "key": os.environ["IMGBB_API_KEY"],
            "image": b64,
        },
    )
    resp.raise_for_status()
    return resp.json()["data"]["url"]


def _rehost_image(fal_url: str) -> str:
    """Download image from fal.ai temp URL and rehost on imgbb for permanent public URL."""
    resp = requests.get(fal_url)
    resp.raise_for_status()
    return _upload_to_imgbb(resp.content)


@tool
def generate_and_host_image(prompt: str, post_id: int) -> str:
    """Generate an image using FLUX AI from a text description, upload it to get a permanent public URL,
    and update the content queue item with the image URL and set status to pending_approval.
    Args:
        prompt: Detailed description of the image to generate. Be specific about composition, style, lighting.
        post_id: The content queue item ID to update with the generated image.
    """
    try:
        fal_url = _generate_flux_image(prompt)
        image_url = _rehost_image(fal_url)

        db = get_db()
        db.execute(
            "UPDATE content_queue SET image_url = ?, status = 'pending_approval' WHERE id = ?",
            (image_url, post_id),
        )
        db.commit()

        return f"Image generated and uploaded for post {post_id}. URL: {image_url}"
    except Exception as e:
        return f"Failed to generate image for post {post_id}: {e}"
