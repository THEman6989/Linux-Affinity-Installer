#!/usr/bin/env python3
import importlib.util
import os
from pathlib import Path
import signal
import stat
import sys
import tempfile
import unittest
from unittest import mock
import warnings


MODULE_PATH = Path(__file__).resolve().parents[1] / "src" / "watcher_v2.py"
spec = importlib.util.spec_from_file_location("watcher_v2", MODULE_PATH)
watcher = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(watcher)


class WatcherV2Tests(unittest.TestCase):
    def test_stop_owner_fails_closed_without_pidfd(self):
        with tempfile.TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            pid_path = directory / "owner.pid"
            pid_path.write_text("424242\n", encoding="ascii")
            owner = directory / "owner"
            owner.write_bytes(b"")

            with (
                mock.patch.object(watcher, "_open_pidfd", return_value=None),
                mock.patch.object(watcher, "is_expected_owner", return_value=True),
                mock.patch.object(watcher.os, "kill") as kill,
            ):
                watcher.stop_owner(pid_path, owner)

            kill.assert_not_called()
            self.assertFalse(pid_path.exists())

    def test_single_png_uri_preserves_decoded_filename(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "original name.png"
            image.write_bytes(b"png")
            payload = f"{image.as_uri()}\r\n".encode()
            self.assertEqual(watcher.parse_single_png(payload), image)

    def test_multiple_file_uris_are_not_collapsed_to_one_image(self):
        payload = b"file:///tmp/a.png\r\nfile:///tmp/b.png\r\n"
        self.assertIsNone(watcher.parse_single_png(payload))

    def test_non_png_uri_is_rejected(self):
        payload = b"file:///tmp/document.txt\r\n"
        self.assertIsNone(watcher.parse_single_png(payload))

    def test_dolphin_uri_selection_requests_owner(self):
        self.assertEqual(
            watcher.selection_action({"text/uri-list", "application/x-kde4-urilist"}),
            "png-file",
        )

    def test_combined_uri_and_png_is_recognized_as_self_feedback(self):
        self.assertEqual(
            watcher.selection_action(
                {
                    "text/uri-list",
                    "image/png",
                    "application/x-affinity-clipboard-v2",
                }
            ),
            "self-feedback",
        )

    def test_external_uri_and_png_selection_requests_owner(self):
        self.assertEqual(
            watcher.selection_action({"text/uri-list", "image/png"}),
            "png-file",
        )

    def test_plain_text_releases_existing_owner(self):
        self.assertEqual(watcher.selection_action({"text/plain"}), "release")

    def _write_owner_script(self, directory: Path, body: str) -> Path:
        owner = directory / "owner.py"
        owner.write_text(f"#!{sys.executable}\n{body}", encoding="utf-8")
        owner.chmod(owner.stat().st_mode | stat.S_IXUSR)
        return owner

    def test_start_owner_writes_pid_after_ready_line(self):
        with tempfile.TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            pid_path = directory / "owner.pid"
            image = directory / "image.png"
            image.write_bytes(b"png")
            owner = self._write_owner_script(
                directory,
                """
import signal
import sys
import time

print("Affinity multi-format clipboard ready", flush=True)
signal.signal(signal.SIGTERM, lambda signum, frame: sys.exit(0))
while True:
    time.sleep(1)
""",
            )

            with warnings.catch_warnings():
                warnings.simplefilter("ignore", ResourceWarning)
                self.assertEqual(
                    watcher.start_owner(pid_path, owner, image, ready_timeout=1.0),
                    "mirrored",
                )
            pid = int(pid_path.read_text(encoding="ascii").strip())
            try:
                self.assertTrue(Path(f"/proc/{pid}").exists())
            finally:
                try:
                    os.kill(pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    os.waitpid(pid, 0)
                except ChildProcessError:
                    pass

    def test_start_owner_rejects_nonexact_ready_line(self):
        with tempfile.TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            pid_path = directory / "owner.pid"
            image = directory / "image.png"
            image.write_bytes(b"png")
            owner = self._write_owner_script(
                directory,
                """
import time

print(" Affinity multi-format clipboard ready ", flush=True)
time.sleep(10)
""",
            )

            self.assertEqual(
                watcher.start_owner(pid_path, owner, image, ready_timeout=0.5),
                "owner-invalid-output",
            )
            self.assertFalse(pid_path.exists())

    def test_start_owner_bounds_ready_output(self):
        with tempfile.TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            pid_path = directory / "owner.pid"
            image = directory / "image.png"
            image.write_bytes(b"png")
            owner = self._write_owner_script(
                directory,
                f"""
import sys
import time

sys.stdout.write("x" * {watcher.MAX_OWNER_READY_BYTES + 1})
sys.stdout.flush()
time.sleep(10)
""",
            )

            self.assertEqual(
                watcher.start_owner(pid_path, owner, image, ready_timeout=0.5),
                "owner-output-too-large",
            )
            self.assertFalse(pid_path.exists())

    def test_start_owner_times_out_without_pid_file(self):
        with tempfile.TemporaryDirectory() as directory_name:
            directory = Path(directory_name)
            pid_path = directory / "owner.pid"
            started_path = directory / "started.pid"
            image = directory / "image.png"
            image.write_bytes(b"png")
            owner = self._write_owner_script(
                directory,
                f"""
import os
import time

open({str(started_path)!r}, "w", encoding="ascii").write(str(os.getpid()))
time.sleep(10)
""",
            )

            self.assertEqual(
                watcher.start_owner(pid_path, owner, image, ready_timeout=0.1),
                "owner-timeout",
            )
            self.assertFalse(pid_path.exists())
            pid = int(started_path.read_text(encoding="ascii"))
            self.assertFalse(Path(f"/proc/{pid}").exists())


if __name__ == "__main__":
    unittest.main()
