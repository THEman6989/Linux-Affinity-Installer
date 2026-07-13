#!/usr/bin/env python3
from pathlib import Path
import signal
import subprocess
import time
import urllib.parse

WL_PASTE = "/home/linuxbrew/.linuxbrew/bin/wl-paste"
XCLIP = "/home/linuxbrew/.linuxbrew/bin/xclip"
BUSCTL = "/usr/bin/busctl"
MAX_URI_BYTES = 65536
owner = None
current_file = None
running = True


def command(args, timeout=2.0):
    return subprocess.run(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        timeout=timeout,
        check=False,
    )


def clipboard_types():
    result = command([WL_PASTE, "--list-types"])
    if result.returncode:
        return set()
    return {line.decode("utf-8", "replace").strip() for line in result.stdout.splitlines()}


def copied_png():
    result = command([WL_PASTE, "--type", "text/uri-list"])
    if result.returncode or len(result.stdout) > MAX_URI_BYTES:
        return None
    for raw in result.stdout.replace(b"\r", b"\n").split(b"\n"):
        raw = raw.strip()
        if not raw or raw.startswith(b"#"):
            continue
        uri = raw.decode("utf-8", "strict")
        parsed = urllib.parse.urlparse(uri)
        if parsed.scheme != "file":
            return None
        path = Path(urllib.parse.unquote(parsed.path))
        if path.is_file() and path.suffix.lower() == ".png":
            return path
        return None
    return None


def stop_owner():
    global owner
    if owner is not None and owner.poll() is None:
        owner.terminate()
        try:
            owner.wait(timeout=1)
        except subprocess.TimeoutExpired:
            owner.kill()
    owner = None


def start_owner(path):
    global owner
    stop_owner()
    subprocess.run(
        [
            BUSCTL,
            "--user",
            "call",
            "org.kde.klipper",
            "/klipper",
            "org.kde.klipper.klipper",
            "clearClipboardContents",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    # Klipper applies the clear asynchronously. Starting xclip immediately can
    # make the delayed clear remove the new owner and create a reclaim loop.
    time.sleep(0.4)
    source = path.open("rb")
    try:
        owner = subprocess.Popen(
            [
                XCLIP,
                "-silent",
                "-loops",
                "0",
                "-selection",
                "clipboard",
                "-t",
                "image/png",
                "-i",
            ],
            stdin=source,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    finally:
        source.close()
    print(f"Affinity PNG ready: {path}", flush=True)


def shutdown(_signum, _frame):
    global running
    running = False


signal.signal(signal.SIGTERM, shutdown)
signal.signal(signal.SIGINT, shutdown)

try:
    while running:
        types = clipboard_types()
        if "text/uri-list" in types:
            path = copied_png()
            if path is not None and path != current_file:
                current_file = path
                start_owner(path)
        elif any(mime.startswith("text/plain") for mime in types):
            current_file = None
            stop_owner()

        # Do not reclaim a selection merely because Affinity consumed it.
        # A new, different Dolphin URI event will start the next PNG owner.
        time.sleep(0.25)
finally:
    stop_owner()
