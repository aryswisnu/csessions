#!/usr/bin/env python3
"""Record demo/csessions.gif against the fake world built by fixture.py.

    ./demo/record.py

Drives the real csessions inside a pty, writes what the terminal received as an
asciicast, and hands that to agg (https://github.com/asciinema/agg) to render a
GIF. Needs only agg: no browser, no ttyd, no ffmpeg.

Nothing here reads your real ~/.claude -- see demo/README.md.
"""
import fcntl
import json
import os
import select
import shutil
import signal
import struct
import subprocess
import sys
import termios
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

DOWN, ESC, CR = "\x1b[B", "\x1b", "\r"

# (wait this long first, then send this) -- timings are what the viewer reads at,
# so they are generous: every pause is someone looking at the screen.
BROWSE = [
    (5.0, DOWN),        # list has painted; select the first session
    (3.0, DOWN),        # preview is open, walk down it
    (3.5, DOWN),        # a session on the other host, driven from a phone
    (3.5, DOWN),        # a closed one, recovered from its transcript alone
    (3.5, ESC),         # drop the preview
    (2.0, "postmortem"),  # fuzzy search reaches every machine at once
    (2.5, DOWN),
    (3.5, ESC),
    (1.5, None),        # final beat, then quit
]

# The ctrl-n binding hands the questions to a brand new terminal window, which
# cannot be filmed. `--new` asks them inline instead: same two pickers, same
# code, and in the fixture the session it finally starts is the stub `claude`,
# which exits immediately.
NEW = [
    (2.5, DOWN),        # host picker: this Mac, or the remote box
    (2.0, CR),
    (2.5, DOWN),        # then a working directory on that host
    (1.6, None),        # stop on the choice: what happens after is a session
]

# (name, argv, script, cols, rows). Terminal size is a framing decision: the
# demo is watched on a phone, so a tighter terminal means bigger type. The
# new-session pickers are a handful of lines and get a short one for the same
# reason.
SCENES = [
    ("browse", ["-a"], BROWSE, 132, 32),
    ("new", ["--new"], NEW, 104, 12),
]


def set_size(fd, cols, rows):
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))


def record(fixture, args, script, cast, cols, rows):
    master, slave = os.openpty()
    set_size(slave, cols, rows)
    env = dict(os.environ,
               HOME=f"{fixture}/home-local",
               PATH=f"{fixture}/bin:" + os.environ["PATH"],
               CSESSIONS_CONFIG=f"{fixture}/config.json",
               TERM="xterm-256color", LINES=str(rows), COLUMNS=str(cols))
    proc = subprocess.Popen([sys.executable, os.path.join(REPO, "csessions")] + args,
                            stdin=slave, stdout=slave, stderr=slave,
                            env=env, cwd=REPO, start_new_session=True)
    os.close(slave)

    # absolute offsets, so a slow read never shifts every later keystroke
    sends, at = [], 0.0
    for delay, keys in script:
        at += delay
        if keys:
            sends.append((at, keys))
    finish = at

    start, events, i = time.time(), [], 0
    while True:
        now = time.time() - start
        if i < len(sends) and now >= sends[i][0]:
            os.write(master, sends[i][1].encode())
            i += 1
            continue
        if now > finish:
            break
        r, _, _ = select.select([master], [], [], 0.05)
        if not r:
            if proc.poll() is not None:
                break
            continue
        try:
            data = os.read(master, 65536)
        except OSError:
            break
        if not data:
            break
        events.append([round(time.time() - start, 3), "o",
                       data.decode("utf-8", "replace")])

    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except OSError:
        pass
    proc.wait(timeout=5)
    os.close(master)

    header = {"version": 2, "width": cols, "height": rows,
              "timestamp": int(start), "env": {"TERM": "xterm-256color"}}
    with open(cast, "w") as f:
        f.write(json.dumps(header) + "\n")
        for e in events:
            f.write(json.dumps(e) + "\n")
    return len(events)


def main():
    if not shutil.which("agg"):
        sys.exit("agg not found: https://github.com/asciinema/agg/releases")

    # ages in the list are relative to now, so build the world immediately
    # before filming it rather than reusing an old one
    fixture = subprocess.run([sys.executable, os.path.join(HERE, "fixture.py")],
                             capture_output=True, text=True, check=True).stdout.strip()
    for stale in ("csessions-rows.json",):
        try:
            os.remove(os.path.join("/tmp", stale))
        except OSError:
            pass
    for f in os.listdir("/tmp"):
        if f.startswith("csessions-history-"):
            try:
                os.remove(os.path.join("/tmp", f))
            except OSError:
                pass

    try:
        for name, args, script, cols, rows in SCENES:
            cast = os.path.join(HERE, f"csessions-{name}.cast")
            gif = os.path.join(HERE, f"csessions-{name}.gif")
            n = record(fixture, args, script, cast, cols, rows)
            subprocess.run(["agg", "--font-size", "16", "--fps-cap", "12",
                            "--idle-time-limit", "2", "--theme", "asciinema",
                            cast, gif], check=True)
            print(f"{name}: {n} events -> {gif} "
                  f"({os.path.getsize(gif) / 1e6:.1f} MB)")
    finally:
        try:
            with open(f"{fixture}/pids") as f:
                for pid in f.read().split():
                    try:
                        os.kill(int(pid), signal.SIGTERM)
                    except (OSError, ValueError):
                        pass
        except OSError:
            pass


if __name__ == "__main__":
    main()
