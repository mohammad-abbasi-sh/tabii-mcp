"""Daily live smoke for tabii_mcp — one fixed probe: the Turkish
homepage (5 sections, 15 live channels) + the pinned show Gassal
via the public API. Fails visibly on 403/timeout.

Run: python tests/smoke_live.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from tabii_mcp import http as H
from tabii_mcp import tabii as T


def main() -> int:
    home = T.parse_homepage(H.fetch_home_html("tr"), "tr")
    assert len(home["sections"]) == 5, home["sections"]
    assert len(home["live_channels"]) == 15, len(home["live_channels"])
    assert home["live_channels"][0]["title"] == "TRT 1"
    show = T.parse_show(H.fetch_show_json(438813, "tr"), "tr")
    assert show["title"] == "Gassal", show["title"]
    assert show["season_count"] == 3
    print(f"smoke OK: {len(home['sections'])} sections, "
          f"{len(home['live_channels'])} live channels, "
          f"show={show['title']} ({show['season_count']} seasons)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
