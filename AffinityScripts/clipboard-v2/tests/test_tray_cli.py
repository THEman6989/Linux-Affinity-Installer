#!/usr/bin/env python3
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
BINARY = ROOT / "build" / "affinity-clipboard-tray"


class TrayCliTests(unittest.TestCase):
    def test_status_reports_inactive_for_unknown_service(self):
        result = subprocess.run(
            [
                str(BINARY),
                "--status",
                "--service",
                "affinity-clipboard-v2-test-does-not-exist.service",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "inactive")


if __name__ == "__main__":
    unittest.main()
