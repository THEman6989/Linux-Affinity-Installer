#!/usr/bin/env python3
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGING = ROOT / "packaging"


def wanted_by_targets(text: str) -> set[str]:
    return {
        target
        for line in text.splitlines()
        if line.startswith("WantedBy=")
        for target in line.removeprefix("WantedBy=").split()
    }


class InstallAssetTests(unittest.TestCase):
    def test_service_is_separate_and_conflicts_with_v1(self):
        text = (PACKAGING / "affinity-clipboard-v2.service").read_text()
        self.assertIn("ExecStart=/usr/bin/python3 %h/.local/bin/affinity-clipboard-v2.py", text)
        self.assertIn("--owner %h/.local/bin/affinity-clipboard-owner", text)
        self.assertIn("Conflicts=affinity-png-file-clipboard.service", text)
        self.assertIn("KillMode=control-group", text)
        self.assertIn("RestartPreventExitStatus=2", text)
        self.assertEqual(wanted_by_targets(text), {"graphical-session.target"})

    def test_tray_starts_with_the_graphical_session(self):
        text = (PACKAGING / "affinity-clipboard-tray.service").read_text()
        self.assertIn("After=graphical-session.target", text)
        self.assertIn("PartOf=graphical-session.target", text)
        self.assertIn("ExecStart=%h/.local/bin/affinity-clipboard-tray", text)
        self.assertEqual(wanted_by_targets(text), {"graphical-session.target"})

    def test_desktop_autostart_is_not_shipped_in_parallel(self):
        for desktop in PACKAGING.glob("*.desktop"):
            text = desktop.read_text(encoding="utf-8")
            self.assertNotIn("affinity-clipboard-tray", text)

if __name__ == "__main__":
    unittest.main()
