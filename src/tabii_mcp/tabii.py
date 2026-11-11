"""Parsers for tabii_mcp — pure functions over fetched HTML/JSON.

Sources:
- Homepage __NEXT_DATA__ (promoter sections + live channels).
- Public catalog API JSON (catalog/v1/public/shows/{id},
  catalog/v1/public/persons/{id}).
- sitemap-en.xml (search index: show slugs + person ids).
"""
from __future__ import annotations

import json
import re

IMAGE_CDN = "https://cms-tabii-public-image.tabii.com/int/webp/w600/q84"
MAX_EPISODES = 60  # cap on episode rows returned per show

_NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
    re.S,
)
_LOC_RE = re.compile(r"<loc>(https://www\.tabii\.com/[a-z]{2}/(?:detail|person)/(\d+)(?:/([^<]*))?)</loc>")

# Turkish-insensitive folding for search: İ/I, ş, ğ, ü, ö, ç, ı.
_TR_UPPER = str.maketrans({"İ": "i", "I": "ı", "Ş": "ş", "Ğ": "ğ", "Ü": "ü", "Ö": "ö", "Ç": "ç"})
_TR_FOLD = (("ş", "s"), ("ğ", "g"), ("ü", "u"), ("ö", "o"), ("ç", "c"), ("ı", "i"))


def fold(text: str) -> str:
    """Lowercase + strip Turkish diacritics, for query matching."""
    s = (text or "").translate(_TR_UPPER).lower()
    for a, b in _TR_FOLD:
        s = s.replace(a, b)
    return s


def parse_next_data(html: str) -> dict:
    """Extract the __NEXT_DATA__ JSON payload from a tabii.com page."""
    m = _NEXT_DATA_RE.search(html)
    if not m:
        raise ValueError("no __NEXT_DATA__ payload found on the page")
    try:
        data = json.loads(m.group(1))
    except Exception as e:
        raise ValueError(f"invalid __NEXT_DATA__ JSON: {e}") from e
    return data.get("props", {}).get("pageProps", {}).get("data")


def _image_url(images: list | None, prefer=("main", "mainWithLogo", "cover")) -> str | None:
    if not images:
        return None
    by_type = {}
    for img in images:
        name = img.get("name")
        if name:
            by_type.setdefault(img.get("imageType"), name)
    for t in prefer:
        if by_type.get(t):
            return f"{IMAGE_CDN}/{by_type[t]}"
    for name in by_type.values():
        return f"{IMAGE_CDN}/{name}"
    return None


def _hls_url(media: list | None) -> str | None:
    for m in media or []:
        if m.get("type") == "hls" and m.get("url"):
            return m["url"]
    return None


def parse_homepage(html: str, language: str = "tr") -> dict:
    """Homepage sections from __NEXT_DATA__.

    Returns {"sections": [{title, items: [{id, slug, title,
    description}]}], "live_channels": [{id, title, slug, watch_url,
    stream_url}], "faq_count": int}."""
    data = parse_next_data(html)
    if not isinstance(data, dict):
        raise ValueError("homepage __NEXT_DATA__ has no page data")
    sections = []
    for sec in data.get("promoter") or []:
        items = []
        for it in sec.get("items") or []:
            desc = (it.get("description") or "").strip()
            items.append({
                "id": it.get("id"),
                "slug": it.get("slug"),
                "title": (it.get("title") or "").strip(),
                "description": desc[:200] if desc else "",
            })
        if items:
            sections.append({"title": (sec.get("title") or "").strip(), "items": items})
    live_channels = []
    for sec in data.get("liveStreamPromoter") or []:
        for it in sec.get("items") or []:
            slug = it.get("slug") or ""
            live_channels.append({
                "id": it.get("id"),
                "title": (it.get("title") or "").strip(),
                "slug": slug,
                "watch_url": (
                    f"https://www.tabii.com/{language}/watch/live/{slug}"
                    f"?trackId={it.get('id')}" if slug else ""
                ),
                "stream_url": _hls_url(it.get("media")),
            })
    faq = data.get("faq") or []
    faq_count = len((faq[0].get("items") or []) if faq else [])
    return {"sections": sections, "live_channels": live_channels,
            "faq_count": faq_count}


