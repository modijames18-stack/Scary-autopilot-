"""Tests that stock clips remain unique and scene files cannot overwrite each other."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import autopilot


class FakeStreamResponse:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size):
        yield b"fake-video-bytes"


class FootageDiversityTests(unittest.TestCase):
    def test_fetch_clips_uses_scene_specific_files_and_excludes_prior_sources(self):
        candidates = [
            [
                ("px1", "https://cdn.example/1.mp4", 7.0),
                ("px2", "https://cdn.example/2.mp4", 7.0),
            ],
            [
                ("px1", "https://cdn.example/1.mp4", 7.0),
                ("px2", "https://cdn.example/2.mp4", 7.0),
                ("px3", "https://cdn.example/3.mp4", 7.0),
                ("px4", "https://cdn.example/4.mp4", 7.0),
            ],
        ]
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(autopilot, "WORK", Path(folder)):
                with patch.object(autopilot, "find_candidates", side_effect=candidates):
                    with patch("autopilot.requests.get", return_value=FakeStreamResponse()):
                        with patch.object(autopilot, "run", return_value=""):
                            used_ids = set()
                            first = autopilot.fetch_clips(
                                ["farm drought crop"], "short", 10, 720, 1280,
                                topic="Climate change, extreme weather and food security",
                                used_ids=used_ids, segment_prefix="scene_01_clip",
                            )
                            second = autopilot.fetch_clips(
                                ["farm drought crop"], "short", 10, 720, 1280,
                                topic="Climate change, extreme weather and food security",
                                used_ids=used_ids, segment_prefix="scene_02_clip",
                            )

        self.assertEqual(
            [name for name, _ in first],
            ["scene_01_clip_00.mp4", "scene_01_clip_01.mp4"],
        )
        self.assertEqual(
            [name for name, _ in second],
            ["scene_02_clip_00.mp4", "scene_02_clip_01.mp4"],
        )
        self.assertEqual(used_ids, {"px1", "px2", "px3", "px4"})

    def test_build_video_passes_one_shared_exclusion_set_and_audits_sources(self):
        calls = []

        def fake_fetch(keywords, fmt, need, width, height, topic=None,
                       used_ids=None, segment_prefix="seg"):
            calls.append((segment_prefix, used_ids))
            source_id = "px1" if len(calls) == 1 else "px2"
            if len(calls) > 1:
                self.assertIn("px1", used_ids)
            used_ids.add(source_id)
            return [(f"{segment_prefix}_00.mp4", 7.0)]

        meta = {
            "topic": "Climate change, extreme weather and food security",
            "visual_scenes": [
                {"text": "First narration sentence.", "keywords": ["farm drought crop"]},
                {"text": "Second narration sentence.", "keywords": ["storm crop field"]},
            ],
        }
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(autopilot, "WORK", Path(folder)):
                with patch.object(autopilot, "fetch_clips", side_effect=fake_fetch):
                    with patch.object(autopilot, "run", return_value=""):
                        autopilot.build_video("short", meta, 10.0)
            scene_one = (Path(folder) / "scene_01.txt").read_text(encoding="utf-8")
            scene_two = (Path(folder) / "scene_02.txt").read_text(encoding="utf-8")

        self.assertEqual(calls[0][0], "scene_01_clip")
        self.assertEqual(calls[1][0], "scene_02_clip")
        self.assertIs(calls[0][1], calls[1][1])
        self.assertIn("scene_01_clip_00.mp4", scene_one)
        self.assertIn("scene_02_clip_00.mp4", scene_two)
        self.assertEqual(meta["visual_clip_audit"][0]["source_ids"], ["px1"])
        self.assertEqual(meta["visual_clip_audit"][1]["source_ids"], ["px2"])


if __name__ == "__main__":
    unittest.main()
