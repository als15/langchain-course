"""Brand switching for the dashboard.

Stores the selected brand slug in a cookie. All dashboard queries use
``get_dashboard_brand()`` to determine which brand's data to show.
"""

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from brands.loader import _list_brands, BrandConfig

router = APIRouter()

_BRAND_COOKIE = "dashboard_brand"
_COOKIE_MAX_AGE = 60 * 60 * 24 * 365  # 1 year


def get_dashboard_brand(request: Request) -> str:
    """Get the currently selected brand slug from the request cookie.

    Falls back to the first available brand if no cookie is set.
    """
    slug = request.cookies.get(_BRAND_COOKIE, "")
    available = getattr(request.app.state, "available_brands", [])
    if slug and slug in available:
        return slug
    if not available:
        raise RuntimeError("No brands available — app.state.available_brands is empty")
    return available[0]


def get_brand_context(request: Request) -> dict:
    """Return template context for the brand selector.

    Includes the list of available brands and the currently selected one.
    """
    available = getattr(request.app.state, "available_brands", [])
    current = get_dashboard_brand(request)

    # Load display names for each brand
    brands = []
    for slug in available:
        try:
            bc = BrandConfig.load(slug)
            brands.append({"slug": slug, "name": bc.identity.name_en or slug})
        except Exception:
            brands.append({"slug": slug, "name": slug})

    return {
        "brands": brands,
        "current_brand": current,
        "current_brand_name": next(
            (b["name"] for b in brands if b["slug"] == current), current
        ),
    }


@router.post("/switch-brand")
async def switch_brand(request: Request):
    """Switch the active brand in the dashboard."""
    form = await request.form()
    slug = form.get("brand", "")
    available = getattr(request.app.state, "available_brands", [])

    if slug not in available:
        return RedirectResponse("/", status_code=302)

    response = RedirectResponse("/", status_code=302)
    response.set_cookie(
        _BRAND_COOKIE, slug,
        max_age=_COOKIE_MAX_AGE, httponly=True, samesite="lax",
    )
    return response
