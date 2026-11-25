import json
import unittest
from unittest.mock import Mock, patch

import autopilot


WATER_TOPIC = "Water scarcity and drying rivers"
INTERNET_TOPIC = "Internet infrastructure and global connectivity"
OCEAN_TOPIC = "Ocean warming, sea-level rise and glacier loss"


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

    def test_retries_scene_plan_once_with_exact_segment_guidance(self):
        narration = water_narration()
        bad = water_scenes()
        bad[0] = {"index": 1, "keywords": ["office workers meeting", "factory robot assembly"]}
        good = water_scenes()
        with patch.object(
            autopilot, "ask_ai",
            side_effect=[json.dumps({"scenes": bad}), json.dumps({"scenes": good})],
        ) as ask:
            plan = autopilot.make_visual_plan(narration, topic=WATER_TOPIC, fmt="short")
        self.assertEqual(len(plan), 6)
        self.assertEqual(ask.call_count, 2)
        self.assertIn("EXACT NARRATION SEGMENT: UN-Water documents river stress", ask.call_args_list[1].args[1])
        self.assertIn("Repair the searches only", ask.call_args_list[1].args[1])

    def test_visual_tokens_normalize_compound_documentary_terms(self):
        tokens = autopilot.visual_tokens(
            "dry riverbed human employee reviewing algorithmic software code "
            "high voltage electricity pylons hyperscale server racks"
        )
        self.assertTrue({"river", "employee", "algorithm", "software", "code", "voltage", "pylon", "server", "rack"} <= tokens)

    def test_stock_tags_accept_new_concrete_topic_anchors(self):
        self.assertTrue(autopilot.stock_tags_match(
            "human employee reviewing algorithmic software code",
            "human employee reviewing algorithmic software code",
            "AI and jobs",
        ))
        self.assertTrue(autopilot.stock_tags_match(
            "hyperscale server rack blue LED server room",
            "hyperscale server rack blue LED server room",
            "Global AI governance and concentration of power",
        ))
        self.assertTrue(autopilot.stock_tags_match(
            "high voltage electricity pylons sunset silhouette",
            "high voltage electricity pylons sunset silhouette",
            "Power-grid resilience and worldwide blackout scenarios",
        ))
        self.assertTrue(autopilot.stock_tags_match(
            "dry riverbed cracked earth ocean delta",
            "dry riverbed cracked earth ocean delta",
            WATER_TOPIC,
        ))

    def test_normalizes_out_of_order_scene_indexes(self):
        scenes = list(reversed(water_scenes()))
        with patch.object(autopilot, "ask_ai", return_value=json.dumps({"scenes": scenes})):
            plan = autopilot.make_visual_plan(water_narration(), topic=WATER_TOPIC, fmt="short")
        self.assertEqual(plan[0]["text"], "UN-Water documents river stress.")
        self.assertEqual(plan[0]["keywords"], water_scenes()[0]["keywords"])

    def test_normalizes_zero_based_scene_indexes(self):
        scenes = water_scenes()
        for scene in scenes:
            scene["index"] -= 1
        with patch.object(autopilot, "ask_ai", return_value=json.dumps({"scenes": scenes})):
            plan = autopilot.make_visual_plan(water_narration(), topic=WATER_TOPIC, fmt="short")
        self.assertEqual(len(plan), 6)
        self.assertEqual(plan[-1]["text"], "Better monitoring can help.")

    def test_accepts_numeric_string_scene_indexes(self):
        scenes = water_scenes()
        for scene in scenes:
            scene["index"] = str(scene["index"])
        with patch.object(autopilot, "ask_ai", return_value=json.dumps({"scenes": scenes})):
            plan = autopilot.make_visual_plan(water_narration(), topic=WATER_TOPIC, fmt="short")
        self.assertEqual(len(plan), 6)

    def test_accepts_omitted_indexes_when_array_order_matches_narration(self):
        scenes = water_scenes()
        for scene in scenes:
            scene.pop("index")
        with patch.object(autopilot, "ask_ai", return_value=json.dumps({"scenes": scenes})):
            plan = autopilot.make_visual_plan(water_narration(), topic=WATER_TOPIC, fmt="short")
        self.assertEqual(plan[0]["text"], "UN-Water documents river stress.")
        self.assertEqual(len(plan), 6)

    def test_rejects_duplicate_scene_indexes(self):
        scenes = water_scenes()
        scenes[1]["index"] = 1
        with patch.object(autopilot, "ask_ai", return_value=json.dumps({"scenes": scenes})):
            with self.assertRaisesRegex(ValueError, "missing, duplicate, or inconsistent scene indexes"):
                autopilot.make_visual_plan(water_narration(), topic=WATER_TOPIC, fmt="short")

    def test_rejects_reordered_scenes_when_indexes_are_omitted(self):
        scenes = list(reversed(water_scenes()))
        for scene in scenes:
            scene.pop("index")
        with patch.object(autopilot, "ask_ai", return_value=json.dumps({"scenes": scenes})):
            with self.assertRaises(ValueError):
                autopilot.make_visual_plan(water_narration(), topic=WATER_TOPIC, fmt="short")

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

    def test_accepts_relevant_pedestrian_mask_smog_searches(self):
        narration = (
            "Air pollution affects people in busy streets. "
            "Fine particles can enter the lungs. "
            "Traffic and industry contribute to polluted air. "
            "Air monitors measure local conditions. "
            "Health guidance can reduce exposure. "
            "Cleaner transport can improve city air."
        )
        scenes = [
            {"index": 1, "keywords": [
                "pedestrian wearing face mask walking through heavy city smog",
                "commuter wearing mask beside traffic in urban air pollution",
            ]},
            {"index": 2, "keywords": [
                "particulate matter entering lungs medical illustration",
                "air pollution health research laboratory",
            ]},
            {"index": 3, "keywords": [
                "vehicle exhaust on busy city street",
                "industrial factory emissions air pollution",
            ]},
            {"index": 4, "keywords": [
                "air quality monitor measuring particulate pollution",
                "scientist checking urban air monitoring station",
            ]},
            {"index": 5, "keywords": [
                "people wearing protective masks near traffic",
                "air pollution health advice public information",
            ]},
            {"index": 6, "keywords": [
                "electric buses replacing diesel city traffic",
                "urban clean public transport street",
            ]},
        ]
        with patch.object(autopilot, "ask_ai", return_value=json.dumps({"scenes": scenes})):
            plan = autopilot.make_visual_plan(
                narration, topic="Air pollution and health", fmt="short"
            )
        self.assertEqual(len(plan), 6)
        self.assertIn("pedestrian wearing face mask", plan[0]["keywords"][0])


    def test_red_river_blood_metaphor_is_normalized_to_neutral_scientific_search(self):
        narration = (
            "NOAA explains harmful algal blooms can discolor river water. "
            "Cyanobacteria blooms can produce toxins in lakes. "
            "Nutrient runoff can trigger rapid algae growth. "
            "Scientists collect water samples and examine them under microscopes. "
            "Wildlife can be harmed when oxygen levels fall. "
            "Monitoring and reducing nutrient pollution can protect river ecosystems."
        )
        scenes = [
            {"index": 1, "keywords": ["blood red river water aerial", "river water sampling scientist"]},
            {"index": 2, "keywords": ["cyanobacteria bloom lake water testing", "algal bloom lake water sample"]},
            {"index": 3, "keywords": ["nutrient runoff river algae bloom", "algal bloom water nutrient testing"]},
            {"index": 4, "keywords": ["scientist water sampling microscope", "river water testing scientist"]},
            {"index": 5, "keywords": ["fish wildlife water sampling algal bloom", "lake water cyanobacteria testing"]},
            {"index": 6, "keywords": ["river water quality monitoring nutrient runoff", "algal bloom prevention river water testing"]},
        ]
        with patch.object(autopilot, "ask_ai", return_value=json.dumps({"scenes": scenes})):
            plan = autopilot.make_visual_plan(
                narration, topic="Red or discolored rivers and harmful algal blooms", fmt="short"
            )
        self.assertEqual(len(plan), 6)
        self.assertEqual(plan[0]["keywords"][0], "red-discolored river water aerial")

    def test_blood_word_remains_rejected_for_unrelated_topics(self):
        scenes = water_scenes()
        scenes[0] = {"index": 1, "keywords": ["blood red river water aerial", "drought affected river basin"]}
        with patch.object(autopilot, "ask_ai", return_value=json.dumps({"scenes": scenes})):
            with self.assertRaisesRegex(ValueError, "fictional or horror footage"):
                autopilot.make_visual_plan(water_narration(), topic=WATER_TOPIC, fmt="short")

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


    def test_pixabay_candidates_require_the_narrated_concrete_subject(self):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "hits": [
                {
                    "id": 1,
                    "tags": "coastal coral reef ocean",
                    "duration": 8,
                    "videos": {"large": {"url": "https://cdn.example/coral-reef.mp4"}},
                },
                {
                    "id": 2,
                    "tags": "coastal seawall infrastructure ocean",
                    "duration": 7,
                    "videos": {"large": {"url": "https://cdn.example/seawall.mp4"}},
                },
            ]
        }
        with patch.dict("os.environ", {"PIXABAY_API_KEY": "test-key", "PEXELS_API_KEY": ""}, clear=True):
            with patch("autopilot.requests.get", return_value=response):
                candidates = autopilot.find_candidates(
                    [
                        "coastal resilience infrastructure seawall ocean",
                        "marine ecosystem underwater coral reef",
                    ],
                    "short",
                    720,
                    topic=OCEAN_TOPIC,
                    scene_text="We must invest in coastal infrastructure and seawall protection.",
                )
        self.assertEqual(
            candidates,
            [("px2", "https://cdn.example/seawall.mp4", 7.0)],
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
