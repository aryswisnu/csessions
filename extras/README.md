# Extras

Optional pieces. None are needed to use `csessions`, and none are installed for
you. Unlike the main script, two of these **write** outside their own files, so
read the warnings.

## build-app.sh

Builds `Claude Sessions.app`, a Dock app that opens `csessions -a` in its own
iTerm window, sized to half the screen.

```sh
extras/build-app.sh              # into ~/Applications
extras/build-app.sh /some/dir    # somewhere else
```

It needs iTerm, and `csessions` on your login shell's `PATH`, because the app
starts it from a login shell. It warns when either is missing. The icon needs
Pillow (`pip3 install pillow`). Without Pillow, the app keeps the default icon.

The script runs four steps, in this order:

1. `osacompile` compiles `launcher.applescript` into the app.
2. `icon.py` draws the icon into `applet.icns`. The script also deletes the
   asset catalogue that `osacompile` writes, because that catalogue outranks
   `applet.icns`.
3. It sets the bundle id to `local.csessions.app`.
4. `codesign` signs the app.

The order matters. macOS ties the app's permission to control iTerm to its
signature. A change after signing, such as a new icon, breaks the signature,
and the app then fails with `Not authorised to send Apple events` (-1743).
Signing last prevents this. If you edit the app by hand, run the script again.

## Window tiling

Not a file: a config key. `csessions` can send a keystroke after it opens a
session window, to hand that window to a tiling tool.

```json
{ "tile_shortcut": { "key_code": 17, "modifiers": ["control", "option", "command"] } }
```

That is ctrl-opt-cmd-T. It needs Accessibility permission for your terminal. Off
unless you set it.

## clipboard-bridge/

Makes pasting a screenshot into a session on another machine work, which it
otherwise cannot: a remote host has no clipboard, and SSH forwards ports rather
than pasteboards.

**It lets the remote host read your Mac's clipboard while a session is open**,
so read [clipboard-bridge/README.md](clipboard-bridge/README.md) before
installing it.

## title-prefix-watcher.py

**This writes to Claude Code's own files. Read this before running it.**

Sessions started on a remote host are indistinguishable from local ones in
claude.ai and the phone app. This renames them with a prefix so you can tell
where they are running.

You cannot set the prefix up front. Passing `--name` fills the same slot Claude
uses for the title it generates from the conversation, and the real title then
never lands. So this waits for the title to appear, then renames, the way
`/rename` does: it appends a `custom-title` record to the session transcript and
updates `name` in `~/.claude/sessions/<pid>.json`.

It is additive and idempotent: it only ever prepends a missing prefix, and never
invents a title. But it is still writing into another program's state, built on
an undocumented format. **Back up `~/.claude` before you run it.**

```sh
export CSESSIONS_TITLE_PREFIX="Work - "
python3 title-prefix-watcher.py
```

Once you trust it, on the remote host:

```cron
* * * * * CSESSIONS_TITLE_PREFIX="Work - " /usr/bin/python3 $HOME/.claude/title-prefix-watcher.py
```

`csessions` can label hosts in its own list with the `prefixes` config key
instead, which changes nothing on disk. Use this watcher only if you want the
prefix to show in claude.ai and the phone app too.
