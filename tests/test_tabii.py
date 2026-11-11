"""Offline tests for tabii_mcp — recorded fixtures (real pages/API
responses fetched 2026-11-11). No network.

Run: python -m unittest discover -s tests -v
"""
import json
import unittest
from pathlib import Path

from tabii_mcp import tabii as T

FIX = Path(__file__).resolve().parent / "fixtures"


def _read(name: str) -> str:
    return (FIX / name).read_text(encoding="utf-8")


def _json(name: str) -> dict:
    return json.loads(_read(name))


class TestFold(unittest.TestCase):
    def test_turkish_folding(self):
        self.assertEqual(T.fold("IŞIK"), "isik")
        self.assertEqual(T.fold("Gassal"), "gassal")
        self.assertEqual(T.fold("Şehzade"), "sehzade")
        self.assertEqual(T.fold("GÖLGE"), "golge")
        self.assertEqual(T.fold("Çocuk"), "cocuk")


class TestSitemap(unittest.TestCase):
    def test_counts(self):
        entries = T.parse_sitemap(_read("sitemap-en.xml"))
        shows = [e for e in entries if e["kind"] == "show"]
        people = [e for e in entries if e["kind"] == "person"]
        self.assertEqual(len(shows), 1306)
        self.assertEqual(len(people), 1180)

    def test_tr_sitemap_same_shows_plus_three(self):
        entries = T.parse_sitemap(_read("sitemap-tr.xml"))
        shows = [e for e in entries if e["kind"] == "show"]
        self.assertEqual(len(shows), 1306)
        merged = T.merge_entries(
            T.parse_sitemap(_read("sitemap-en.xml")),
            T.parse_sitemap(_read("sitemap-tr.xml")),
        )
        merged_shows = [e for e in merged if e["kind"] == "show"]
        self.assertEqual(len(merged_shows), 1306)

    def test_known_entries(self):
        entries = T.parse_sitemap(_read("sitemap-en.xml"))
        by_slug = {e["slug"]: e for e in entries if e["slug"]}
        self.assertEqual(by_slug["gassal"]["id"], 438813)
        self.assertEqual(by_slug["mevlana-celaleddin-i-rumi"]["id"], 154554)
        people = [e for e in entries if e["kind"] == "person" and e["id"] == 6774]
        self.assertEqual(len(people), 1)
        self.assertIsNone(people[0]["slug"])  # person URLs carry no slug


class TestSearch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.entries = T.merge_entries(
            T.parse_sitemap(_read("sitemap-en.xml")),
            T.parse_sitemap(_read("sitemap-tr.xml")),
        )

    def test_exact(self):
        hits = T.search_entries(self.entries, "gassal")
        self.assertEqual(hits[0]["id"], 438813)

    def test_case_and_diacritic_insensitive(self):
        hits = T.search_entries(self.entries, "GASSAL")
        self.assertEqual(hits[0]["id"], 438813)
        hits = T.search_entries(self.entries, "Mevlana")
        self.assertEqual(hits[0]["id"], 154554)

    def test_multiword(self):
        hits = T.search_entries(self.entries, "mevlana celaleddin")
        self.assertEqual(hits[0]["id"], 154554)

    def test_no_match(self):
        self.assertEqual(T.search_entries(self.entries, "zzzqqq"), [])
        self.assertEqual(T.search_entries(self.entries, ""), [])

    def test_resolve_slug(self):
        self.assertEqual(T.resolve_show_slug(self.entries, "gassal"), 438813)
        self.assertEqual(T.resolve_show_slug(self.entries, "GASSAL"), 438813)
        self.assertIsNone(T.resolve_show_slug(self.entries, "no-such-show"))


