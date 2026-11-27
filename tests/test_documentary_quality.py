"""Regression tests for documentary quality gates, run history, and API read-back."""
import json
import re
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
        "scenario, not a claim about every river. SOLUTIONS: Communities can conserve water, repair leaking pipes, "
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


def good_ai_meta():
    narration = (
        "FACT: The UN's Independent International Scientific Panel on AI describes risks across "
        "economic, social, security and human-rights domains, and warns that safeguards may not be "
        "keeping pace with AI capabilities. "
        "FORECAST: If AI deployment spreads faster than oversight, concentrated control of data and "
        "computing could increase the influence of a small number of firms, although outcomes depend "
        "on regulation, competition, public accountability and local democratic oversight. "
        "WHAT-IF: Imagine a hypothetical future in which a few providers control critical AI systems; "
        "communities might struggle to challenge automated decisions, but this scenario is not an "
        "established event. "
        "SOLUTIONS: Public institutions can fund independent research, strengthen transparent rules, support "
        "competition and share oversight across borders. "
        "Which safeguard should be strengthened first?"
    )
    return {
        "topic": "Global AI governance and concentration of power",
        "title": "Who Sets the Rules for AI?",
        "description": "An evidence-led look at international AI governance and concentration risks.",
        "narration": narration,
        "sources": [
            {"title": "UN AI Panel", "url": "https://www.un.org/independent-international-scientific-panel-ai/en/preliminary-report"},
            {"title": "UN AI Governance", "url": "https://www.un.org/en/global-issues/artificial-intelligence"},
        ],
    }


