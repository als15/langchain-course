import os
import logging
import requests

log = logging.getLogger("capaco")


def refresh_meta_token() -> str:
    """Refresh the Instagram long-lived token. Should be called every ~50 days."""
    current_token = os.environ.get("META_ACCESS_TOKEN", "")

    # Try file-based token first (persists across restarts)
    token_path = os.path.join("data", "meta_token.txt")
    if os.path.exists(token_path):
        with open(token_path) as f:
            file_token = f.read().strip()
            if file_token:
                current_token = file_token

    resp = requests.get(
        "https://graph.instagram.com/refresh_access_token",
        params={
            "grant_type": "ig_refresh_token",
            "access_token": current_token,
        },
    )
    resp.raise_for_status()
    new_token = resp.json()["access_token"]

    # Update in-memory
    os.environ["META_ACCESS_TOKEN"] = new_token

    # Persist to file
    os.makedirs("data", exist_ok=True)
    with open(token_path, "w") as f:
        f.write(new_token)

    log.info("Meta token refreshed successfully.")
    return new_token


def load_persisted_token():
    """Load token from file if it exists (call on startup)."""
    token_path = os.path.join("data", "meta_token.txt")
    if os.path.exists(token_path):
        with open(token_path) as f:
            token = f.read().strip()
            if token:
                os.environ["META_ACCESS_TOKEN"] = token
                log.info("Loaded persisted Meta token from file.")
