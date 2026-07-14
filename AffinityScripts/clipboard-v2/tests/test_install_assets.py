#!/usr/bin/env python3
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGING = ROOT / "packaging"


class InstallAssetTests(unittest.TestCase):
    def test_service_is_separate_and_conflicts_with_v1(self):
        text = (PACKAGING / "affinity-clipboard-v2.service").read_text()
        self.assertIn("ExecStart=/usr/bin/python3 %h/.local/bin/affinity-clipboard-v2.py", text)
        self.assertIn("--owner %h/.local/bin/affinity-clipboard-owner", text)
        self.assertIn("Conflicts=affinity-png-file-clipboard.service", text)
        self.assertIn("KillMode=control-group", text)

    def test_tray_autostart_is_visible_to_plasma_settings(self):
        text = (PACKAGING / "affinity-clipboard-tray.desktop").read_text()
        self.assertIn("Exec=affinity-clipboard-tray", text)
        self.assertIn("OnlyShowIn=KDE;", text)
        self.assertIn("X-KDE-autostart-phase=2", text)


if __name__ == "__main__":
    unittest.main()
