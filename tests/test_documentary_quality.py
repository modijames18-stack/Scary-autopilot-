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
        "FACT: UN-Water reports that water scarcity is already affecting communities, farms and ecosystems, "
        "while pressure varies sharply between river basins. The UNU-INWEH warns that overuse, pollution "
        "and climate pressure can push some rivers and aquifers into severe stress. "
        "FORECAST: If demand keeps rising and dry periods intensify, some regions may face harder competition "
        "for drinking water, food production and healthy rivers; the scale depends on local management, "
        "rainfall and investment. WHAT-IF: Imagine a basin where groundwater is pumped faster than rain can "
        "replace it. Wells could fail, harvests could shrink and families might pay more, but this is a "
        "scenario, not a claim about every river. Communities can conserve water, repair leaking pipes, "
        "protect wetlands, monitor aquifers and plan fair sharing before a crisis grows. "
        "Which action should leaders fund first?"
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

    def test_rejects_fictional_character_led_story(self):
        meta = good_meta()
        meta["narration"] = "One morning when Caleb heard a phone ring. " + meta["narration"]
        with self.assertRaisesRegex(ValueError, "Fictional story framing"):
            autopilot.validate_documentary_script(meta, TOPIC, "short")

    def test_fact_section_requires_institutional_attribution(self):
        meta = good_meta()
        meta["narration"] = meta["narration"].replace("UN-Water reports", "Researchers report")
        meta["narration"] = meta["narration"].replace("The UNU-INWEH warns", "Researchers warn")
        with self.assertRaisesRegex(ValueError, "institution from the matching evidence catalogue"):
            autopilot.validate_documentary_script(meta, TOPIC, "short")

    def test_what_if_must_be_explicitly_hypothetical(self):
        meta = good_meta()
        meta["narration"] = meta["narration"].replace("Imagine a basin", "A basin")
        meta["narration"] = meta["narration"].replace("this is a scenario", "this is a possibility")
        with self.assertRaisesRegex(ValueError, "WHAT-IF section must explicitly identify"):
            autopilot.validate_documentary_script(meta, TOPIC, "short")

    def test_question_repair_adds_a_closing_question(self):
        meta = good_meta()
        meta["narration"] = meta["narration"].rstrip("?") + "."
        repaired = autopilot.ensure_viewer_question(meta, "short")
        self.assertTrue(repaired["narration"].endswith("?"))
        self.assertIn("FACT:", repaired["narration"])
        self.assertIn("FORECAST:", repaired["narration"])
        self.assertIn("WHAT-IF:", repaired["narration"])

    def test_question_repair_preserves_existing_question(self):
        meta = good_meta()
        original = meta["narration"]
        autopilot.ensure_viewer_question(meta, "short")
        self.assertEqual(meta["narration"], original)

    def test_question_repair_rejects_overlength_short_script(self):
        meta = good_meta()
        meta["narration"] = ("FACT: " + "evidence " * 55
                             + "FORECAST: " + "risk " * 55
                             + "WHAT-IF: " + "scenario " * 55)
        with self.assertRaisesRegex(ValueError, "too long"):
            autopilot.ensure_viewer_question(meta, "short")


class RunHistoryTests(unittest.TestCase):
    def test_github_run_context_is_persisted_without_secrets(self):
        with patch.dict("os.environ", {
            "GITHUB_RUN_ID": "123456",
            "GITHUB_RUN_ATTEMPT": "2",
            "GITHUB_EVENT_NAME": "schedule",
        }, clear=True):
            self.assertEqual(autopilot.github_run_context(), {
                "github_run_id": "123456",
                "github_run_attempt": "2",
                "github_event": "schedule",
            })

    def test_disabled_platforms_are_delivery_issues_not_completion(self):
        platforms = {
            "youtube": {"status": "skipped"},
            "facebook": {"status": "skipped"},
            "instagram": {"status": "skipped"},
            "tiktok": {"status": "skipped"},
        }
        self.assertEqual(
            autopilot.delivery_completion_status(platforms),
            "completed_with_delivery_issues",
        )

    def test_no_platform_delivery_does_not_create_a_post_record(self):
        platforms = {
            "youtube": {"status": "skipped"},
            "facebook": {"status": "skipped"},
            "instagram": {"status": "skipped"},
            "tiktok": {"status": "skipped"},
        }
        self.assertFalse(autopilot.has_confirmed_delivery(platforms))

    def test_tiktok_inbox_is_a_confirmed_handoff_not_a_public_post(self):
        platforms = {"tiktok": {"status": "inbox_uploaded"}}
        self.assertTrue(autopilot.has_confirmed_delivery(platforms))

    def test_all_verified_handoffs_are_marked_completed(self):
        platforms = {
            "youtube": {"status": "verified_upload"},
            "facebook": {"status": "verified_publish"},
            "instagram": {"status": "verified_publish"},
            "tiktok": {"status": "inbox_uploaded"},
        }
        self.assertEqual(autopilot.delivery_completion_status(platforms), "completed")

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
