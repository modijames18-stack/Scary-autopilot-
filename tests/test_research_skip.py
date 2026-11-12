"""Optional audience-interest research must not block scheduled generation."""
import os
import unittest
from unittest.mock import patch

import autopilot


class ResearchSkipTests(unittest.TestCase):
    @patch.dict(os.environ, {"YT_REFRESH_TOKEN": "configured"}, clear=True)
    @patch("googleapiclient.discovery.build")
    def test_youtube_research_is_skipped_when_publishing_is_disabled(self, build):
        result = autopilot.research("short", {"patterns": {}})
        self.assertIn("publishing is disabled", result)
        build.assert_not_called()


if __name__ == "__main__":
    unittest.main()
