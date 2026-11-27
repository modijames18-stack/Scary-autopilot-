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
            "candidates": [{"content": {"parts": [{"text": "{\"validated\": true}"}]}}]
        }
        post.side_effect = [requests.Timeout("primary timed out"), success]

        result = autopilot.ask_ai("system", "prompt", max_tokens=300, json_mode=True)

        self.assertEqual(result, "{\"validated\": true}")
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
        "GEMINI_ATTEMPTS_PER_MODEL": "1",
    }, clear=True)
    @patch("autopilot.requests.post")
    def test_json_response_schema_is_sent_when_requested(self, post):
        success = Mock(ok=True, status_code=200)
        success.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": '{"topic":"Water"}'}]}}]
        }
        post.return_value = success
        schema = {
            "type": "OBJECT",
            "properties": {"topic": {"type": "STRING"}},
            "required": ["topic"],
        }

        result = autopilot.ask_ai(
            "system", "prompt", json_mode=True, response_schema=schema
        )

        self.assertEqual(result, '{"topic":"Water"}')
        generation = post.call_args.kwargs["json"]["generationConfig"]
        self.assertEqual(generation["responseMimeType"], "application/json")
        self.assertEqual(generation["responseSchema"], schema)

    @patch.dict("os.environ", {
        "AI_PROVIDER": "gemini",
        "GEMINI_API_KEY": "test-key",
        "GEMINI_MODEL": "gemini-primary",
        "GEMINI_FALLBACK_MODELS": "gemini-fallback",
        "GEMINI_ATTEMPTS_PER_MODEL": "1",
    }, clear=True)
    @patch("autopilot.requests.post")
    def test_unsupported_response_schema_retries_without_schema(self, post):
        rejected = Mock(ok=False, status_code=400, text="responseSchema is not supported")
        success = Mock(ok=True, status_code=200)
        success.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": '{"topic":"Water"}'}]}}]
        }
        post.side_effect = [rejected, success]
        schema = {
            "type": "OBJECT",
            "properties": {"topic": {"type": "STRING"}},
            "required": ["topic"],
        }

        result = autopilot.ask_ai(
            "system", "prompt", json_mode=True, response_schema=schema
        )

        self.assertEqual(result, '{"topic":"Water"}')
        self.assertEqual(post.call_count, 2)
        second_config = post.call_args_list[1].kwargs["json"]["generationConfig"]
        self.assertNotIn("responseSchema", second_config)
        self.assertEqual(second_config["responseMimeType"], "application/json")

    @patch.dict("os.environ", {
        "AI_PROVIDER": "gemini",
        "GEMINI_API_KEY": "test-key",
        "GEMINI_MODEL": "gemini-primary",
        "GEMINI_FALLBACK_MODELS": "gemini-fallback",
        "GEMINI_ATTEMPTS_PER_MODEL": "1",
    }, clear=True)
    @patch("autopilot.requests.post")
    def test_non_json_primary_response_uses_configured_fallback(self, post):
        malformed = Mock(ok=True, status_code=200)
        malformed.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": "Here is a summary, not JSON."}]}}]
        }
        valid = Mock(ok=True, status_code=200)
        valid.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": '{"topic": "Water"}'}]}}]
        }
        post.side_effect = [malformed, valid]

        result = autopilot.ask_ai("system", "prompt", json_mode=True)

        self.assertEqual(result, '{"topic": "Water"}')
        self.assertEqual(post.call_count, 2)
        self.assertIn("gemini-primary:generateContent", post.call_args_list[0].args[0])
        self.assertIn("gemini-fallback:generateContent", post.call_args_list[1].args[0])

    @patch.dict("os.environ", {
        "AI_PROVIDER": "gemini",
        "GEMINI_API_KEY": "test-key",
        "GEMINI_MODEL": "gemini-primary",
        "GEMINI_FALLBACK_MODELS": "gemini-fallback",
        "GEMINI_ATTEMPTS_PER_MODEL": "1",
    }, clear=True)
    @patch("autopilot.requests.post")
    def test_all_non_json_models_fail_closed(self, post):
        malformed = Mock(ok=True, status_code=200)
        malformed.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": "No structured response."}]}}]
        }
        post.side_effect = [malformed, malformed]

        with self.assertRaisesRegex(RuntimeError, "non-JSON response"):
            autopilot.ask_ai("system", "prompt", json_mode=True)

        self.assertEqual(post.call_count, 2)

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

    @patch.dict("os.environ", {
        "AI_PROVIDER": "gemini",
        "GEMINI_API_KEY": "test-key",
    }, clear=True)
    @patch("autopilot.requests.post")
    def test_default_attempts_per_model_is_one(self, post):
        unavailable = Mock(ok=False, status_code=503, text="temporary server error")
        post.return_value = unavailable

        with self.assertRaisesRegex(RuntimeError, "unavailable"):
            autopilot.ask_ai("system", "prompt")

        # The primary and both configured fallbacks are each tried once.
        self.assertEqual(post.call_count, 3)

    @patch.dict("os.environ", {}, clear=True)
    def test_default_model_sequence_includes_low_cost_tertiary_fallback(self):
        self.assertEqual(
            autopilot.gemini_model_sequence(),
            ["gemini-3.8-flash", "gemini-3.6-flash", "gemini-3.5-flash-lite"],
        )


if __name__ == "__main__":
    unittest.main()
