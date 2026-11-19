"""Regression tests for the production GitHub Actions runner setup."""
import unittest
from pathlib import Path


WORKFLOW = (
    Path(__file__).resolve().parents[1]
    / ".github"
    / "workflows"
    / "autopilot.yml"
)


class WorkflowRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = WORKFLOW.read_text(encoding="utf-8")

    def test_production_runner_is_pinned_to_ubuntu_24_04(self):
        self.assertIn("runs-on: ubuntu-24.04", self.content)
        self.assertNotIn("runs-on: ubuntu-latest", self.content)

    def test_media_installation_has_a_longer_retry_budget(self):
        self.assertGreaterEqual(self.content.count("timeout 600s sudo apt-get"), 2)
        self.assertIn("Acquire::Retries=3", self.content)
        self.assertIn("Acquire::http::Timeout=30", self.content)
        self.assertIn("Acquire::https::Timeout=30", self.content)

    def test_workflow_exports_each_stage_outcome_for_history(self):
        for step in (
            "steps.media_tools.outcome",
            "steps.python_packages.outcome",
            "steps.python_syntax.outcome",
            "steps.unit_tests.outcome",
            "steps.platform_preflight.outcome",
            "steps.autopilot.outcome",
        ):
            self.assertIn(step, self.content)


if __name__ == "__main__":
    unittest.main()
