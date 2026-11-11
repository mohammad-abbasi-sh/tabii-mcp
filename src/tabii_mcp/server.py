"""MCP server: unofficial read-only access to tabii.com (TRT's
streaming platform — Turkish series, movies, documentaries, kids
content and 15 live TRT channels)."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from mcp.server.fastmcp import FastMCP

from . import http as _http
from . import tabii as _T

mcp = FastMCP("tabii-mcp")

INSTRUCTIONS = """\
Unofficial read-only MCP server for tabii.com, TRT's streaming
platform (launched 2023, 11M+ subscribers) — Turkish series,
movies, documentaries, kids content and 15 live TRT channels.
tabii_search_content searches the catalog by the ORIGINAL
Turkish title (e.g. "gassal", "mevlana") — the site's own search
API needs a login, so search scans the site's sitemaps (1,306
titles) and resolves the top matches' localized titles through
the public catalog API; English titles (e.g. "The Late Offices")
are returned on the matches, but query with the Turkish title.
Some licensed titles are absent from the sitemaps and cannot be
found by search — they are still reachable by id, e.g. through
tabii_homepage's featured sections. tabii_get_show returns
full detail for one title by numeric id or slug: localized title,
original title, type (series/movie/documentary/...), year, genres,
age restriction, seasons with episode titles and durations, cast,
directors, writers, description, audio/subtitle languages and the
tabii.com URL. tabii_homepage returns the current featured
sections (exclusive content, series, movies, documentary, kids).
tabii_live_channels lists the 15 live TRT channels with their
public HLS stream URLs and watch URLs. tabii_get_person returns a
cast/crew member by numeric id (from a show's cast list) with
their filmography on tabii. All tools take an optional language
("tr" default, also "en", "es", "ar", "ur") — titles, descriptions
and genres come back in that language. Data comes from tabii.com's
public catalog API and server-rendered pages — no login, no API
key. Read-only; transport uses Chrome TLS impersonation; requests
are spaced ~0.8s apart. Playback needs a logged-in Tabii Premium
session and is out of scope — this server is catalog metadata
only. Genre/category browse is not offered: those pages are
client-side shells fed by a login-gated endpoint. Built by
Mohammad Abbasi (mohammad-abbasi-sh) — https://almanibama.ir ·
https://mabbasi.ir — Turkey MCP factory.\
"""

_SOURCE = "tabii.com"
_DISCLAIMER = "Unofficial read-only data from tabii.com; verify on the site before acting on it."


def _envelope() -> dict:
    return {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "source": _SOURCE,
        "disclaimer": _DISCLAIMER,
    }


def _ok(payload: dict) -> str:
    return json.dumps({**_envelope(), **payload}, ensure_ascii=False)


def _err(e: Exception) -> str:
    return _ok({"error": str(e)})


def _validate_limit(limit: int, lo: int = 1, hi: int = 10) -> int:
    if not lo <= limit <= hi:
        raise ValueError(f"limit must be between {lo} and {hi}")
    return limit


def _sitemap_entries() -> list[dict]:
    return _http.fetch_sitemap_entries()


@mcp.tool()
def tabii_search_content(query: str, language: str = "tr", limit: int = 5) -> str:
    """Search tabii's catalog by (original Turkish) title. query:
    a title or part of it, e.g. "gassal", "mevlana", "hobbit".
    language: "tr" (default), "en", "es", "ar" or "ur" — the
    returned titles are localized to it. limit 1..10 (default 5).
    Returns id, slug, localized title, original title, type, year
    and tabii.com URL per match. Note: matching is against the
    original Turkish title/slug (the site's own search needs a
    login) and covers the 1,306 titles in the site's sitemaps —
    some licensed titles (e.g. The Hobbit) are absent from the
    sitemaps and cannot be found this way; they are reachable by
    id via tabii_homepage's featured sections. English titles are
    shown on the matches but cannot be searched."""
    try:
        if not query or not str(query).strip():
            raise ValueError("query must not be empty")
        _validate_limit(limit)
        lang = _http.validate_language(language)
        entries = _sitemap_entries()
        matches = _T.search_entries(entries, str(query).strip(), limit)
        results = []
        for m in matches:
            row = {
                "id": m["id"],
                "slug": m["slug"],
                "title": None,
                "original_title": None,
                "content_type": None,
                "made_year": None,
                "url": f"https://www.tabii.com/{lang}/detail/{m['id']}/{m['slug']}",
            }
            try:
                data = _http.fetch_show_json(m["id"], lang)
                row["title"] = (data.get("title") or "").strip() or None
                row["original_title"] = data.get("originalTitle") or None
                row["content_type"] = data.get("contentType") or None
                row["made_year"] = data.get("madeYear")
            except _http.TabiiError:
                pass  # keep the sitemap match even if enrichment fails
            results.append(row)
    except (ValueError, _http.TabiiError) as e:
        return _err(e)
    return _ok({"query": str(query).strip(), "count": len(results), "results": results})


@mcp.tool()
def tabii_get_show(
    show_id: int | None = None,
    slug: str | None = None,
    language: str = "tr",
) -> str:
    """Full detail of one tabii title. Give show_id (numeric, from
    tabii_search_content) or slug (e.g. "gassal",
    "mevlana-celaleddin-i-rumi"). language: "tr" (default), "en",
    "es", "ar" or "ur". Returns localized title, original title,
    type, year, genres, age restriction, season count, seasons with
    episode titles + durations (capped at 60 episodes), cast,
    directors, writers, description, audio/subtitle languages,
    badges, trailer count and the tabii.com URL."""
    try:
        lang = _http.validate_language(language)
        if show_id is None:
            if not slug or not str(slug).strip():
                raise ValueError("give show_id or slug")
            entries = _sitemap_entries()
            resolved = _T.resolve_show_slug(entries, str(slug).strip())
            if resolved is None:
                raise ValueError(
                    f"no tabii title with slug {str(slug).strip()!r} — "
                    "search tabii_search_content for the right slug"
                )
            show_id = resolved
        data = _http.fetch_show_json(int(show_id), lang)
    except (ValueError, _http.TabiiError) as e:
        return _err(e)
    return _ok(_T.parse_show(data, lang))


@mcp.tool()
def tabii_homepage(language: str = "tr") -> str:
    """tabii's current homepage sections: exclusive content, series,
    movies, documentary and kids — each with its titles (id, slug,
    localized title, short description). language: "tr" (default),
    "en", "es", "ar" or "ur". No arguments besides language."""
    try:
        lang = _http.validate_language(language)
        html_text = _http.fetch_home_html(lang)
        home = _T.parse_homepage(html_text, lang)
    except (ValueError, _http.TabiiError) as e:
        return _err(e)
    return _ok({
        "language": lang,
        "section_count": len(home["sections"]),
        "sections": home["sections"],
        "live_channel_count": len(home["live_channels"]),
        "faq_count": home["faq_count"],
    })


@mcp.tool()
def tabii_live_channels(language: str = "tr") -> str:
    """The 15 live TRT channels on tabii (TRT 1, TRT 2, TRT Belgesel,
    TRT Haber, TRT Spor, TRT Çocuk, TRT World, ...), each with id,
    title, slug, watch URL and the public HLS stream URL.
    language: "tr" (default), "en", "es", "ar" or "ur". No
    arguments besides language. Note: the streams are the site's
    public HLS URLs; actual playback may still need a tabii login
    for some channels."""
    try:
        lang = _http.validate_language(language)
        html_text = _http.fetch_home_html(lang)
        home = _T.parse_homepage(html_text, lang)
    except (ValueError, _http.TabiiError) as e:
        return _err(e)
    return _ok({"count": len(home["live_channels"]), "channels": home["live_channels"]})


@mcp.tool()
def tabii_get_person(person_id: int, language: str = "tr") -> str:
    """One cast/crew member by numeric tabii person id (from a
    show's cast/directors/writers lists, e.g. Ahmet Kural is
    6774). language: "tr" (default), "en", "es", "ar" or "ur".
    Returns name, job title and their filmography on tabii (title,
    original title, type, year, genres per show)."""
    try:
        lang = _http.validate_language(language)
        if not person_id or int(person_id) <= 0:
            raise ValueError("person_id must be a positive integer")
        data = _http.fetch_person_json(int(person_id), lang)
    except (ValueError, _http.TabiiError) as e:
        return _err(e)
    return _ok(_T.parse_person(data, lang))


@mcp.tool()
def tabii_health() -> str:
    """Check whether tabii.com is reachable right now.

    Returns status ok (HTTP 200), blocked (HTTP 403/429 — bot wall or
    rate limit) or error, plus the HTTP status and the probed URL.
    Two polite requests (homepage + one public show); it does not
    fetch any listings."""
    return _ok(_http.health_check())


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
