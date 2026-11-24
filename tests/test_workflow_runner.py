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

    def test_schedule_runs_every_three_hours_away_from_hour_boundary(self):
        self.assertIn('cron: "17 */3 * * *"', self.content)

    def test_media_installation_caches_packages_and_has_a_longer_retry_budget(self):
        self.assertIn("uses: actions/cache@v4", self.content)
        self.assertIn("path: ~/.cache/apt/archives", self.content)
        self.assertIn("key: ubuntu-24.04-ffmpeg-${{ github.run_id }}", self.content)
        self.assertIn("restore-keys: |", self.content)
        self.assertIn("Dir::Cache::archives=", self.content)
        self.assertIn("timeout 300s sudo apt-get", self.content)
        self.assertIn("timeout 1800s sudo apt-get", self.content)
        self.assertIn("Acquire::Retries=5", self.content)
        self.assertIn("Acquire::http::Timeout=60", self.content)
        self.assertIn("Acquire::https::Timeout=60", self.content)

    def test_media_installation_checks_ffprobe_and_subtitle_support(self):
        self.assertIn("command -v ffprobe", self.content)
        self.assertIn("ffprobe -version | head -n 1", self.content)
        self.assertIn("ffmpeg -hide_banner -filters | grep -q subtitles", self.content)

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
