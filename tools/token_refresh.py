"""Meta (Facebook Graph API) long-lived access token refresh.

Publishing uses the FB Login flow (graph.facebook.com/{ig-user-id}/media
with an FB user access token), so the refresh path must also use the FB
Login flow: `fb_exchange_token` against graph.facebook.com/oauth/access_token.
The earlier implementation called graph.instagram.com/refresh_access_token
with grant_type=ig_refresh_token — that endpoint is for the IG Login flow
and silently fails on FB user tokens, which is why short-lived bootstrap
tokens were dying after ~1–2h without ever being extended.

Tokens are stored in the brand_credentials table under the key
META_ACCESS_TOKEN so they survive Railway redeploys. The env var
MILA_META_ACCESS_TOKEN (and equivalents for other brands) is used only
for bootstrap — once a refresh has written to the DB, the DB is
canonical.

See GitHub issue #1 for the incident that motivated persisting to the DB.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone

import requests

from tools.brand_credentials import (
    Credential,
    credential_expires_in_days,
    get_credential,
    set_credential,
)

log = logging.getLogger("capaco")

CREDENTIAL_KEY = "META_ACCESS_TOKEN"

# Fallback if the refresh API doesn't return an expires_in field.
# Instagram long-lived tokens are valid for 60 days.
_DEFAULT_TTL = timedelta(days=60)


def _read_current_token(brand_slug: str) -> str:
    """Pick the current token — DB first, then env var (bootstrap)."""
    cred = get_credential(brand_slug, CREDENTIAL_KEY)
    if cred and cred.value:
        return cred.value
    return os.environ.get("META_ACCESS_TOKEN", "")


def refresh_meta_token(brand_slug: str) -> str:
    """Exchange the current token for a long-lived (60-day) FB user token.

    Works for both a freshly-issued short-lived token (gets upgraded to
    long-lived) and an already-long-lived token (Meta returns a new
    long-lived token; note that this does not reset the 60-day clock when
    the input is already long-lived — that's a Meta constraint).

    Writes the new token (with computed expiry) to brand_credentials
    and updates os.environ for the current process. Returns the new token.
    """
    current_token = _read_current_token(brand_slug)
    if not current_token:
        raise RuntimeError(
            f"No META_ACCESS_TOKEN for brand {brand_slug}: neither DB nor env has one."
        )

    app_id = os.environ.get("META_APP_ID")
    app_secret = os.environ.get("META_APP_SECRET")
    if not app_id or not app_secret:
        raise RuntimeError(
            f"META_APP_ID / META_APP_SECRET missing for {brand_slug}; "
            "cannot exchange for long-lived token."
        )

    resp = requests.get(
        "https://graph.facebook.com/v21.0/oauth/access_token",
        params={
            "grant_type": "fb_exchange_token",
            "client_id": app_id,
            "client_secret": app_secret,
            "fb_exchange_token": current_token,
        },
        timeout=30,
    )
    resp.raise_for_status()
    body = resp.json()
    new_token = body["access_token"]
    expires_in_s = body.get("expires_in")

    if isinstance(expires_in_s, (int, float)) and expires_in_s > 0:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in_s)
    else:
        expires_at = datetime.now(timezone.utc) + _DEFAULT_TTL

    set_credential(brand_slug, CREDENTIAL_KEY, new_token, expires_at=expires_at)
    os.environ["META_ACCESS_TOKEN"] = new_token

    log.info(
        "Meta token refreshed for %s; new expiry %s",
        brand_slug,
        expires_at.isoformat(),
    )
    return new_token


def load_persisted_token(brand_slug: str) -> bool:
    """Hydrate os.environ['META_ACCESS_TOKEN'] from the DB for a brand.

    Returns True if a stored token was loaded, False if we fell through to
    whatever was already in the env (typically a bootstrap env var).
    """
    cred = get_credential(brand_slug, CREDENTIAL_KEY)
    if cred and cred.value:
        os.environ["META_ACCESS_TOKEN"] = cred.value
        log.info("Loaded persisted Meta token for %s from DB.", brand_slug)
        return True
    return False


def token_expires_in_days(brand_slug: str) -> int | None:
    """Days until the stored token expires. None if the DB has no record yet."""
    return credential_expires_in_days(brand_slug, CREDENTIAL_KEY)


def token_status(brand_slug: str) -> Credential | None:
    """Full credential record (value, expires_at, updated_at) for diagnostics."""
    return get_credential(brand_slug, CREDENTIAL_KEY)
