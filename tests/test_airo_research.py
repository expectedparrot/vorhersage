"""Research fidelity checks without network or model calls."""
import importlib.util
import sys
import unittest
from datetime import date
from pathlib import Path

EXAMPLE = Path(__file__).resolve().parents[1] / "examples/airo"
sys.path.insert(0, str(EXAMPLE))
try:
    import research_bridge as bridge
finally:
    sys.path.pop(0)


class ResearchTests(unittest.TestCase):
    def test_tavily_recency_uses_exact_news_dates(self):
        body = bridge.search_body({"query": "risk", "recent_days": 30, "max_results": 8}, date(2026, 9, 12))
        self.assertEqual(body, {"query": "risk", "max_results": 8, "search_depth": "advanced",
                               "include_answer": False, "topic": "news", "start_date": "2026-08-13", "end_date": "2026-09-12"})
        plain = bridge.search_body({"query": "base rates"}, date(2026, 9, 12))
        self.assertNotIn("start_date", plain)
        self.assertNotIn("topic", plain)
        self.assertTrue(plain["include_answer"])

    def test_page_windows_cover_saved_text_without_gaps(self):
        text = "0123456789" * 1701
        start, chunks = 0, []
        while True:
            window = bridge.page_window(text, start, "https://example.org")
            chunks.append(window["text"])
            self.assertEqual(window["total_chars"], len(text))
            self.assertLessEqual(len(window["text"]), 7000)
            if "next_offset" not in window:
                break
            start = window["next_offset"]
        self.assertEqual("".join(chunks), text)
        self.assertEqual(len(chunks), 3)


if __name__ == "__main__":
    unittest.main()
