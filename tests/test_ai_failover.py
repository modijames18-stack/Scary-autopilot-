"""Tests for bounded Gemini retries, model failover, and output limits."""
import unittest
from unittest.mock import Mock, patch

import requests

import autopilot


class GeminiFailoverTests(unittest.TestCase):
    @patch.dict("os.environ", {
        "AI_PROVIDER": "gemini",
        "GEMINI_API_KEY": "test-key",
        "GEMINI_MODEL": "gemini-primary",
        "GEMINI_FALLBACK_MODELS": "gemini-fallback",
        "GEMINI_ATTEMPTS_PER_MODEL": "1",
        "GEMINI_TIMEOUT_SECONDS": "30",
    }, clear=True)
    @patch("autopilot.time.sleep")
    @patch("autopilot.requests.post")
    def test_primary_timeout_falls_back_to_secondary_model(self, post, _sleep):
        success = Mock(ok=True, status_code=200)
        success.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": "validated candidate"}]}}]
        }
        post.side_effect = [requests.Timeout("primary timed out"), success]

        result = autopilot.ask_ai("system", "prompt", max_tokens=300, json_mode=True)

        self.assertEqual(result, "validated candidate")
        self.assertEqual(post.call_count, 2)
        self.assertIn("gemini-primary:generateContent", post.call_args_list[0].args[0])
        self.assertIn("gemini-fallback:generateContent", post.call_args_list[1].args[0])
        self.assertEqual(post.call_args_list[0].kwargs["timeout"], 30)
        generation = post.call_args_list[0].kwargs["json"]["generationConfig"]
        self.assertEqual(generation["maxOutputTokens"], 512)
        self.assertEqual(generation["responseMimeType"], "application/json")

    @patch.dict("os.environ", {
        "AI_PROVIDER": "gemini",
        "GEMINI_API_KEY": "test-key",
        "GEMINI_MODEL": "gemini-primary",
        "GEMINI_FALLBACK_MODELS": "gemini-fallback",
        "GEMINI_ATTEMPTS_PER_MODEL": "3",
    }, clear=True)
    @patch("autopilot.time.sleep")
    @patch("autopilot.requests.post")
    def test_hard_quota_skips_retries_and_tries_next_model(self, post, sleep):
        quota = Mock(
            ok=False,
            status_code=429,
            text='{"error":{"message":"You exceeded your current quota"}}',
        )
        success = Mock(ok=True, status_code=200)
        success.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": "fallback succeeded"}]}}]
        }
        post.side_effect = [quota, success]

        result = autopilot.ask_ai("system", "prompt")

        self.assertEqual(result, "fallback succeeded")
        self.assertEqual(post.call_count, 2)
        self.assertIn("gemini-primary:generateContent", post.call_args_list[0].args[0])
        self.assertIn("gemini-fallback:generateContent", post.call_args_list[1].args[0])
        sleep.assert_not_called()

    @patch.dict("os.environ", {"AI_PROVIDER": "gemini"}, clear=True)
    def test_quota_diagnostic_is_actionable_and_does_not_echo_raw_error(self):
        detail = autopilot.safe_ai_error_summary(
            RuntimeError("HTTP 429: quota exceeded; sensitive-token-placeholder")
        )
        self.assertIn("quota", detail.lower())
        self.assertIn("ANTHROPIC_API_KEY", detail)
        self.assertNotIn("sensitive-token-placeholder", detail)

    @patch.dict("os.environ", {
        "AI_PROVIDER": "gemini",
        "GEMINI_API_KEY": "test-key",
        "GEMINI_MODEL": "gemini-primary",
        "GEMINI_FALLBACK_MODELS": "gemini-fallback",
        "GEMINI_ATTEMPTS_PER_MODEL": "1",
    }, clear=True)
    @patch("autopilot.requests.post")
    def test_non_retryable_auth_error_stops_without_model_fallback(self, post):
        denied = Mock(ok=False, status_code=403, text="permission denied")
        post.return_value = denied

        with self.assertRaisesRegex(RuntimeError, "Gemini error 403"):
            autopilot.ask_ai("system", "prompt")

        post.assert_called_once()


if __name__ == "__main__":
    unittest.main()
