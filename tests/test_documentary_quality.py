"""Regression tests for documentary quality gates, run history, and API read-back."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import autopilot


TOPIC = "Water scarcity and drying rivers"


def good_meta():
    narration = (
        "FACT: " + "documented " * 40
        + ". FORECAST: " + "credible " * 40
        + ". WHAT-IF: " + "hypothetical " * 40
        + ". What should communities do?"
    )
    return {
        "topic": TOPIC,
        "title": "Where the Rivers Are Going",
        "description": "An evidence-led investigation into water stress and practical responses.",
        "narration": narration,
        "sources": [{"title": "UN-Water", "url": "https://www.unwater.org/a"},
                    {"title": "UNU-INWEH", "url": "https://www.unwater.org/b"}],
    }


class DocumentaryQualityTests(unittest.TestCase):
    def test_accepts_labeled_short_documentary(self):
        meta = good_meta()
        result = autopilot.validate_documentary_script(meta, TOPIC, "short")
        self.assertIs(result, meta)

    def test_rejects_topic_drift(self):
        meta = good_meta()
        meta["topic"] = "AI and jobs"
        with self.assertRaisesRegex(ValueError, "topic drift"):
            autopilot.validate_documentary_script(meta, TOPIC, "short")

    def test_rejects_missing_fact_forecast_or_what_if_label(self):
        meta = good_meta()
        meta["narration"] = meta["narration"].replace("WHAT-IF:", "SCENARIO:")
        with self.assertRaisesRegex(ValueError, "missing labels"):
            autopilot.validate_documentary_script(meta, TOPIC, "short")

    def test_rejects_short_script_outside_word_range(self):
        meta = good_meta()
        meta["narration"] = "FACT: Evidence. FORECAST: Risk. WHAT-IF: Hypothetical. What now?"
        with self.assertRaisesRegex(ValueError, "110-160 words"):
            autopilot.validate_documentary_script(meta, TOPIC, "short")

    def test_requires_a_viewer_question(self):
        meta = good_meta()
        meta["narration"] = meta["narration"].rstrip("?") + "."
        with self.assertRaisesRegex(ValueError, "viewer question"):
            autopilot.validate_documentary_script(meta, TOPIC, "short")


class RunHistoryTests(unittest.TestCase):
    def test_legacy_history_gets_a_runs_collection_and_persists_it(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "history.json"
            path.write_text(json.dumps({"posts": [], "patterns": {}}), encoding="utf-8")
            with patch.object(autopilot, "HISTORY_FILE", path):
                history = autopilot.load_history()
                self.assertEqual(history["runs"], [])
                history["runs"].append({"status": "generation_failed"})
                autopilot.save_history(history)
                saved = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(saved["runs"][0]["status"], "generation_failed")


class PlatformReadBackTests(unittest.TestCase):
    @patch("googleapiclient.discovery.build")
    @patch.object(autopilot, "yt_credentials", return_value="test-credentials")
    def test_youtube_id_and_private_status_are_read_back(self, _creds, build):
        yt = build.return_value
        yt.videos.return_value.list.return_value.execute.return_value = {
            "items": [{
                "id": "youtube-123",
                "status": {"privacyStatus": "private"},
                "snippet": {"title": "Test documentary"},
            }]
        }
        result = autopilot.verify_youtube_upload("youtube-123")
        self.assertEqual(result["privacy_status"], "private")
        self.assertEqual(result["title"], "Test documentary")

    @patch.dict("os.environ", {"FB_PAGE_TOKEN": "test-token"}, clear=True)
    @patch("autopilot.requests.get")
    def test_facebook_page_reel_id_is_read_back(self, get):
        response = Mock(ok=True)
        response.json.return_value = {
            "id": "facebook-123",
            "permalink_url": "https://www.facebook.com/reel/123",
        }
        get.return_value = response
        result = autopilot.verify_facebook_reel("facebook-123")
        self.assertEqual(result["permalink"], "https://www.facebook.com/reel/123")

    @patch.dict("os.environ", {"FB_PAGE_TOKEN": "test-token"}, clear=True)
    @patch("autopilot.requests.get")
    def test_instagram_reel_id_and_media_type_are_read_back(self, get):
        response = Mock(ok=True)
        response.json.return_value = {
            "id": "instagram-123",
            "media_type": "VIDEO",
            "media_product_type": "REELS",
            "permalink": "https://www.instagram.com/reel/123/",
        }
        get.return_value = response
        result = autopilot.verify_instagram_reel("instagram-123")
        self.assertEqual(result["media_product_type"], "REELS")
        self.assertEqual(result["permalink"], "https://www.instagram.com/reel/123/")


if __name__ == "__main__":
    unittest.main()
