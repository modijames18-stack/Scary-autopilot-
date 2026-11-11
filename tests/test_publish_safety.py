import os
import unittest
from unittest.mock import patch

import autopilot


class PublishingSafetyTests(unittest.TestCase):
    def test_missing_switch_disables_publishing(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(autopilot.publishing_enabled("ENABLE_YOUTUBE_UPLOAD"))
            self.assertFalse(autopilot.publishing_enabled("ENABLE_FACEBOOK_PUBLISH"))

    def test_only_explicit_true_enables_publishing(self):
        with patch.dict(os.environ, {
            "ENABLE_YOUTUBE_UPLOAD": "true",
            "ENABLE_FACEBOOK_PUBLISH": "TRUE",
        }, clear=True):
            self.assertTrue(autopilot.publishing_enabled("ENABLE_YOUTUBE_UPLOAD"))
            self.assertTrue(autopilot.publishing_enabled("ENABLE_FACEBOOK_PUBLISH"))

    def test_other_values_do_not_enable_publishing(self):
        for value in ("", "false", "yes", "1", " public "):
            with self.subTest(value=value), patch.dict(
                os.environ, {"ENABLE_YOUTUBE_UPLOAD": value}, clear=True
            ):
                self.assertFalse(autopilot.publishing_enabled("ENABLE_YOUTUBE_UPLOAD"))


if __name__ == "__main__":
    unittest.main()