def parse_show(data: dict, language: str = "tr") -> dict:
    """Compact a public show JSON object (catalog/v1/public/shows)."""
    show_id = data.get("id")
    slug = data.get("slug") or ""
    genres = [
        {"id": g.get("id"), "title": g.get("title")}
        for g in data.get("genres") or [] if g.get("title")
    ]
    seasons = []
    total_eps = 0
    truncated = False
    for s in data.get("seasons") or []:
        eps = []
        for ep in s.get("episodes") or []:
            if total_eps >= MAX_EPISODES:
                truncated = True
                break
            eps.append({
                "number": ep.get("episodeNumber"),
                "title": (ep.get("title") or "").strip(),
                "duration_sec": ep.get("duration"),
            })
            total_eps += 1
        seasons.append({
            "season": s.get("seasonNumber"),
            "episode_count": len(s.get("episodes") or []),
            "episodes": eps,
        })
        if truncated:
            break
    loc = data.get("localization") or {}
    return {
        "id": show_id,
        "slug": slug,
        "title": (data.get("title") or "").strip(),
        "original_title": data.get("originalTitle") or "",
        "content_type": data.get("contentType") or "",
        "made_year": data.get("madeYear"),
        "genres": genres,
        "categories": [
            c.get("title") for c in data.get("categories") or [] if c.get("title")
        ],
        "age_restriction": data.get("ageRestriction") or "",
        "season_count": data.get("seasonCount"),
        "seasons": seasons,
        "episodes_truncated": truncated,
        "casts": [
            {"id": p.get("id"), "name": p.get("title")}
            for p in data.get("casts") or [] if p.get("title")
        ],
        "directors": [
            {"id": p.get("id"), "name": p.get("title")}
            for p in data.get("directors") or [] if p.get("title")
        ],
        "writers": [
            {"id": p.get("id"), "name": p.get("title")}
            for p in data.get("writers") or [] if p.get("title")
        ],
        "description": (data.get("description") or "").strip(),
        "spot": (data.get("spot") or "").strip(),
        "audio_languages": [
            a.get("language") for a in loc.get("audios") or [] if a.get("language")
        ],
        "subtitle_languages": [
            s.get("language") for s in loc.get("subtitles") or [] if s.get("language")
        ],
        "badges": [b.get("title") for b in data.get("badges") or [] if b.get("title")],
        "trailer_count": len(data.get("trailers") or []),
        "can_watch_offline": bool(data.get("canWatchOffline")),
        "url": (
            f"https://www.tabii.com/{language}/detail/{show_id}/{slug}"
            if show_id and slug else ""
        ),
        "image_url": _image_url(data.get("images")),
    }


def parse_person(data: dict, language: str = "tr") -> dict:
    """Compact a public person JSON object
    (catalog/v1/public/persons)."""
    shows = []
    for s in data.get("discography") or []:
        shows.append({
            "id": s.get("id"),
            "title": (s.get("title") or "").strip(),
            "original_title": s.get("originalTitle") or "",
            "content_type": s.get("contentType") or "",
            "made_year": s.get("madeYear"),
            "genres": [g.get("title") for g in s.get("genres") or [] if g.get("title")],
        })
    return {
        "id": data.get("id"),
        "name": (data.get("title") or data.get("description") or "").strip(),
        "job_title": data.get("jobTitle") or "",
        "content_type": data.get("contentType") or "",
        "show_count": len(shows),
        "shows": shows,
        "url": (
            f"https://www.tabii.com/{language}/person/{data.get('id')}"
            if data.get("id") else ""
        ),
    }


def parse_sitemap(xml: str) -> list[dict]:
    """Sitemap index entries: shows have id+slug, people have id
    only (person URLs carry no slug). Accepts any locale prefix
    (/en/, /tr/, ...)."""
    entries = []
    for url, id_s, slug in _LOC_RE.findall(xml):
        kind = "show" if "/detail/" in url else "person"
        entries.append({
            "kind": kind,
            "id": int(id_s),
            "slug": (slug or "").strip("/") or None,
            "url": url,
        })
    return entries


def merge_entries(*lists: list[dict]) -> list[dict]:
    """Merge sitemap entry lists, deduplicated by (kind, id)."""
    seen: dict[tuple[str, int], dict] = {}
    for entries in lists:
        for e in entries:
            key = (e["kind"], e["id"])
            if key not in seen:
                seen[key] = e
            elif not seen[key].get("slug") and e.get("slug"):
                seen[key]["slug"] = e["slug"]
    return list(seen.values())


def search_entries(entries: list[dict], query: str, limit: int = 5) -> list[dict]:
    """Rank show entries by a Turkish-insensitive substring match
    of the query against the slug (the original Turkish title).

    All query words must appear in the slug. Exact slug match
    first, then prefix, then shortest slug first."""
    q = fold(query).strip()
    if not q:
        return []
    words = q.split()
    q_hyphen = "-".join(words)
    scored = []
    for e in entries:
        if e["kind"] != "show" or not e["slug"]:
            continue
        slug_fold = fold(e["slug"].replace("-", " "))
        if not all(w in slug_fold for w in words):
            continue
        slug_h = fold(e["slug"])
        if slug_h == q_hyphen:
            rank = 0
        elif slug_h.startswith(q_hyphen):
            rank = 1
        else:
            rank = 2
        scored.append((rank, len(e["slug"]), e))
    scored.sort(key=lambda t: (t[0], t[1]))
    return [e for _, _, e in scored[:limit]]


def resolve_show_slug(entries: list[dict], slug: str) -> int | None:
    """Show id for a slug (exact, case-insensitive)."""
    want = fold(slug).strip().replace(" ", "-")
    for e in entries:
        if e["kind"] == "show" and e["slug"] and fold(e["slug"]) == want:
            return e["id"]
    return None
