#!/usr/bin/env python3
import json
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
BINARY = ROOT / "build" / "affinity-clipboard-owner"


class OwnerCliTests(unittest.TestCase):
    def test_describe_reports_png_and_filename_formats(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "original name.png"
            image.write_bytes(b"\x89PNG\r\n\x1a\nowner-cli-test")
            result = subprocess.run(
                [str(BINARY), "--describe", str(image)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            description = json.loads(result.stdout)
            self.assertEqual(description["file"], str(image))
            self.assertIn("image/png", description["formats"])
            self.assertIn("text/uri-list", description["formats"])
            self.assertIn("application/x-kde4-urilist", description["formats"])


if __name__ == "__main__":
    unittest.main()
