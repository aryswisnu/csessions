#!/usr/bin/env python3
"""Build a throwaway world for the demo recording.

csessions only ever reads: `claude agents --json`, ~/.claude.json,
~/.claude/rate-limits.json, ~/.claude/sessions/*.json and
~/.claude/projects/*/*.jsonl -- reached locally, or over ssh for a remote host.
So a fake $HOME plus a stub `claude` and `ssh` on $PATH is a complete, honest
world: the real code runs unmodified against invented data.

Writes to demo/.fixture (gitignored). Nothing here touches your real ~/.claude.
"""
import json
import os
import shutil
import stat
import subprocess
import sys
import time

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".fixture")
NOW = time.time()
MIN, HOUR, DAY = 60, 3600, 86400

# (host, sessionId, title, cwd, kind, state, remote-controlled, seconds-ago)
SESSIONS = [
    ("local", "a1f3c8d2", "Refactor the billing adapter to drop the retry queue",
     "~/code/payments", "background", "working", True, 2 * MIN),
    ("work", "b7e21904", "Fix the flaky integration test on CI",
     "~/srv/api", "background", "working", True, 11 * MIN),
    ("local", "c4d90f61", "Proposed new architecture for the ingest pipeline",
     "~/code/ingest", "interactive", "-", False, 29 * MIN),
    ("work", "d0a5b733", "Debug the SSE reconnect loop",
     "~/srv/gateway", "background", "blocked", True, 2 * HOUR),
    ("local", "e6b1c045", "Upgrade the Postgres driver to v5",
     "~/code/payments", "interactive", "-", False, 26 * HOUR),
    ("work", "f2c7d918", "Write the incident postmortem for the 03:00 page",
     "~/srv/api", "interactive", "-", False, 3 * DAY),
]

# Conversations shown in the preview pane. Kept short: only the last 5 turns render.
TALK = {
    "a1f3c8d2": [
        ("user", "the retry queue is doing more harm than good. can we just drop it?"),
        ("assistant",
         "Yes. The queue only ever retries on `502` and `504`, and the gateway "
         "already retries those itself before we see them.\n\n"
         "So every queued job is a **second** retry of something that was retried "
         "once. That is where the duplicate charges came from.\n\n"
         "- `RetryQueue` and its table go\n"
         "- `BillingAdapter.submit` calls the gateway directly\n"
         "- the `billing_retry_depth` metric goes with it\n\n"
         "About 180 lines deleted, nothing added."),
        ("user", "do it, but keep the metric"),
        ("assistant",
         "Done. Queue removed, `billing_retry_depth` kept and now reports the "
         "gateway's own retry count instead of ours, so the dashboard keeps working.\n\n"
         "```\n 4 files changed, 11 insertions(+), 174 deletions(-)\n```\n\n"
         "Tests pass. `test_duplicate_charge_on_504` now fails without the fix, "
         "which it did not before."),
    ],
    "b7e21904": [
        ("user", "/status"),
        ("user", "test_checkout_flow fails maybe 1 run in 5 on CI, never locally"),
        ("assistant",
         "It is a clock race, not a flake in the usual sense.\n\n"
         "The test seeds an order with `created_at = now()` then asserts it shows "
         "in the *last minute* window. CI runs the seed and the assert in separate "
         "transactions, and Postgres `now()` is transaction start time, so on a slow "
         "runner the two differ by more than a second.\n\n"
         "Freeze the clock in the fixture rather than widening the window."),
    ],
    "c4d90f61": [
        ("user", "should ingest own its own queue or share the one billing uses?"),
        ("assistant",
         "Own queue.\n\n"
         "Shared would couple two services with different failure behaviour: "
         "billing must never drop a message, ingest can drop freely and re-poll. "
         "One queue means one retention policy, and it would have to be billing's.\n\n"
         "The operational cost of a second queue is a dashboard row."),
    ],
    "d0a5b733": [
        ("user", "the SSE stream reconnects every ~30s in prod but not staging"),
        ("assistant",
         "Staging has no load balancer in front of it. That is the whole difference.\n\n"
         "The ALB idle timeout is 30s and an SSE stream that is merely *open* with "
         "no bytes flowing counts as idle. The server never sends a heartbeat, so "
         "the ALB closes it and the client reconnects.\n\n"
         "Send a `: ping` comment line every 15s. One line of server code."),
        ("user", "is a comment line safe for all clients?"),
    ],
    "e6b1c045": [
        ("user", "bump the pg driver to v5, check what breaks"),
        ("assistant",
         "Two breaks, both in our code rather than the driver.\n\n"
         "- v5 returns `bytes` for `json` columns, not `dict`. Four call sites assume dict.\n"
         "- connection pooling moved behind `Pool()`, so `connect(max_conns=)` is gone.\n\n"
         "Neither is deep. The json one is the risk: it fails at runtime, not import."),
    ],
    "f2c7d918": [
        ("user", "draft the postmortem for last night"),
        ("assistant",
         "# Incident: checkout unavailable, 02:51-03:34\n\n"
         "**Impact.** 43 minutes, all checkout traffic. 1,204 failed attempts, "
         "no data loss, no duplicate charges.\n\n"
         "**Cause.** A migration added a `NOT NULL` column to `orders` without a "
         "default. The deploy ran it against a table under write load, which took "
         "an `ACCESS EXCLUSIVE` lock and queued every write behind it.\n\n"
         "**Detection.** Paged at 03:00 by checkout error rate, nine minutes in. "
         "The migration itself had no alert."),
    ],
}

