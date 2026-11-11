"""HTTP layer for tabii_mcp.

tabii.com is TRT's streaming platform (tabii — launched 2023,
11M+ subscribers, 13M Android installs). Two tokenless data
sources, verified live 2026-11-11:

1. The site's own public catalog API — no login, no API key, no
   session token:
   https://eu1.tabii.com/apigateway/catalog/v1/public/shows/{id}
   https://eu1.tabii.com/apigateway/catalog/v1/public/persons/{id}
   Both take an Accept-Language header (tr/en/es/ar/ur) and return
   full JSON. The authenticated variants (search/v1,
   catalog/v1/show/{id}, catalog/v1/person/{id}) return HTTP 401
   without a Bearer session token, so they are NOT used.

2. Server-rendered Next.js pages, whose __NEXT_DATA__ JSON carries
   the homepage sections (featured/series/movies/documentary/kids
   + the 15 live TRT channels with public HLS URLs) and the full
   detail payload as a fallback. Plain HTTP 200, no bot wall.

Search: the site's own search page is client-side and calls the
authenticated search/v1 endpoint, so there is no tokenless search
API. Search here scans the site's own sitemaps (EN + TR merged:
1,306 shows, 1,180 people) against the query, then resolves the
top matches' localized titles through the public shows API. The
sitemaps are cached in-process for 6 hours. Known gap: the
sitemaps do not cover the whole catalog — some licensed titles
(e.g. The Hobbit) and some originals are absent from both; those
titles are still reachable by id (e.g. via the homepage sections)
and the gap is documented in the tool text, not hidden.

Documented, not worked around:
- Genre/category browse pages (/genre/{id}) are client-side shells
  whose data comes from the authenticated
  catalog/v1/pages/genres/{id} endpoint (the guessed public
  variant 504s), so no genre-browse tool is offered.
- /live-channels/{id} returns HTTP 500 at build time; live
  channels are served from the homepage data instead.
- Playback itself (DRM streams, watch entitlement) needs a
  logged-in Tabii Premium session and is out of scope — this
  server is catalog metadata only, read-only.

Transport uses curl-cffi Chrome impersonation (the proven pattern
of the other Turkey-factory servers) even though the site answers
plain curl 200 today — it survives a future bot-wall tightening.
Requests are kept gentle (one at a time, ~0.8s apart) and
read-only. GET only.

VM note: on this VM outbound HTTPS goes through an egress proxy;
the MCP stdio client spawns servers with a minimal environment
(no proxy variables), so client-spawned runs here need the proxy
variables forwarded (see tests/smoke_mcp.py) or requests die
mid-TLS (curl 35, connection reset). On a normal machine with
direct internet this does not apply.
"""
from __future__ import annotations

import time
from urllib.parse import quote

from curl_cffi import requests as _r

BASE_WEB = "https://www.tabii.com"
BASE_API = "https://eu1.tabii.com/apigateway"
TIMEOUT = 30.0
MIN_INTERVAL = 0.8  # seconds between requests — be polite

LANGUAGES = ("tr", "en", "es", "ar", "ur")
DEFAULT_LANGUAGE = "tr"

SITEMAP_TTL = 6 * 3600  # seconds — sitemap is re-fetched at most every 6h

_HEADERS_HTML = {
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
}

_last_fetch = 0.0


class TabiiError(RuntimeError):
    pass


_PROFILES = ("chrome120", "chrome131", "safari17_0")
_MAX_ATTEMPTS = 2  # one retry with the next profile
_RETRY_BACKOFF = 1.0  # seconds between attempts
_profile_idx = 0  # sticky: profile that last succeeded

# In-process sitemap cache: {"fetched_at": float, "xml": str}
_sitemap_cache: dict = {}


def validate_language(language: str) -> str:
    lang = (language or "").strip().lower()
    if lang not in LANGUAGES:
        raise ValueError(
            f"unsupported language {language!r} — use one of: "
            + ", ".join(LANGUAGES)
        )
    return lang


def _request(url: str, headers: dict, timeout: float = TIMEOUT):
    """GET with fingerprint rotation.

    Starts at the sticky profile (chrome120 on a fresh process), retries
    once with the next profile on HTTP 403/429 or a transport error, then
    returns the last response (so the caller raises the specific 403/429
    error) or raises a network error if every attempt failed at the
    transport. Added 2026-11-10 (fleet audit fix).
    """
    global _profile_idx
    last_exc: Exception | None = None
    for k in range(_MAX_ATTEMPTS):
        profile = _PROFILES[(_profile_idx + k) % len(_PROFILES)]
        try:
            resp = _r.get(url, impersonate=profile, headers=headers, timeout=timeout)
        except Exception as e:
            last_exc = e
            if k + 1 < _MAX_ATTEMPTS:
                time.sleep(_RETRY_BACKOFF)
                continue
            raise TabiiError(f"network error fetching {url}: {e}") from e
        if resp.status_code in (403, 429):
            if k + 1 < _MAX_ATTEMPTS:
                time.sleep(_RETRY_BACKOFF)
                continue
            return resp
        _profile_idx = (_profile_idx + k) % len(_PROFILES)
        return resp
    raise TabiiError(f"network error fetching {url}: {last_exc}") from last_exc


