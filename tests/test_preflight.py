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

    def test_all_three_platforms_can_be_ready(self):
        checks, errors = inspect_config({
            "GEMINI_API_KEY": "x", "PIXABAY_API_KEY": "x",
            "ENABLE_YOUTUBE_UPLOAD": "true",
            "YT_CLIENT_ID": "x", "YT_CLIENT_SECRET": "x", "YT_REFRESH_TOKEN": "x",
            "ENABLE_FACEBOOK_PUBLISH": "true", "FB_PAGE_ID": "x", "FB_PAGE_TOKEN": "x",
            "ENABLE_TIKTOK_UPLOAD": "true", "TIKTOK_ACCESS_TOKEN": "x",
        })
        self.assertEqual(errors, [])
        self.assertTrue(all(c[1] for c in checks if c[0] in
                            ("AI writing", "Stock footage", "YouTube", "Facebook Page", "TikTok inbox")))

    def test_disabled_platforms_are_not_errors(self):
        checks, errors = inspect_config({
            "GEMINI_API_KEY": "x", "PEXELS_API_KEY": "x",
        })
        self.assertEqual(errors, [])
        self.assertTrue(all(not c[1] for c in checks if c[0] in
                            ("YouTube", "Facebook Page", "TikTok inbox")))


if __name__ == "__main__":
    unittest.main()
