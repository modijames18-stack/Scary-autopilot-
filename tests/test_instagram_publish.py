"""Tests for Instagram Reels publishing and the three-hour output format."""
import os
import tempfile
import unittest
from unittest.mock import Mock, patch

import autopilot


def response(payload, ok=True, status_code=200):
    return Mock(ok=ok, status_code=status_code, text="", json=lambda: payload)


class InstagramPublishingTests(unittest.TestCase):
    @patch.dict(os.environ, {
        "CLOUDINARY_CLOUD_NAME": "demo",
        "CLOUDINARY_API_KEY": "key",
        "CLOUDINARY_API_SECRET": "secret",
    })
    @patch("autopilot.time.time", return_value=123456)
    @patch("autopilot.requests.post")
    def test_cloudinary_returns_secure_video_url(self, post, _clock):
        post.return_value = response({"secure_url": "https://res.cloudinary.com/demo/video/upload/test.mp4"})
        with tempfile.NamedTemporaryFile(suffix=".mp4") as video:
            video.write(b"video")
            video.flush()
            url = autopilot.cloudinary_video_url(video.name)
        self.assertEqual(url, "https://res.cloudinary.com/demo/video/upload/test.mp4")
        self.assertIn("/video/upload", post.call_args.args[0])
        self.assertEqual(post.call_args.kwargs["data"]["timestamp"], 123456)
        self.assertEqual(post.call_args.kwargs["data"]["api_key"], "key")
        self.assertEqual(len(post.call_args.kwargs["data"]["signature"]), 40)

    @patch.dict(os.environ, {
        "IG_USER_ID": "ig-user",
        "FB_PAGE_TOKEN": "page-token",
        "CLOUDINARY_CLOUD_NAME": "demo",
        "CLOUDINARY_API_KEY": "key",
        "CLOUDINARY_API_SECRET": "secret",
    })
    @patch("autopilot.time.sleep")
    @patch("autopilot.requests.get")
    @patch("autopilot.requests.post")
    def test_instagram_reel_publishes_only_after_processing_finishes(self, post, get, _sleep):
        post.side_effect = [
            response({"secure_url": "https://res.cloudinary.com/demo/video/upload/test.mp4"}),
            response({"id": "container-123"}),
            response({"id": "media-456"}),
        ]
        get.return_value = response({"status_code": "FINISHED", "status": "Finished"})
        with tempfile.NamedTemporaryFile(suffix=".mp4") as video:
            video.write(b"video")
            video.flush()
            result = autopilot.post_instagram_reel(
                video.name,
                {"title": "Water crisis", "description": "A sourced report",
                 "sources": [{"title": "UN Water", "url": "https://www.unwater.org/report"}]},
                "short",
            )
        self.assertEqual(result, "media-456")
        self.assertEqual(get.call_count, 1)
        self.assertTrue(post.call_args.args[0].endswith("/ig-user/media_publish"))
        self.assertEqual(post.call_args.kwargs["data"]["creation_id"], "container-123")

    @patch.dict(os.environ, {}, clear=True)
    def test_instagram_fails_closed_without_credentials(self):
        with self.assertRaisesRegex(RuntimeError, "IG_USER_ID and FB_PAGE_TOKEN"):
            autopilot.post_instagram_reel("missing.mp4", {"title": "test"}, "short")

    @patch.dict(os.environ, {}, clear=True)
    def test_scheduled_format_is_short_for_all_four_platforms(self):
        self.assertEqual(autopilot.pick_format(), "short")


if __name__ == "__main__":
    unittest.main()
