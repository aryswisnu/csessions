#!/usr/bin/env python3
"""Turn a pasted path from another machine into an image this one can read.

Install as a UserPromptSubmit hook on the REMOTE host.

Pasting a screenshot into a terminal session gives you the path the Mac wrote
it to. The session runs here, so that path means nothing, and Claude opens it
only to be told the file does not exist. The image itself never left the Mac,
because SSH forwards ports and not pasteboards.

This spots such a path, pulls the image from the Mac through the reverse tunnel
csessions opens with the session, writes it here, and tells Claude where it
landed. An ordinary Cmd+V then works, the way it does in the desktop app.

It stays quiet unless it can help: no tunnel, no token, nothing on the
clipboard, or a path that exists locally, and the prompt goes through untouched.
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

CONF = os.path.expanduser("~/.config/csessions")
SAVE_DIR = os.path.expanduser("~/.cache/csessions-clips")
# a quoted or bare path to an image file, which is what a paste leaves behind
PATH = re.compile(r"""["']?(/[^\s"']+\.(?:png|jpe?g|gif|webp))["']?""", re.I)


def read(name, default=""):
    try:
        with open(os.path.join(CONF, name)) as f:
            return f.read().strip() or default
    except OSError:
        return default


def fetch():
    """The Mac's clipboard image, or None if it cannot be had."""
    token = read("clipboard-token")
    if not token:
        return None
    port = read("clipboard-port", "8477")
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{port}/",
                                     headers={"X-Clip-Token": token})
        with urllib.request.urlopen(req, timeout=4) as r:
            return r.read()
    except (urllib.error.URLError, OSError):
        return None   # no tunnel, or the clipboard holds no image


def main():
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return
    prompt = payload.get("prompt") or ""

    missing = [m.group(1) for m in PATH.finditer(prompt)
               if not os.path.exists(m.group(1))]
    if not missing:
        return        # nothing pasted, or it is already readable here

    png = fetch()
    if not png:
        return

    os.makedirs(SAVE_DIR, exist_ok=True)
    local = os.path.join(SAVE_DIR, f"clip-{int(time.time())}.png")
    try:
        with open(local, "wb") as f:
            f.write(png)
    except OSError:
        return

    # Name every path this replaces: the prompt still carries them, and without
    # saying so Claude would open the original and report a missing file.
    listed = ", ".join(missing)
    json.dump({"hookSpecificOutput": {
        "hookEventName": "UserPromptSubmit",
        "additionalContext":
            f"The image the user pasted is not at {listed}: that is a path on "
            f"their own machine, not this one. It has been copied here to "
            f"{local}. Read that file instead, and do not report the original "
            f"path as missing."}}, sys.stdout)


if __name__ == "__main__":
    main()
