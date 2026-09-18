#!/usr/bin/env python3
"""Prefix this machine's Claude session titles, e.g. "Work - ".

Runs on a timer. Claude writes a session's real title only once it has enough
conversation to name it, so the prefix cannot be set up front: passing --name
fills the same slot and the auto-title then never lands. This waits for the
real title to appear and renames afterwards, the way /rename does.

Idempotent and additive: it only ever prepends the prefix to a title that
lacks it, and never invents a title of its own.
"""
import glob
import json
import os
import tempfile
import time

PREFIX = os.environ.get("CSESSIONS_TITLE_PREFIX", "")
FRESH = 3 * 86400          # ignore transcripts nobody has touched in days
HOME = os.path.expanduser("~")


def latest_title(path):
    """The title Claude last recorded for this transcript, if any."""
    title = None
    try:
        with open(path, errors="ignore") as f:
            for line in f:
                if "itle" not in line:          # matches aiTitle / customTitle
                    continue
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                title = d.get("customTitle") or d.get("aiTitle") or title
    except OSError:
        return None
    return title


def set_title(path, sid, title):
    with open(path, "a") as f:
        f.write(json.dumps({"type": "custom-title", "customTitle": title,
                            "sessionId": sid}) + "\n")


def sync_pid_file(sid, title):
    """Keep `claude agents --json` in step with the transcript."""
    for p in glob.glob(f"{HOME}/.claude/sessions/*.json"):
        try:
            with open(p) as f:
                d = json.load(f)
        except (OSError, ValueError):
            continue
        if d.get("sessionId") != sid or d.get("name") == title:
            continue
        d["name"], d["nameSource"] = title, "user"
        try:  # atomic, so a half-written file never reaches Claude
            with tempfile.NamedTemporaryFile("w", dir=os.path.dirname(p),
                                             delete=False) as tmp:
                json.dump(d, tmp)
            os.replace(tmp.name, p)
        except OSError:
            pass
        return


def main():
    cutoff = time.time() - FRESH
    renamed = 0
    for path in glob.glob(f"{HOME}/.claude/projects/*/*.jsonl"):
        try:
            if os.path.getmtime(path) < cutoff:
                continue
        except OSError:
            continue
        title = latest_title(path)
        if not title or title.startswith(PREFIX):
            continue
        sid = os.path.basename(path)[:-6]
        new = PREFIX + title
        try:
            set_title(path, sid, new)
        except OSError:
            continue
        sync_pid_file(sid, new)
        renamed += 1
        print(f"{time.strftime('%F %T')} renamed {sid[:8]} -> {new}", flush=True)
    return renamed


if __name__ == "__main__":
    if not PREFIX:
        raise SystemExit("set CSESSIONS_TITLE_PREFIX, e.g. 'Work - '")
    main()
