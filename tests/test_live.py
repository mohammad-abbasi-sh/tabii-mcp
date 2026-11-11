"""Live tests for tabii_mcp — real requests to tabii.com and the
public catalog API (no auth needed).

Requires network. The server is polite by design (~0.8s between
requests), so this file takes ~40s. Run:
    python -m unittest discover -s tests -v

Titles rotate on the homepage, so tests assert structure and sane
ranges, not exact featured lists — except the pinned show Gassal
(id 438813), which is a TRT original and stable.
"""
import json
import unittest

from tabii_mcp import http as H
from tabii_mcp import tabii as T

# Pinned TRT original, verified live 2026-11-11.
SHOW_ID = 438813
PERSON_ID = 6774  # Ahmet Kural


class TestLiveHomepage(unittest.TestCase):
    def test_sections(self):
        home = T.parse_homepage(H.fetch_home_html("tr"), "tr")
        self.assertEqual(len(home["sections"]), 5)
        for s in home["sections"]:
            self.assertTrue(s["title"])
            self.assertGreater(len(s["items"]), 10)
            for it in s["items"][:3]:
                self.assertTrue(it["id"])
                self.assertTrue(it["slug"])
                self.assertTrue(it["title"])

    def test_live_channels(self):
        home = T.parse_homepage(H.fetch_home_html("en"), "en")
        self.assertEqual(len(home["live_channels"]), 15)
        titles = [c["title"] for c in home["live_channels"]]
        self.assertIn("TRT 1", titles)
        self.assertIn("TRT WORLD", titles)
        for c in home["live_channels"]:
            self.assertIn("master.m3u8", c["stream_url"])
            self.assertIn("/watch/live/", c["watch_url"])


class TestLiveShow(unittest.TestCase):
    def test_pinned_show_tr(self):
        show = T.parse_show(H.fetch_show_json(SHOW_ID, "tr"), "tr")
        self.assertEqual(show["title"], "Gassal")
        self.assertEqual(show["content_type"], "series")
        self.assertEqual(show["season_count"], 3)
        self.assertGreater(len(show["casts"]), 0)

    def test_pinned_show_en(self):
        show = T.parse_show(H.fetch_show_json(SHOW_ID, "en"), "en")
        self.assertEqual(show["title"], "The Late Offices")
        self.assertEqual(show["original_title"], "Gassal")


class TestLivePerson(unittest.TestCase):
    def test_pinned_person(self):
        person = T.parse_person(H.fetch_person_json(PERSON_ID, "en"), "en")
        self.assertEqual(person["name"], "Ahmet Kural")
        self.assertGreaterEqual(person["show_count"], 1)
        ids = [s["id"] for s in person["shows"]]
        self.assertIn(SHOW_ID, ids)


class TestLiveSearch(unittest.TestCase):
    def test_search_index(self):
        entries = H.fetch_sitemap_entries()
        shows = [e for e in entries if e["kind"] == "show"]
        self.assertGreaterEqual(len(shows), 1300)
        hits = T.search_entries(entries, "gassal")
        self.assertEqual(hits[0]["id"], SHOW_ID)


class TestLiveServerTools(unittest.TestCase):
    def test_search_tool_json(self):
        from tabii_mcp import server as S

        out = json.loads(S.tabii_search_content("gassal", language="en", limit=3))
        self.assertIn("results", out)
        self.assertGreater(len(out["results"]), 0)
        self.assertEqual(out["results"][0]["id"], SHOW_ID)
        self.assertEqual(out["results"][0]["title"], "The Late Offices")
        self.assertEqual(out["source"], "tabii.com")

    def test_get_show_by_slug(self):
        from tabii_mcp import server as S

        out = json.loads(S.tabii_get_show(slug="gassal", language="tr"))
        self.assertEqual(out["id"], SHOW_ID)
        self.assertEqual(out["title"], "Gassal")

    def test_get_show_bad_slug(self):
        from tabii_mcp import server as S

        out = json.loads(S.tabii_get_show(slug="no-such-show-xyz"))
        self.assertIn("error", out)

    def test_live_channels_tool(self):
        from tabii_mcp import server as S

        out = json.loads(S.tabii_live_channels(language="tr"))
        self.assertEqual(out["count"], 15)
        self.assertEqual(out["channels"][0]["title"], "TRT 1")

    def test_health_tool(self):
        from tabii_mcp import server as S

        out = json.loads(S.tabii_health())
        self.assertEqual(out["status"], "ok")


if __name__ == "__main__":
    unittest.main()
