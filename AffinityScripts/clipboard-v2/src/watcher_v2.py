#!/usr/bin/env python3
"""Event-driven Dolphin PNG file to multi-format X11 clipboard bridge."""

from __future__ import annotations

import argparse
import fcntl
import os
from pathlib import Path
import select
import selectors
import shutil
import signal
import subprocess
import sys
import time
from typing import Optional
import urllib.parse

MAX_URI_BYTES = 64 * 1024
MAX_TYPES_BYTES = 64 * 1024
READ_TIMEOUT_SECONDS = 2.0
OWNER_READY_LINE = "Affinity multi-format clipboard ready"
OWNER_READY_TIMEOUT_SECONDS = 2.0
MAX_OWNER_READY_BYTES = 4096
SELF_FEEDBACK_MIME = "application/x-affinity-clipboard-v2"


def command_path(name: str) -> str:
    value = shutil.which(name)
    if value is None:
        raise RuntimeError(f"required command not found: {name}")
    return value


def parse_single_png(payload: bytes) -> Optional[Path]:
    if len(payload) > MAX_URI_BYTES:
        return None
    paths: list[Path] = []
    for raw in payload.replace(b"\r", b"\n").split(b"\n"):
        raw = raw.strip()
        if not raw or raw.startswith(b"#"):
            continue
        try:
            parsed = urllib.parse.urlparse(raw.decode("utf-8", "strict"))
        except UnicodeDecodeError:
            return None
        if parsed.scheme != "file" or parsed.netloc not in ("", "localhost"):
            return None
        paths.append(Path(urllib.parse.unquote(parsed.path)))
    if len(paths) != 1:
        return None
    path = paths[0]
    if path.suffix.lower() != ".png" or not path.is_file():
        return None
    return path


def selection_action(types: set[str]) -> str:
    has_uri = "text/uri-list" in types
    if has_uri and SELF_FEEDBACK_MIME in types:
        return "self-feedback"
    if has_uri:
        return "png-file"
    return "release"


def read_bounded(args: list[str], max_bytes: int) -> tuple[Optional[bytes], str]:
    process = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    assert process.stdout is not None
    fd = process.stdout.fileno()
    os.set_blocking(fd, False)
    selector = selectors.DefaultSelector()
    selector.register(fd, selectors.EVENT_READ)
    payload = bytearray()
    deadline = time.monotonic() + READ_TIMEOUT_SECONDS
    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None, "timeout"
            if not selector.select(remaining):
                return None, "timeout"
            chunk = os.read(fd, min(16 * 1024, max_bytes + 1 - len(payload)))
            if not chunk:
                return_code = process.wait(timeout=max(0.1, remaining))
                if return_code != 0:
                    return None, "read-failed"
                return bytes(payload), "ok"
            payload.extend(chunk)
            if len(payload) > max_bytes:
                return None, "too-large"
    finally:
        selector.close()
        process.stdout.close()
        if process.poll() is None:
            process.kill()
            process.wait()


def get_types(wl_paste: str) -> set[str]:
    payload, status = read_bounded([wl_paste, "--list-types"], MAX_TYPES_BYTES)
    if status != "ok" or payload is None:
        return set()
    return {
        line.decode("utf-8", "replace").strip()
        for line in payload.splitlines()
        if line.strip()
    }


def runtime_paths() -> tuple[Path, Path]:
    runtime = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))
    return (
        runtime / "affinity-clipboard-v2.owner.pid",
        runtime / "affinity-clipboard-v2.lock",
    )


def read_owner_pid(pid_path: Path) -> Optional[int]:
    try:
        pid = int(pid_path.read_text(encoding="ascii").strip())
    except (FileNotFoundError, OSError, ValueError):
        return None
    return pid if pid > 1 else None


def is_expected_owner(pid: int, owner_binary: Path) -> bool:
    try:
        executable = Path(f"/proc/{pid}/exe").resolve(strict=True)
        return executable == owner_binary.resolve(strict=True)
    except (FileNotFoundError, OSError):
        return False


def _open_pidfd(pid: int) -> Optional[int]:
    pidfd_open = getattr(os, "pidfd_open", None)
    if pidfd_open is None:
        return None
    try:
        return pidfd_open(pid, 0)
    except (OSError, ProcessLookupError):
        return None


def _pidfd_send(pidfd: int, signum: signal.Signals) -> bool:
    sender = getattr(signal, "pidfd_send_signal", None)
    if sender is None:
        return False
    try:
        sender(pidfd, signum, None, 0)
        return True
    except ProcessLookupError:
        return True
    except OSError:
        return False


def _pidfd_exited(pidfd: int, timeout: float) -> bool:
    readable, _, _ = select.select([pidfd], [], [], timeout)
    return bool(readable)


