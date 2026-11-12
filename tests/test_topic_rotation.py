"""Topic rotation must advance after failed generation attempts."""
import unittest

import autopilot


class TopicRotationTests(unittest.TestCase):
    def test_failed_attempt_advances_rotation_without_a_published_post(self):
        history = {
            "posts": [],
            "runs": [{
                "topic": "Water scarcity and drying rivers",
                "status": "generation_failed",
            }],
        }
        self.assertEqual(autopilot.choose_topic(history), "AI and jobs")

    def test_latest_attempt_topic_takes_precedence_over_older_successful_post(self):
        history = {
            "posts": [{"topic": "Water scarcity and drying rivers"}],
            "runs": [{"topic": "AI and jobs", "status": "generation_failed"}],
        }
        self.assertEqual(
            autopilot.choose_topic(history),
            "Climate change, extreme weather and food security",
        )

    def test_legacy_history_without_run_topics_still_uses_last_post(self):
        history = {
            "posts": [{"topic": "Water scarcity and drying rivers"}],
            "runs": [{"status": "generation_failed"}],
        }
        self.assertEqual(autopilot.choose_topic(history), "AI and jobs")


if __name__ == "__main__":
    unittest.main()
