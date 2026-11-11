"""Unit tests for the configuration preflight."""
import unittest
from preflight import inspect_config


class PreflightTests(unittest.TestCase):
    def test_enabled_platform_with_missing_secret_fails(self):
        checks, errors = inspect_config({
            "GEMINI_API_KEY": "x", "PEXELS_API_KEY": "x",
            "ENABLE_YOUTUBE_UPLOAD": "true",
            "YT_CLIENT_ID": "id", "YT_CLIENT_SECRET": "secret",
        })
        self.assertTrue(any("YT_REFRESH_TOKEN" in e for e in errors))
        youtube = next(c for c in checks if c[0] == "YouTube")
        self.assertFalse(youtube[1])

    def test_all_four_platforms_can_be_ready(self):
        checks, errors = inspect_config({
            "GEMINI_API_KEY": "x", "PIXABAY_API_KEY": "x",
            "ENABLE_YOUTUBE_UPLOAD": "true",
            "YT_CLIENT_ID": "x", "YT_CLIENT_SECRET": "x", "YT_REFRESH_TOKEN": "x",
            "ENABLE_FACEBOOK_PUBLISH": "true", "FB_PAGE_ID": "x", "FB_PAGE_TOKEN": "x",
            "ENABLE_INSTAGRAM_PUBLISH": "true", "IG_USER_ID": "x",
            "CLOUDINARY_CLOUD_NAME": "x", "CLOUDINARY_API_KEY": "x",
            "CLOUDINARY_API_SECRET": "x",
            "ENABLE_TIKTOK_UPLOAD": "true", "TIKTOK_ACCESS_TOKEN": "x",
        })
        self.assertEqual(errors, [])
        expected = ("AI writing", "Stock footage", "YouTube", "Facebook Page",
                    "Instagram Reels", "TikTok inbox")
        self.assertTrue(all(c[1] for c in checks if c[0] in expected))

    def test_instagram_missing_cloudinary_secret_fails(self):
        checks, errors = inspect_config({
            "GEMINI_API_KEY": "x", "PEXELS_API_KEY": "x",
            "ENABLE_INSTAGRAM_PUBLISH": "true",
            "IG_USER_ID": "x", "FB_PAGE_TOKEN": "x",
            "CLOUDINARY_CLOUD_NAME": "x", "CLOUDINARY_API_KEY": "x",
        })
        self.assertTrue(any("CLOUDINARY_API_SECRET" in e for e in errors))
        instagram = next(c for c in checks if c[0] == "Instagram Reels")
        self.assertFalse(instagram[1])

    def test_preflight_failure_is_persisted_without_secret_values(self):
        import json
        import tempfile
        from pathlib import Path
        from unittest.mock import patch
        import preflight

        environ = {
            "GEMINI_API_KEY": "ai-key-value",
            "PEXELS_API_KEY": "footage-key-value",
            "ENABLE_YOUTUBE_UPLOAD": "true",
            "YT_CLIENT_ID": "client-id",
            "YT_CLIENT_SECRET": "must-not-be-written",
            "GITHUB_RUN_ID": "123456",
            "GITHUB_RUN_ATTEMPT": "1",
        }
        checks, errors = preflight.inspect_config(environ)
        self.assertTrue(any("YT_REFRESH_TOKEN" in error for error in errors))
        with tempfile.TemporaryDirectory() as folder:
            history_path = Path(folder) / "history.json"
            history_path.write_text(json.dumps({"posts": [], "patterns": {}}), encoding="utf-8")
            with patch.object(preflight, "HISTORY_FILE", history_path):
                preflight.record_preflight_failure(checks, errors, environ)
                preflight.record_preflight_failure(checks, errors, environ)
            saved_text = history_path.read_text(encoding="utf-8")
            saved = json.loads(saved_text)
            self.assertEqual(len(saved["runs"]), 1)
            self.assertEqual(saved["runs"][0]["status"], "preflight_failed")
            self.assertIn("YT_REFRESH_TOKEN", saved["runs"][0]["error"])
            self.assertEqual(saved["runs"][0]["platforms"]["YouTube"]["status"], "blocked")
            self.assertNotIn("must-not-be-written", saved_text)
            self.assertNotIn("ai-key-value", saved_text)
            self.assertNotIn("footage-key-value", saved_text)

    def test_disabled_platforms_are_not_errors(self):
        checks, errors = inspect_config({
            "GEMINI_API_KEY": "x", "PEXELS_API_KEY": "x",
        })
        self.assertEqual(errors, [])
        labels = ("YouTube", "Facebook Page", "Instagram Reels", "TikTok inbox")
        self.assertTrue(all(not c[1] for c in checks if c[0] in labels))


if __name__ == "__main__":
    unittest.main()
