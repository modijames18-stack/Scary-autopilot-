import json
import unittest
from unittest.mock import Mock, patch

import autopilot


WATER_TOPIC = "Water scarcity and drying rivers"
INTERNET_TOPIC = "Internet infrastructure and global connectivity"


def water_narration():
    return (
        "UN-Water documents river stress. "
        "Reservoirs are falling. "
        "Farmers need irrigation. "
        "Groundwater levels matter. "
        "Wetlands protect communities. "
        "Better monitoring can help."
    )


def water_scenes():
    return [
        {"index": 1, "keywords": ["UN-Water river monitoring", "drought affected river basin"]},
        {"index": 2, "keywords": ["low reservoir water levels", "drought reservoir monitoring"]},
        {"index": 3, "keywords": ["farmers using irrigation canals", "crop irrigation water use"]},
        {"index": 4, "keywords": ["groundwater aquifer monitoring", "well water groundwater levels"]},
        {"index": 5, "keywords": ["wetland restoration river delta", "wetland flood protection"]},
        {"index": 6, "keywords": ["river water monitoring instruments", "aquifer monitoring equipment"]},
    ]


class VisualPlanTests(unittest.TestCase):
    def test_creates_one_ordered_scene_per_short_narration_sentence(self):
        narration = (
            "AI is changing jobs. "
            "Workers use new tools. "
            "Offices are adapting. "
            "Factory employees need training. "
            "Automation affects warehouse tasks. "
            "New skills can protect livelihoods."
        )
        payload = {"scenes": [
            {"index": 1, "keywords": ["AI factory workers", "automation in workplace"]},
            {"index": 2, "keywords": ["workers using AI tools", "robot workers workplace"]},
            {"index": 3, "keywords": ["office employees using AI", "workplace automation teams"]},
            {"index": 4, "keywords": ["factory employee training", "industrial robotics skills"]},
            {"index": 5, "keywords": ["warehouse automation workers", "factory robots assembly line"]},
            {"index": 6, "keywords": ["worker reskilling training", "computer skills classroom"]},
        ]}
        with patch.object(autopilot, "ask_ai", return_value=json.dumps(payload)):
            plan = autopilot.make_visual_plan(narration, topic="AI and jobs", fmt="short")
        self.assertEqual(len(plan), 6)
        self.assertEqual(plan[0]["text"], "AI is changing jobs.")
        self.assertEqual(plan[1]["text"], "Workers use new tools.")
        self.assertEqual(plan[5]["text"], "New skills can protect livelihoods.")

    def test_rejects_missing_scene(self):
        payload = {"scenes": [water_scenes()[0]]}
        with patch.object(autopilot, "ask_ai", return_value=json.dumps(payload)):
            with self.assertRaisesRegex(ValueError, "one scene for every narration segment"):
                autopilot.make_visual_plan(water_narration(), topic=WATER_TOPIC, fmt="short")

    def test_rejects_horror_footage_for_water_documentary(self):
        scenes = water_scenes()
        scenes[0] = {"index": 1, "keywords": ["haunted hallway", "black forest"]}
        with patch.object(autopilot, "ask_ai", return_value=json.dumps({"scenes": scenes})):
            with self.assertRaisesRegex(ValueError, "fictional or horror footage"):
                autopilot.make_visual_plan(water_narration(), topic=WATER_TOPIC, fmt="short")

    def test_rejects_unrelated_scene_keywords(self):
        scenes = water_scenes()
        scenes[0] = {"index": 1, "keywords": ["office workers", "factory robots"]}
        with patch.object(autopilot, "ask_ai", return_value=json.dumps({"scenes": scenes})):
            with self.assertRaisesRegex(ValueError, "does not match its narration or topic"):
                autopilot.make_visual_plan(water_narration(), topic=WATER_TOPIC, fmt="short")

    def test_rejects_generic_or_incomplete_keywords(self):
        scenes = water_scenes()
        scenes[0] = {"index": 1, "keywords": ["drying river"]}
        with patch.object(autopilot, "ask_ai", return_value=json.dumps({"scenes": scenes})):
            with self.assertRaisesRegex(ValueError, "too few specific footage searches"):
                autopilot.make_visual_plan(water_narration(), topic=WATER_TOPIC, fmt="short")

    def test_rejects_ambiguous_cable_car_search_for_internet_documentary(self):
        narration = (
            "Global internet traffic crosses oceans. "
            "Submarine cables carry international data. "
            "Repair ships restore damaged links. "
            "Landing stations connect networks on shore. "
            "Satellite routes can provide limited backup."
        )
        scenes = [
            {"index": 1, "keywords": ["global economy cable car", "mountain cable car network"]},
            {"index": 2, "keywords": ["submarine cable ship", "undersea cable landing station"]},
            {"index": 3, "keywords": ["submarine cable repair ship", "underwater fiber optic cable"]},
            {"index": 4, "keywords": ["internet cable landing station", "telecom network exchange"]},
            {"index": 5, "keywords": ["satellite internet ground station", "satellite internet communications dish"]},
        ]
        with patch.object(autopilot, "ask_ai", return_value=json.dumps({"scenes": scenes})):
            with self.assertRaisesRegex(ValueError, "at least two concrete topic-specific anchors"):
                autopilot.make_visual_plan(narration, topic=INTERNET_TOPIC, fmt="short")

    def test_pixabay_tags_reject_cable_car_and_accept_undersea_cable(self):
        self.assertFalse(
            autopilot.stock_tags_match(
                "cable car, mountains",
                "global economy cable car",
                INTERNET_TOPIC,
            )
        )
        self.assertTrue(
            autopilot.stock_tags_match(
                "underwater, submarine cable, ocean",
                "undersea cable repair ship",
                INTERNET_TOPIC,
            )
        )

    def test_pixabay_candidates_are_filtered_by_their_own_tags(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "hits": [
                {
                    "id": 1,
                    "tags": "cable car, mountains",
                    "duration": 8,
                    "videos": {"large": {"url": "https://cdn.example/cable-car.mp4"}},
                },
                {
                    "id": 2,
                    "tags": "underwater, submarine cable, ocean",
                    "duration": 7,
                    "videos": {"large": {"url": "https://cdn.example/submarine-cable.mp4"}},
                },
            ]
        }
        with patch.dict("os.environ", {"PIXABAY_API_KEY": "test-key", "PEXELS_API_KEY": ""}, clear=True):
            with patch("autopilot.requests.get", return_value=response):
                candidates = autopilot.find_candidates(
                    ["undersea cable repair ship"], "short", 720, topic=INTERNET_TOPIC
                )
        self.assertEqual(
            candidates,
            [("px2", "https://cdn.example/submarine-cable.mp4", 7.0)],
        )

    def test_pexels_fallback_requires_and_reads_page_subject_metadata(self):
        api_response = Mock()
        api_response.raise_for_status.return_value = None
        api_response.json.return_value = {
            "videos": [{
                "id": 9,
                "url": "https://www.pexels.com/video/submarine-cable-repair-123/",
                "duration": 8,
                "video_files": [{
                    "file_type": "video/mp4",
                    "width": 1280,
                    "link": "https://videos.pexels.com/submarine-cable.mp4",
                }],
            }]
        }
        page_response = Mock(ok=True)
        page_response.text = (
            '<meta property="og:title" content="Underwater submarine cable repair ship ocean">'
        )
        with patch.dict("os.environ", {"PIXABAY_API_KEY": "", "PEXELS_API_KEY": "test-key"}, clear=True):
            with patch("autopilot.requests.get", side_effect=[api_response, page_response]):
                candidates = autopilot.find_candidates(
                    ["undersea cable repair ship"], "short", 720, topic=INTERNET_TOPIC
                )
        self.assertEqual(
            candidates,
            [("pe9", "https://videos.pexels.com/submarine-cable.mp4", 8.0)],
        )

    def test_parse_meta_reports_invalid_json_without_raw_response(self):
        with self.assertRaisesRegex(ValueError, "did not contain a JSON object"):
            autopilot.parse_meta("The provider returned no structured script.")


if __name__ == "__main__":
    unittest.main()
