import os
import unittest
from unittest.mock import patch

import autopilot
from evidence_library import TOPICS, evidence_catalogue_text, sources_for_topic


class EvidenceLibraryTests(unittest.TestCase):
    def test_every_topic_has_at_least_two_https_sources(self):
        for topic, item in TOPICS.items():
            with self.subTest(topic=topic):
                self.assertGreaterEqual(len(item["sources"]), 2)
                self.assertTrue(all(s["url"].startswith("https://") for s in item["sources"]))

    def test_catalogue_includes_topic_names_and_source_urls(self):
        catalogue = evidence_catalogue_text()
        for topic, item in TOPICS.items():
            with self.subTest(topic=topic):
                self.assertIn(topic, catalogue)
                self.assertIn(item["sources"][0]["url"], catalogue)

    def test_source_verifier_replaces_model_sources_with_curated_sources(self):
        class Reachable:
            ok = True
            url = "https://www.ilo.org/example"

        meta = {
            "topic": "AI and jobs",
            "sources": [{"title": "invented", "url": "https://example.invalid"}],
        }
        with patch("autopilot.requests.get", return_value=Reachable()):
            checked = autopilot.verify_source_links(meta)
        self.assertEqual(
            [s["url"] for s in checked["sources"]],
            [s["url"] for s in sources_for_topic("AI and jobs")],
        )
        self.assertNotEqual(checked["sources"][0]["title"], "invented")

    def test_unknown_topic_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unknown or unsupported"):
            autopilot.verify_source_links({"topic": "a made-up topic"})

    def test_youtube_audience_research_is_optional_without_oauth(self):
        with patch.dict(os.environ, {}, clear=True):
            result = autopilot.research("short", {"patterns": {}})
        self.assertIn("skipped", result.lower())
        self.assertIn("curated evidence catalogue", result.lower())


if __name__ == "__main__":
    unittest.main()
