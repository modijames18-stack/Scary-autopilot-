import json
import unittest
from unittest.mock import patch

import autopilot


class VisualPlanTests(unittest.TestCase):
    def test_creates_ordered_scene_searches(self):
        narration = "AI is changing jobs. Workers use new tools. Offices are adapting. Factory employees need training."
        payload = {"scenes": [
            {"index": 1, "keywords": ["AI workers in office", "automation in workplace"]},
            {"index": 2, "keywords": ["factory workers training", "employment skills workshop"]},
        ]}
        with patch.object(autopilot, "ask_ai", return_value=json.dumps(payload)):
            plan = autopilot.make_visual_plan(narration, topic="AI and jobs")
        self.assertEqual(len(plan), 2)
        self.assertIn("AI is changing jobs.", plan[0]["text"])
        self.assertIn("Factory employees need training.", plan[1]["text"])
        self.assertEqual(plan[0]["keywords"][0], "AI workers in office")

    def test_rejects_missing_scene(self):
        narration = "First sentence. Second sentence. Third sentence. Fourth sentence."
        payload = {"scenes": [
            {"index": 1, "keywords": ["factory workers", "industrial robots"]}
        ]}
        with patch.object(autopilot, "ask_ai", return_value=json.dumps(payload)):
            with self.assertRaisesRegex(ValueError, "one scene for every narration segment"):
                autopilot.make_visual_plan(narration, topic="AI and jobs")

    def test_rejects_horror_footage_for_water_documentary(self):
        narration = "A river is drying. Farmers are losing crops. Water levels are falling."
        payload = {"scenes": [
            {"index": 1, "keywords": ["haunted hallway", "black forest"]}
        ]}
        with patch.object(autopilot, "ask_ai", return_value=json.dumps(payload)):
            with self.assertRaisesRegex(ValueError, "fictional or horror footage"):
                autopilot.make_visual_plan(narration, topic="Water scarcity and drying rivers")

    def test_rejects_unrelated_scene_keywords(self):
        narration = "A river is drying. Farmers are losing crops. Water levels are falling."
        payload = {"scenes": [
            {"index": 1, "keywords": ["office workers", "factory robots"]}
        ]}
        with patch.object(autopilot, "ask_ai", return_value=json.dumps(payload)):
            with self.assertRaisesRegex(ValueError, "does not match its narration or topic"):
                autopilot.make_visual_plan(narration, topic="Water scarcity and drying rivers")

    def test_rejects_generic_or_incomplete_keywords(self):
        narration = "A river is drying. Farmers are losing crops. Water levels are falling."
        payload = {"scenes": [
            {"index": 1, "keywords": ["drying river"]}
        ]}
        with patch.object(autopilot, "ask_ai", return_value=json.dumps(payload)):
            with self.assertRaisesRegex(ValueError, "too few specific footage searches"):
                autopilot.make_visual_plan(narration, topic="Water scarcity and drying rivers")


if __name__ == "__main__":
    unittest.main()