class TestHomepage(unittest.TestCase):
    def test_tr_sections(self):
        home = T.parse_homepage(_read("home-tr.html"), "tr")
        self.assertEqual(len(home["sections"]), 5)
        titles = [s["title"] for s in home["sections"]]
        self.assertEqual(titles[0], "tabii'ye Özel İçerikler")
        self.assertEqual(titles[1], "Dizi")
        self.assertEqual(titles[2], "Film")
        counts = [len(s["items"]) for s in home["sections"]]
        self.assertEqual(counts, [22, 20, 20, 16, 20])
        first = home["sections"][1]["items"][0]
        self.assertEqual(first["slug"], "gassal")
        self.assertEqual(first["id"], 438813)

    def test_en_sections(self):
        home = T.parse_homepage(_read("home-en.html"), "en")
        self.assertEqual([s["title"] for s in home["sections"]],
                         ["Exclusive Content on tabii", "Series", "Movies",
                          "Documentary", "Kids"])
        self.assertEqual(home["sections"][1]["items"][0]["title"], "The Late Offices")

    def test_live_channels(self):
        home = T.parse_homepage(_read("home-tr.html"), "tr")
        self.assertEqual(len(home["live_channels"]), 15)
        ch = home["live_channels"][0]
        self.assertEqual(ch["title"], "TRT 1")
        self.assertEqual(ch["slug"], "trt1")
        self.assertEqual(ch["stream_url"], "https://tv-trt1.medya.trt.com.tr/master.m3u8")
        self.assertEqual(ch["watch_url"],
                         "https://www.tabii.com/tr/watch/live/trt1?trackId=150002")
        titles = [c["title"] for c in home["live_channels"]]
        self.assertIn("TRT WORLD", titles)
        self.assertIn("TRT ÇOCUK", titles)
        for c in home["live_channels"]:
            # TRT Spor / Spor Yıldız carry a ?app=clean query string
            self.assertIn("master.m3u8", c["stream_url"])

    def test_faq_count(self):
        self.assertEqual(T.parse_homepage(_read("home-tr.html"), "tr")["faq_count"], 7)
        self.assertEqual(T.parse_homepage(_read("home-en.html"), "en")["faq_count"], 6)

    def test_no_next_data(self):
        with self.assertRaises(ValueError):
            T.parse_next_data("<html><body>no data</body></html>")


class TestShow(unittest.TestCase):
    def test_gassal_tr(self):
        show = T.parse_show(_json("api-pub-show-tr.json")["data"], "tr")
        self.assertEqual(show["id"], 438813)
        self.assertEqual(show["slug"], "gassal")
        self.assertEqual(show["title"], "Gassal")
        self.assertEqual(show["original_title"], "Gassal")
        self.assertEqual(show["content_type"], "series")
        self.assertEqual(show["made_year"], 2024)
        self.assertEqual(show["genres"], [{"id": 69, "title": "Dram"},
                                          {"id": 71, "title": "Komedi"}])
        self.assertEqual(show["season_count"], 3)
        self.assertEqual([s["season"] for s in show["seasons"]], [1, 2, 3])
        self.assertEqual(show["seasons"][0]["episode_count"], 10)
        self.assertEqual(show["seasons"][0]["episodes"][0],
                         {"number": 1, "title": "1. Ben, Gassal", "duration_sec": 2092})
        self.assertEqual(show["casts"][0], {"id": 6774, "name": "Ahmet Kural"})
        self.assertEqual(show["directors"], [{"id": 11731, "name": "Selçuk Aydemir"}])
        self.assertEqual(show["writers"], [{"id": 154690, "name": "Sümeyye Karaarslan"}])
        self.assertEqual(show["audio_languages"], ["Türkçe - Sesli Betimleme"])
        self.assertIn("English", show["subtitle_languages"])
        self.assertIn("Urdu", show["subtitle_languages"])
        self.assertEqual(show["age_restriction"], "7+")
        self.assertEqual(show["trailer_count"], 4)
        self.assertFalse(show["episodes_truncated"])
        self.assertEqual(show["url"], "https://www.tabii.com/tr/detail/438813/gassal")
        self.assertTrue(show["image_url"].startswith(
            "https://cms-tabii-public-image.tabii.com/int/webp/w600/q84/"))

    def test_gassal_en_title_differs(self):
        show = T.parse_show(_json("api-pub-show-en.json")["data"], "en")
        self.assertEqual(show["title"], "The Late Offices")
        self.assertEqual(show["original_title"], "Gassal")
        self.assertEqual(show["genres"][0]["title"], "Drama")

    def test_detail_page_fallback(self):
        # The server-rendered detail page carries the same payload in
        # __NEXT_DATA__ — the fallback path for show detail.
        data = T.parse_next_data(_read("detail-tr.html"))
        show = T.parse_show(data, "tr")
        self.assertEqual(show["id"], 438813)
        self.assertEqual(show["title"], "Gassal")


class TestPerson(unittest.TestCase):
    def test_ahmet_kural(self):
        person = T.parse_person(_json("api-pub-person.json")["data"], "en")
        self.assertEqual(person["id"], 6774)
        self.assertEqual(person["name"], "Ahmet Kural")
        self.assertEqual(person["job_title"], "Actor")
        self.assertEqual(person["show_count"], 1)
        show = person["shows"][0]
        self.assertEqual(show["id"], 438813)
        self.assertEqual(show["title"], "The Late Offices")
        self.assertEqual(show["original_title"], "Gassal")
        self.assertEqual(show["content_type"], "series")
        self.assertEqual(show["made_year"], 2024)
        self.assertEqual(show["genres"], ["Drama", "Comedy"])
        self.assertEqual(person["url"], "https://www.tabii.com/en/person/6774")


if __name__ == "__main__":
    unittest.main()