RATE_LIMITS = {
    "five_hour": {"used_percentage": 34, "resets_at": NOW + 59 * MIN},
    "seven_day": {"used_percentage": 85, "resets_at": NOW + 2.6 * DAY},
}

# Enough assistant turns, dated across the week, to make the STATS panel real.
USAGE = [(0.4, 1_900_000), (3, 2_400_000), (26, 6_100_000), (50, 5_200_000),
         (74, 4_800_000), (99, 7_300_000), (122, 3_900_000), (146, 6_600_000)]


def write(path, text, mtime=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)
    if mtime:
        os.utime(path, (mtime, mtime))


def home_for(host):
    return os.path.join(OUT, f"home-{host}")


def build_home(host, pids):
    home = home_for(host)
    mine = [s for s in SESSIONS if s[0] == host]

    # account identity and plan, read from ~/.claude.json
    write(f"{home}/.claude.json", json.dumps({"oauthAccount": {
        "emailAddress": "you@example.com", "userRateLimitTier": "max_5x"}}))
    write(f"{home}/.claude/rate-limits.json", json.dumps(RATE_LIMITS))

    # a login shell must find the stub `claude`; $HOME is ours, so its profile is too
    write(f"{home}/.bash_profile", f'export PATH="{OUT}/bin:$PATH"\n')

    for i, (_, sid, title, cwd, kind, state, rc, ago) in enumerate(mine):
        ts = NOW - ago
        # the session the demo finally starts really does cd here, so the
        # directory has to exist or bash prints an error over the last frame
        os.makedirs(os.path.join(home, cwd.lstrip("~/")), exist_ok=True)
        slug = "-" + cwd.strip("~/").replace("/", "-")

        # transcript: the only record a closed session leaves behind
        lines = [json.dumps({"type": "ai-title", "aiTitle": title,
                             "cwd": cwd, "sessionId": sid})]
        for n, (who, text) in enumerate(TALK.get(sid, [])):
            rec = {"type": who, "sessionId": sid, "cwd": cwd,
                   "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S",
                                              time.gmtime(ts - (10 - n) * MIN))}
            if who == "user":
                rec["message"] = {"role": "user", "content": text}
            else:
                rec["message"] = {"role": "assistant", "model": "claude-opus-5",
                                  "content": [{"type": "text", "text": text}],
                                  "usage": {"input_tokens": 1200, "output_tokens": 800,
                                            "cache_read_input_tokens": 240_000,
                                            "cache_creation_input_tokens": 9_000}}
            lines.append(json.dumps(rec))

        write(f"{home}/.claude/projects/{slug}/{sid}.jsonl", "\n".join(lines) + "\n", ts)

        # a live session also has a daemon record; the pid must really be alive,
        # because the probe kill(pid, 0)s it to spot records left by a hard kill
        if state != "-":
            pid = pids.pop()
            write(f"{home}/.claude/sessions/{pid}.json", json.dumps({
                "pid": pid, "sessionId": sid, "name": title, "cwd": cwd,
                "updatedAt": int(ts * 1000), "startedAt": int((ts - HOUR) * 1000),
                **({"bridgeSessionId": "bridge-" + sid} if rc else {})}))

    # Usage totals need more traffic than six conversations carry. Park it in its
    # own untitled transcript: the usage probe still counts it, while the list
    # skips untitled sessions and no preview ever shows these stub turns.
    if host == "local":
        bulk = [json.dumps({
            "type": "assistant",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S",
                                       time.gmtime(NOW - hours_ago * HOUR)),
            "message": {"role": "assistant", "model": "claude-opus-5",
                        "content": [{"type": "text", "text": "."}],
                        "usage": {"input_tokens": 4_000, "output_tokens": 2_500,
                                  "cache_read_input_tokens": cached,
                                  "cache_creation_input_tokens": 30_000}}})
            for hours_ago, cached in USAGE]
        write(f"{home}/.claude/projects/-archive/00000000.jsonl",
              "\n".join(bulk) + "\n", NOW - HOUR)


