"""Tests for optional TikTok inbox upload integration."""
import os
import tempfile
import unittest
from unittest.mock import Mock, patch

import autopilot


class TikTokInboxUploadTests(unittest.TestCase):
    @patch.dict(os.environ, {"TIKTOK_ACCESS_TOKEN": "test-token"})
    @patch("autopilot.requests.put")
    @patch("autopilot.requests.post")
    def test_uploads_file_and_returns_publish_id(self, post, put):
        post.return_value = Mock(
            ok=True,
            json=lambda: {
                "data": {"publish_id": "test-publish-id", "upload_url": "https://upload.example/test"},
                "error": {"code": "ok", "message": ""},
            },
        )
        put.return_value = Mock(status_code=200, text="")
        with tempfile.NamedTemporaryFile(suffix=".mp4") as video:
            video.write(b"test-video-bytes")
            video.flush()
            result = autopilot.post_tiktok_inbox(video.name, {"title": "Test"})
        self.assertEqual(result, "test-publish-id")
        request = post.call_args
        self.assertIn("/video/init/", request.args[0])
        self.assertEqual(request.kwargs["json"]["source_info"]["source"], "FILE_UPLOAD")
        self.assertEqual(request.kwargs["json"]["source_info"]["chunk_size"], 16)
        self.assertEqual(request.kwargs["json"]["source_info"]["total_chunk_count"], 1)
        self.assertEqual(put.call_count, 1)
        self.assertEqual(put.call_args.kwargs["headers"]["Content-Range"],
                         "bytes 0-15/16")

    @patch.dict(os.environ, {}, clear=True)
    def test_missing_token_fails_closed(self):
        with tempfile.NamedTemporaryFile(suffix=".mp4") as video:
            video.write(b"x")
            video.flush()
            with self.assertRaisesRegex(RuntimeError, "TIKTOK_ACCESS_TOKEN"):
                autopilot.post_tiktok_inbox(video.name, {})


if __name__ == "__main__":
    unittest.main()