def stop_owner(pid_path: Path, owner_binary: Path) -> None:
    pid = read_owner_pid(pid_path)
    pidfd = _open_pidfd(pid) if pid is not None else None
    try:
        if (
            pid is not None
            and pidfd is not None
            and is_expected_owner(pid, owner_binary)
            and _pidfd_send(pidfd, signal.SIGTERM)
        ):
            deadline = time.monotonic() + 1.0
            while time.monotonic() < deadline:
                if _pidfd_exited(pidfd, 0.02):
                    break
            if not _pidfd_exited(pidfd, 0):
                _pidfd_send(pidfd, signal.SIGKILL)
    finally:
        if pidfd is not None:
            os.close(pidfd)
    try:
        pid_path.unlink()
    except FileNotFoundError:
        pass


def _terminate_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=0.5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def _wait_for_owner_ready(process: subprocess.Popen[bytes], timeout: float) -> str:
    assert process.stdout is not None
    fd = process.stdout.fileno()
    os.set_blocking(fd, False)
    selector = selectors.DefaultSelector()
    selector.register(fd, selectors.EVENT_READ)
    buffer = bytearray()
    expected = OWNER_READY_LINE.encode("ascii")
    deadline = time.monotonic() + timeout
    try:
        while True:
            if process.poll() is not None:
                return "owner-failed"
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return "owner-timeout"
            if not selector.select(remaining):
                return "owner-timeout"
            read_size = min(1024, MAX_OWNER_READY_BYTES + 1 - len(buffer))
            if read_size <= 0:
                return "owner-output-too-large"
            chunk = os.read(fd, read_size)
            if not chunk:
                return "owner-failed"
            buffer.extend(chunk)
            if len(buffer) > MAX_OWNER_READY_BYTES:
                return "owner-output-too-large"
            while b"\n" in buffer:
                line, _, remainder = buffer.partition(b"\n")
                buffer = bytearray(remainder)
                if line == expected:
                    return "ready"
                return "owner-invalid-output"
    finally:
        selector.close()


def start_owner(
    pid_path: Path,
    owner_binary: Path,
    png_path: Path,
    ready_timeout: float = OWNER_READY_TIMEOUT_SECONDS,
) -> str:
    stop_owner(pid_path, owner_binary)
    process = subprocess.Popen(
        [str(owner_binary), str(png_path)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    status = _wait_for_owner_ready(process, ready_timeout)
    assert process.stdout is not None
    process.stdout.close()
    if status != "ready":
        _terminate_process(process)
        return status
    temporary = pid_path.with_suffix(f".tmp.{os.getpid()}")
    temporary.write_text(f"{process.pid}\n", encoding="ascii")
    os.replace(temporary, pid_path)
    return "mirrored"


def detach_watch_stdin() -> None:
    devnull = os.open(os.devnull, os.O_RDONLY)
    try:
        os.dup2(devnull, sys.stdin.fileno())
    finally:
        if devnull != sys.stdin.fileno():
            os.close(devnull)


def event_main(owner_binary: Path) -> int:
    detach_watch_stdin()
    wl_paste = command_path("wl-paste")
    pid_path, lock_path = runtime_paths()
    with lock_path.open("a+b") as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        types = get_types(wl_paste)
        action = selection_action(types)
        if action == "self-feedback":
            return 0
        if action == "release":
            stop_owner(pid_path, owner_binary)
            return 0

        payload, status = read_bounded(
            [wl_paste, "--type", "text/uri-list"], MAX_URI_BYTES
        )
        if status != "ok" or payload is None:
            print(f"Affinity clipboard V2 warning: {status}", file=sys.stderr)
            return 0
        png_path = parse_single_png(payload)
        if png_path is None:
            stop_owner(pid_path, owner_binary)
            return 0
        status = start_owner(pid_path, owner_binary, png_path)
        if status == "mirrored":
            print(f"Affinity clipboard V2 ready: {png_path}", flush=True)
        else:
            print(f"Affinity clipboard V2 warning: {status}", file=sys.stderr)
    return 0


def watch_main(wl_paste: str, owner_binary: Path) -> int:
    pid_path, _ = runtime_paths()
    stop_owner(pid_path, owner_binary)
    command = [
        wl_paste,
        "--watch",
        sys.executable,
        str(Path(__file__).resolve()),
        "--event",
        "--owner",
        str(owner_binary),
    ]
    subprocess.run(command, check=False)
    return 1


def parse_args() -> argparse.Namespace:
    default_owner = Path(__file__).resolve().with_name("affinity-clipboard-owner")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--owner", type=Path, default=default_owner)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not os.environ.get("WAYLAND_DISPLAY") or not os.environ.get("DISPLAY"):
        print("Wayland and Xwayland displays are required", file=sys.stderr)
        return 2
    owner_binary = args.owner.resolve()
    if not owner_binary.is_file() or not os.access(owner_binary, os.X_OK):
        print(f"owner binary is not executable: {owner_binary}", file=sys.stderr)
        return 2
    try:
        if args.event:
            return event_main(owner_binary)
        return watch_main(command_path("wl-paste"), owner_binary)
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"Affinity clipboard V2 error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