class DocumentaryQualityTests(unittest.TestCase):
    def test_accepts_labeled_short_documentary(self):
        meta = good_meta()
        result = autopilot.validate_documentary_script(meta, TOPIC, "short")
        self.assertIs(result, meta)

    def test_ai_fact_accepts_formal_un_panel_name_with_possessive(self):
        meta = good_ai_meta()
        result = autopilot.validate_documentary_script(
            meta, "Global AI governance and concentration of power", "short"
        )
        self.assertIs(result, meta)

    def test_ai_fact_rejects_vague_attribution_without_named_institution(self):
        meta = good_ai_meta()
        meta["narration"] = meta["narration"].replace(
            "The UN's Independent International Scientific Panel on AI", "Independent private research groups and academic experts"
        )
        with self.assertRaisesRegex(ValueError, "institution from the matching evidence catalogue"):
            autopilot.validate_documentary_script(
                meta, "Global AI governance and concentration of power", "short"
            )

    def test_repairs_short_script_length_and_preserves_curated_sources(self):
        original = {
            "topic": TOPIC,
            "title": "Short test",
            "description": "A documentary test.",
            "narration": (
                "FACT: UN-Water documents water scarcity. "
                "FORECAST: Some basins may face pressure. "
                "WHAT-IF: Imagine a dry reservoir. "
                "SOLUTIONS: Communities can conserve water and repair pipes. "
                "What should leaders do first?"
            ),
            "visual_keywords": ["river basin", "water monitoring", "reservoir", "groundwater"],
            "sources": [
                {"title": "UN-Water", "url": "https://www.unwater.org/a"},
                {"title": "UNU-INWEH", "url": "https://www.unwater.org/b"},
            ],
        }
        expanded = good_meta()
        expanded["visual_keywords"] = ["river basin", "water monitoring", "reservoir", "groundwater"]
        expanded["sources"] = [{"title": "Unapproved source", "url": "https://example.com/fake"}]
        expanded["narration"] += (
            " Local plans should rely on measured conditions and transparent public information."
        )
        with patch.object(autopilot, "ask_ai", return_value=json.dumps(expanded)) as ask:
            repaired = autopilot.repair_short_script_length(original, TOPIC)
        count = len(re.findall(r"\b[\w’'-]+\b", repaired["narration"]))
        self.assertTrue(120 <= count <= 150)
        self.assertEqual(repaired["sources"], original["sources"])
        self.assertEqual(repaired["topic"], TOPIC)
        self.assertEqual(ask.call_count, 1)

    def test_short_script_length_repair_is_not_called_when_already_in_range(self):
        meta = good_meta()
        with patch.object(autopilot, "ask_ai") as ask:
            result = autopilot.repair_short_script_length(meta, TOPIC)
        self.assertIs(result, meta)
        ask.assert_not_called()

    def test_short_script_length_repair_skips_ai_within_validator_bounds(self):
        meta = good_meta()
        meta["narration"] = meta["narration"].replace(
            "The UNU-INWEH warns that overuse, pollution "
            "and climate pressure can push some rivers and aquifers into severe stress. ",
            "",
        )
        count = len(re.findall(r"\b[\w’'-]+\b", meta["narration"]))
        self.assertGreaterEqual(count, 110)
        self.assertLessEqual(count, 160)
        with patch.object(autopilot, "ask_ai") as ask:
            result = autopilot.repair_short_script_length(meta, TOPIC)
        self.assertIs(result, meta)
        ask.assert_not_called()

    def test_rejects_topic_drift(self):
        meta = good_meta()
        meta["topic"] = "AI and jobs"
        with self.assertRaisesRegex(ValueError, "topic drift"):
            autopilot.validate_documentary_script(meta, TOPIC, "short")

    def test_rejects_missing_solutions_label(self):
        meta = good_meta()
        meta["narration"] = meta["narration"].replace("SOLUTIONS:", "RESPONSE:")
        with self.assertRaisesRegex(ValueError, "missing labels: SOLUTIONS"):
            autopilot.validate_documentary_script(meta, TOPIC, "short")

    def test_requires_two_concrete_actions_inside_solutions_section(self):
        meta = good_meta()
        meta["narration"] = meta["narration"].replace(
            "SOLUTIONS: Communities can conserve water, repair leaking pipes, protect wetlands, "
            "monitor aquifers and plan fair sharing before a crisis grows.",
            "SOLUTIONS: Communities can discuss the issue and consider possible improvements "
            "before a crisis grows.",
        )
        with self.assertRaisesRegex(ValueError, "at least two concrete actions"):
            autopilot.validate_documentary_script(meta, TOPIC, "short")


    def test_solution_validator_accepts_establish_publish_and_provide_actions(self):
        meta = good_meta()
        meta["narration"] = meta["narration"].replace(
            "Communities can conserve water, repair leaking pipes, protect wetlands, "
            "monitor aquifers and plan fair sharing before a crisis grows.",
            "Local agencies can establish water-sharing agreements, publish transparent river data "
            "and provide drought training.",
        )
        autopilot.validate_documentary_script(meta, TOPIC, "short")

    def test_rejects_missing_fact_forecast_or_what_if_label(self):
        meta = good_meta()
        meta["narration"] = meta["narration"].replace("WHAT-IF:", "SCENARIO:")
        with self.assertRaisesRegex(ValueError, "missing labels"):
            autopilot.validate_documentary_script(meta, TOPIC, "short")

    def test_forecast_accepts_likely_as_an_uncertainty_qualifier(self):
        meta = good_meta()
        meta["narration"] = meta["narration"].replace(
            "some regions may face harder competition",
            "some regions are likely to face harder competition",
        )
        autopilot.validate_documentary_script(meta, TOPIC, "short")

    def test_forecast_accepts_not_inevitable_and_will_depend_on(self):
        meta = good_meta()
        meta["narration"] = meta["narration"].replace(
            "some regions may face harder competition for drinking water, food production "
            "and healthy rivers; the scale depends on local management, rainfall and investment.",
            "harder competition is not inevitable and will depend on local management, rainfall "
            "and investment across drinking water, food production and healthy rivers.",
        )
        autopilot.validate_documentary_script(meta, TOPIC, "short")

    def test_forecast_rejects_an_unqualified_certain_outcome(self):
        meta = good_meta()
        meta["narration"] = meta["narration"].replace(
            "If demand keeps rising and dry periods intensify, some regions may face harder "
            "competition for drinking water, food production and healthy rivers; the scale "
            "depends on local management, rainfall and investment.",
            "Dry periods will force every river basin into severe competition for drinking "
            "water, food production and healthy rivers by 2030.",
        )
        with self.assertRaisesRegex(ValueError, "qualify uncertainty"):
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



