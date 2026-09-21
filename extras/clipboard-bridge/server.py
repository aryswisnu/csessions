#!/usr/bin/env python3
"""Serve this Mac's clipboard image to sessions running on other machines.

A terminal session on a remote host has no clipboard. SSH forwards ports, not
pasteboards, so Ctrl+V inside a remote Claude Code session has nothing to read,
and Cmd+V pastes a path to a file that only exists here.

This listens on localhost. csessions reverse-forwards the same port into every
remote session it opens, so the remote side can ask for the image you just
copied, and only while one of those sessions is open.

    python3 server.py            # foreground, prints the port and token
    python3 server.py --install  # load it as a launchd agent instead

Requests must carry the token in an X-Clip-Token header. It is written to
~/.config/csessions/clipboard-token with owner-only permissions; csessions
passes it to the remote hook through the session's environment.
"""
import argparse
import http.server
import os
import plistlib
import secrets
import subprocess
import sys
import tempfile

CONF = os.path.expanduser("~/.config/csessions")
TOKEN_FILE = os.path.join(CONF, "clipboard-token")
PORT_FILE = os.path.join(CONF, "clipboard-port")
LABEL = "local.csessions.clipboard"
DEFAULT_PORT = 8477


def token():
    """A stable secret, created once, readable only by this account."""
    os.makedirs(CONF, exist_ok=True)
    try:
        with open(TOKEN_FILE) as f:
            t = f.read().strip()
        if t:
            return t
    except OSError:
        pass
    t = secrets.token_urlsafe(24)
    fd = os.open(TOKEN_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(t)
    return t


def clipboard_png():
    """The clipboard's image as PNG bytes, or None when it holds no image.

    osascript is the only route that sees the real pasteboard; pbpaste cannot
    return image data. It writes to a file rather than stdout because AppleScript
    has no way to hand back raw bytes.
    """
    path = os.path.join(tempfile.gettempdir(), "csessions-clip.png")
    script = (f'set f to (open for access POSIX file "{path}" with write permission)\n'
              'set eof f to 0\n'
              'try\n'
              '  write (the clipboard as «class PNGf») to f\n'
              'on error\n'
              '  close access f\n'
              '  error "no image"\n'
              'end try\n'
              'close access f')
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if r.returncode != 0:
        return None
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError:
        return None
    finally:
        try:
            os.remove(path)
        except OSError:
            pass
    return data or None


class Handler(http.server.BaseHTTPRequestHandler):
    secret = ""

    def do_GET(self):
        if not secrets.compare_digest(self.headers.get("X-Clip-Token", ""), self.secret):
            self.send_error(403, "bad token")
            return
        png = clipboard_png()
        if png is None:
            self.send_error(404, "clipboard holds no image")
            return
        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", str(len(png)))
        self.end_headers()
        self.wfile.write(png)

    def log_message(self, *a):
        pass          # one line per paste is noise, and it would go to a log nobody reads


def install(port):
    """Register with launchd so the bridge survives a reboot."""
    agents = os.path.expanduser("~/Library/LaunchAgents")
    os.makedirs(agents, exist_ok=True)
    plist = os.path.join(agents, f"{LABEL}.plist")
    with open(plist, "wb") as f:
        plistlib.dump({
            "Label": LABEL,
            "ProgramArguments": [sys.executable, os.path.abspath(__file__),
                                 "--port", str(port)],
            "RunAtLoad": True,
            "KeepAlive": True,
        }, f)
    subprocess.run(["launchctl", "unload", plist], capture_output=True)
    subprocess.run(["launchctl", "load", plist], check=True)
    print(f"loaded {LABEL} on port {port}")
    print("first paste will ask for permission to control your Mac; that is the")
    print("pasteboard read, and macOS only asks once")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--install", action="store_true")
    args = ap.parse_args()

    os.makedirs(CONF, exist_ok=True)
    with open(PORT_FILE, "w") as f:
        f.write(str(args.port))
    if args.install:
        return install(args.port)

    Handler.secret = token()
    # localhost only: the sole way in is a reverse tunnel csessions opens
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"clipboard bridge on 127.0.0.1:{args.port}")
    print(f"token in {TOKEN_FILE}")
    srv.serve_forever()


if __name__ == "__main__":
    main()
