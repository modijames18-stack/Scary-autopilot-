import json
import unittest
from unittest.mock import patch

import autopilot


class VisualPlanTests(unittest.TestCase):
    def test_creates_ordered_scene_searches(self):
        narration = "First sentence. Second sentence. Third sentence. Fourth sentence."
        payload = {"scenes": [
            {"index": 1, "keywords": ["factory workers", "industrial robots"]},
            {"index": 2, "keywords": ["office employees", "workplace computers"]},
        ]}
        with patch.object(autopilot, "ask_ai", return_value=json.dumps(payload)):
            plan = autopilot.make_visual_plan(narration)
        self.assertEqual(len(plan), 2)
        self.assertIn("First sentence.", plan[0]["text"])
        self.assertIn("Fourth sentence.", plan[1]["text"])
        self.assertEqual(plan[0]["keywords"][0], "factory workers")

    def test_rejects_missing_scene(self):
        narration = "First sentence. Second sentence. Third sentence. Fourth sentence."
        payload = {"scenes": [
            {"index": 1, "keywords": ["factory workers", "industrial robots"]}
        ]}
        with patch.object(autopilot, "ask_ai", return_value=json.dumps(payload)):
            with self.assertRaisesRegex(ValueError, "one scene for every narration segment"):
                autopilot.make_visual_plan(narration)

    def test_rejects_generic_or_incomplete_keywords(self):
        narration = "A river is drying. Farmers are losing crops. Water levels are falling."
        payload = {"scenes": [
            {"index": 1, "keywords": ["drying river"]}
        ]}
        with patch.object(autopilot, "ask_ai", return_value=json.dumps(payload)):
            with self.assertRaisesRegex(ValueError, "too few specific footage searches"):
                autopilot.make_visual_plan(narration)


if __name__ == "__main__":
    unittest.main()