def _get(url: str, headers: dict) -> bytes:
    global _last_fetch
    wait = MIN_INTERVAL - (time.monotonic() - _last_fetch)
    if wait > 0:
        time.sleep(wait)
    try:
        resp = _request(url, headers)
    except TabiiError:
        raise
    except Exception as e:
        raise TabiiError(f"network error fetching {url}: {e}") from e
    finally:
        _last_fetch = time.monotonic()
    if resp.status_code == 403:
        raise TabiiError(
            "tabii.com refused the request (HTTP 403, bot wall) — try again later"
        )
    if resp.status_code == 429:
        raise TabiiError(
            "tabii.com rate-limited the request (HTTP 429) — try again later"
        )
    if resp.status_code in (404, 410):
        raise TabiiError(f"page not found (HTTP {resp.status_code}): {url}")
    if resp.status_code == 400:
        raise TabiiError(
            f"tabii.com rejected the request (HTTP 400, invalid id?): {url}"
        )
    if resp.status_code != 200:
        raise TabiiError(f"unexpected HTTP {resp.status_code} fetching {url}")
    return resp.content


def fetch_home_html(language: str = DEFAULT_LANGUAGE) -> str:
    """Homepage for a locale (server-rendered, __NEXT_DATA__ carries
    the featured sections + live channels). /tr and /en are the
    locale roots; the bare root is English."""
    lang = validate_language(language)
    url = f"{BASE_WEB}/{lang}"
    return _get(url, _HEADERS_HTML).decode("utf-8", errors="replace")


def _api_headers(language: str) -> dict:
    return {
        "Accept": "application/json",
        "Accept-Language": validate_language(language),
        "User-Agent": "tabii-mcp/0.1.0",
    }


def fetch_show_json(show_id: int, language: str = DEFAULT_LANGUAGE) -> dict:
    """Public show detail JSON (no auth):
    catalog/v1/public/shows/{id}."""
    import json

    lang = validate_language(language)
    url = f"{BASE_API}/catalog/v1/public/shows/{int(show_id)}"
    raw = _get(url, _api_headers(lang))
    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception as e:
        raise TabiiError(f"invalid JSON from {url}: {e}") from e
    if not isinstance(data, dict) or "data" not in data:
        raise TabiiError(f"unexpected API response from {url}")
    return data["data"]


def fetch_person_json(person_id: int, language: str = DEFAULT_LANGUAGE) -> dict:
    """Public person detail JSON (no auth):
    catalog/v1/public/persons/{id}."""
    import json

    lang = validate_language(language)
    url = f"{BASE_API}/catalog/v1/public/persons/{int(person_id)}"
    raw = _get(url, _api_headers(lang))
    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception as e:
        raise TabiiError(f"invalid JSON from {url}: {e}") from e
    if not isinstance(data, dict) or "data" not in data:
        raise TabiiError(f"unexpected API response from {url}")
    return data["data"]


def fetch_sitemap_xml(language: str = "en") -> str:
    """One locale sitemap (sitemap-en.xml: 2,511 URLs; sitemap-tr.xml:
    1,456 URLs — the same 1,306 shows, far fewer people)."""
    lang = validate_language(language)
    url = f"{BASE_WEB}/sitemap-{lang}.xml"
    return _get(url, _HEADERS_HTML).decode("utf-8", errors="replace")


def fetch_sitemap_entries() -> list[dict]:
    """Merged search index from the EN + TR sitemaps (1,306 shows,
    1,180 people), deduplicated by (kind, id). Cached in-process
    for SITEMAP_TTL seconds. The sitemaps do not cover the whole
    catalog — some licensed titles (e.g. The Hobbit) and some
    originals are absent; that gap is documented, not hidden."""
    from . import tabii as _tabii

    now = time.monotonic()
    if _sitemap_cache.get("entries") and now - _sitemap_cache.get("fetched_at", 0) < SITEMAP_TTL:
        return _sitemap_cache["entries"]
    entries = _tabii.merge_entries(
        _tabii.parse_sitemap(fetch_sitemap_xml("en")),
        _tabii.parse_sitemap(fetch_sitemap_xml("tr")),
    )
    _sitemap_cache["entries"] = entries
    _sitemap_cache["fetched_at"] = now
    return entries


def health_check() -> dict:
    """Two polite probes of the source site: the Turkish homepage
    and one public show (Gassal, id 438813).

    Returns {"status": "ok"|"blocked"|"error", "http_status": int|None,
    "url": ..., "detail": ...}. Used by the `tabii_health` tool
    and the daily smoke CI."""
    url = f"{BASE_WEB}/tr"
    try:
        fetch_home_html("tr")
        fetch_show_json(438813, "tr")
    except TabiiError as e:
        msg = str(e)
        if "403" in msg:
            return {"status": "blocked", "http_status": 403, "url": url, "detail": msg}
        if "429" in msg:
            return {"status": "blocked", "http_status": 429, "url": url, "detail": msg}
        return {"status": "error", "http_status": None, "url": url, "detail": msg}
    return {"status": "ok", "http_status": 200, "url": url,
            "detail": "homepage + public show API both answer"}