def agents_json(host):
    rows = []
    for h, sid, title, cwd, kind, state, rc, ago in SESSIONS:
        if h != host or state == "-":
            continue
        rows.append({"sessionId": sid, "name": title, "cwd": cwd, "kind": kind,
                     "state": state, "startedAt": int((NOW - ago - HOUR) * 1000)})
    return json.dumps(rows, indent=1)


def stub(path, body):
    write(path, "#!/bin/bash\n" + body)
    os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def main():
    shutil.rmtree(OUT, ignore_errors=True)
    os.makedirs(f"{OUT}/bin")

    # live sessions need live pids. sleepers outlive the recording, then get reaped.
    procs = []
    for host in ("local", "work"):
        pids = []
        for _ in range(sum(1 for s in SESSIONS if s[0] == host and s[5] != "-")):
            # detached, with our pipes closed: a caller using $(fixture.py) would
            # otherwise block until these exit, because they hold its stdout open
            p = subprocess.Popen(["sleep", "900"], stdin=subprocess.DEVNULL,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                 start_new_session=True)
            procs.append(p)
            pids.append(p.pid)
        build_home(host, pids)

    write(f"{OUT}/pids", "\n".join(str(p.pid) for p in procs) + "\n")

    # `claude agents --json` for whichever home we are pretending to be
    stub(f"{OUT}/bin/claude", f'''
[ "$1" = --version ] && {{ echo "2.1.276 (Claude Code)"; exit 0; }}
[ "$1" = agents ] || exit 0
case "$HOME" in
  *home-work) cat <<'EOF'
{agents_json("work")}
EOF
  ;;
  *) cat <<'EOF'
{agents_json("local")}
EOF
  ;;
esac
''')

    # csessions reaches a remote host with: ssh -o.. -o.. target "bash -lc '...'"
    # Run that command here instead, pointed at the other fake home.
    stub(f"{OUT}/bin/ssh", f'''
cmd="${{@: -1}}"
HOME="{OUT}/home-work" exec bash -c "$cmd"
''')

    write(f"{OUT}/config.json", json.dumps({
        "hosts": {"local": None, "work": "you@10.0.0.5"},
        "refresh": 5, "preview_width": 40, "terminal": "iTerm"}, indent=2))

    print(OUT)


if __name__ == "__main__":
    main()