class ScriptCallBudgetTests(unittest.TestCase):
    def _write_script_call_count(self, polish_enabled):
        meta = good_meta()
        meta["visual_keywords"] = [
            "river basin", "water monitoring", "reservoir", "groundwater",
        ]
        payload = json.dumps(meta)
        settings = {"ENABLE_SCRIPT_POLISH": "true"} if polish_enabled else {}
        with patch.dict("os.environ", settings, clear=True), \
             patch.object(autopilot, "ask_ai", return_value=payload) as ask, \
             patch.object(autopilot, "repair_short_script_length",
                          side_effect=lambda value, topic: value), \
             patch.object(autopilot, "verify_source_links", side_effect=lambda value: value), \
             patch.object(autopilot, "validate_documentary_script",
                          side_effect=lambda value, expected_topic, fmt: value):
            result = autopilot.write_script(
                "short", "audience notes", {"posts": [], "runs": []},
                topic=TOPIC, include_visual_plan=False,
            )
        self.assertEqual(result["topic"], TOPIC)
        return ask.call_count

    def test_optional_polish_is_disabled_by_default_to_conserve_api_quota(self):
        self.assertEqual(self._write_script_call_count(False), 1)

    def test_optional_polish_remains_available_when_explicitly_enabled(self):
        self.assertEqual(self._write_script_call_count(True), 2)

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

    @patch.dict("os.environ", {}, clear=True)
    @patch.object(autopilot, "notify")
    def test_daily_report_counts_generated_runs_separately_from_posts(self, notify):
        report_date = "2026-11-22"
        history = {
            "posts": [],
            "runs": [{
                # Keep the fixture aligned with the date patched below; do not
                # depend on the real calendar date when the suite is executed.
                "time": f"{report_date}T09:00:00Z",
                "github_event": "schedule",
                "status": "completed_with_delivery_issues",
                "generated": True,
                "format": "short",
                "platforms": {
                    "youtube": {"status": "skipped"},
                    "facebook": {"status": "skipped"},
                    "instagram": {"status": "skipped"},
                    "tiktok": {"status": "skipped"},
                },
            }],
        }
        with patch.object(autopilot, "NOW", autopilot.dt.datetime(2026, 11, 22, 9, 17)), \
             patch.object(autopilot, "TODAY", report_date):
            autopilot.daily_report(history)
        report = notify.call_args.args[0]
        self.assertIn("Scheduled attempts recorded: 1", report)
        self.assertIn("cancelled: 0; missed slots (estimated): 3", report)
        self.assertIn("Videos generated: 1 (1 short, 0 long)", report)
        self.assertIn(
            "Verified platform deliveries: YouTube 0; Facebook 0; Instagram 0; TikTok inbox 0",
            report,
        )

    @patch.dict("os.environ", {}, clear=True)
    def test_daily_report_is_sent_when_generation_fails_in_report_slot(self):
        history = {"posts": [], "patterns": {}, "runs": []}
        with patch.object(autopilot, "NOW", autopilot.dt.datetime(2026, 11, 22, 22, 12)), \
             patch.object(autopilot, "REPORT_HOUR", 21), \
             patch.object(autopilot, "SCHEDULE_MINUTE", 17), \
             patch.object(autopilot, "load_history", return_value=history), \
             patch.object(autopilot, "pick_format", return_value="short"), \
             patch.object(autopilot, "choose_topic", return_value=TOPIC), \
             patch.object(autopilot, "research", return_value="curated evidence"), \
             patch.object(autopilot, "write_script", side_effect=RuntimeError("provider unavailable")), \
             patch.object(autopilot, "save_history"), \
             patch.object(autopilot, "notify"), \
             patch.object(autopilot, "daily_report") as report:
            with self.assertRaises(SystemExit):
                autopilot.main()
        report.assert_called_once_with(history)

    def test_report_slot_detection_tolerates_github_delay_without_duplicate_next_slot(self):
        with patch.object(autopilot, "REPORT_HOUR", 21), \
             patch.object(autopilot, "SCHEDULE_MINUTE", 17):
            self.assertTrue(
                autopilot.is_report_slot(autopilot.dt.datetime(2026, 11, 22, 22, 12))
            )
            self.assertFalse(
                autopilot.is_report_slot(autopilot.dt.datetime(2026, 11, 23, 0, 17))
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
