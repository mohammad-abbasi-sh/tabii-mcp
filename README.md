# tabii-mcp 🇹🇷

mcp-name: io.github.mohammad-abbasi-sh/tabii-mcp

Unofficial **read-only** MCP server for tabii.com, TRT's streaming platform (launched 2023, 11M+ subscribers) — Turkish series, movies, documentaries, kids content and 15 live TRT channels. Catalog search by original Turkish title, full show details (seasons, episodes, cast, languages), live-channel HLS stream URLs, and cast/crew filmographies.

> Built by Mohammad Abbasi as part of the "Turkey MCP factory" (Sepehr-style pipeline). Not affiliated with tabii.com or TRT.

## For AI agents

Add to your MCP client config (stdio):

```json
{
  "mcpServers": {
    "tabii": {
      "command": "uvx",
      "args": ["tabii-mcp==0.1.0"]
    }
  }
}
```

Or run locally: `python -m tabii_mcp.server` (needs `mcp<2`, `curl-cffi`).

## Tools

| Tool | Description |
|------|-------------|
| `tabii_search_content` | Search the catalog by original Turkish title (e.g. "gassal", "mevlana") — `language` ("tr" default, "en", "es", "ar", "ur"), `limit` 1..10; id, slug, localized title, original title, type, year, URL per match |
| `tabii_get_show` | Full detail of one title — `show_id` or `slug` (e.g. "gassal"); localized title, original title, type, year, genres, age restriction, seasons with episode titles + durations (capped at 60), cast, directors, writers, description, audio/subtitle languages, badges, trailer count, URL |
| `tabii_homepage` | Current homepage sections (exclusive content, series, movies, documentary, kids) with their titles — `language` |
| `tabii_live_channels` | The 15 live TRT channels (TRT 1, TRT 2, TRT Belgesel, TRT Haber, TRT Spor, TRT Çocuk, TRT World, ...) with watch URL and public HLS stream URL |
| `tabii_get_person` | One cast/crew member by numeric person id (e.g. Ahmet Kural is 6774) — name, job title, filmography on tabii |
| `tabii_health` | Reachability probe (homepage + one public show) — ok / blocked / error |

Example output (`tabii_search_content` / "gassal", language "en"):

```json
{"id": 438813, "slug": "gassal", "title": "The Late Offices",
 "original_title": "Gassal", "content_type": "series", "made_year": 2024,
 "url": "https://www.tabii.com/en/detail/438813/gassal"}
```

## How it works

tabii.com exposes a public catalog API that needs no login, no API key and no session token: `eu1.tabii.com/apigateway/catalog/v1/public/shows/{id}` and `.../public/persons/{id}` (the authenticated variants — `search/v1`, `catalog/v1/show/{id}` — return HTTP 401 without a Bearer session token and are not used). The homepage is server-rendered Next.js; its `__NEXT_DATA__` JSON carries the featured sections and the 15 live channels with their public HLS URLs. Search scans the site's own sitemaps (EN + TR merged: 1,306 shows, 1,180 people — cached 6h) and resolves the top matches' localized titles through the public shows API. Two things are documented, not worked around: the sitemaps do not cover the whole catalog (some licensed titles, e.g. The Hobbit, and some originals are absent — they are still reachable by id, e.g. via the homepage sections), and genre/category browse pages are client-side shells fed by a login-gated endpoint, so no genre-browse tool is offered. Playback needs a logged-in Tabii Premium session and is out of scope — this server is catalog metadata only. Transport uses Chrome TLS impersonation (`curl-cffi`, rotation); requests are spaced ~0.8s apart; everything is read-only.

## Install

```bash
uvx tabii-mcp==0.1.0        # run directly (needs uv)
# or
pip install tabii-mcp==0.1.0
tabii-mcp    # starts the MCP server on stdio
```

## Tests

```bash
python -m venv .venv && .venv/bin/pip install -e .
.venv/bin/python -m unittest discover -s tests -v
```

Offline tests run on recorded fixtures (real pages/API responses fetched 2026-11-11); live tests hit tabii.com and the public API. Tests green at build time (see repo for counts) plus an MCP stdio smoke test.

## Roadmap

- Genre browse if tabii ever publishes a session-free endpoint
- "New this week" / recently-added feed from the homepage sections
- Episode-level detail (per-episode description, audio/subtitle tracks)

## License

MIT — see [LICENSE](LICENSE).

---

Built by [Mohammad Abbasi](https://github.com/mohammad-abbasi-sh) — [Almanibama](https://almanibama.ir) · [mabbasi.ir](https://mabbasi.ir)
