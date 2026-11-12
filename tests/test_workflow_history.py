"""Tests for scheduled-run history recovery."""
import json
import tempfile
import unittest
from pathlib import Path

from record_workflow import record_workflow_outcome


class WorkflowHistoryTests(unittest.TestCase):
    def test_cancelled_schedule_before_autopilot_is_recorded(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "history.json"
            path.write_text(json.dumps({"posts": [], "patterns": {}, "runs": []}), encoding="utf-8")
            env = {
                "GITHUB_EVENT_NAME": "schedule",
                "GITHUB_RUN_ID": "12345",
                "GITHUB_RUN_NUMBER": "28",
                "GITHUB_RUN_ATTEMPT": "1",
                "JOB_STATUS": "cancelled",
                "GEMINI_API_KEY": "must-not-be-recorded",
            }

            self.assertTrue(record_workflow_outcome(env, path))
            saved_text = path.read_text(encoding="utf-8")
            saved = json.loads(saved_text)
            self.assertEqual(len(saved["runs"]), 1)
            self.assertEqual(saved["runs"][0]["status"], "workflow_cancelled_before_generation")
            self.assertEqual(saved["runs"][0]["github_run_id"], "12345")
            self.assertFalse(saved["runs"][0]["generated"])
            self.assertNotIn("must-not-be-recorded", saved_text)

    def test_existing_preflight_record_is_not_duplicated(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "history.json"
            path.write_text(json.dumps({
                "runs": [{"run_id": "12345", "run_attempt": "1", "status": "preflight_failed"}]
            }), encoding="utf-8")
            env = {
                "GITHUB_EVENT_NAME": "schedule",
                "GITHUB_RUN_ID": "12345",
                "GITHUB_RUN_ATTEMPT": "1",
                "JOB_STATUS": "failure",
            }

            self.assertFalse(record_workflow_outcome(env, path))
            saved = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(len(saved["runs"]), 1)
            self.assertEqual(saved["runs"][0]["status"], "preflight_failed")

    def test_interrupted_started_record_is_marked_cancelled(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "history.json"
            path.write_text(json.dumps({
                "runs": [{
                    "github_run_id": "12345",
                    "github_run_attempt": "2",
                    "status": "started",
                    "generated": False,
                }]
            }), encoding="utf-8")
            env = {
                "GITHUB_EVENT_NAME": "schedule",
                "GITHUB_RUN_ID": "12345",
                "GITHUB_RUN_ATTEMPT": "2",
                "JOB_STATUS": "cancelled",
            }

            self.assertTrue(record_workflow_outcome(env, path))
            saved = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(saved["runs"][0]["status"], "workflow_cancelled_during_generation")
            self.assertFalse(saved["runs"][0]["generated"])

    def test_manual_dispatch_is_not_counted_as_a_scheduled_slot(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "history.json"
            env = {
                "GITHUB_EVENT_NAME": "workflow_dispatch",
                "GITHUB_RUN_ID": "12345",
                "JOB_STATUS": "failure",
            }
            self.assertFalse(record_workflow_outcome(env, path))
            self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
