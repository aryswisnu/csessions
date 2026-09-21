# Clipboard bridge

Paste a screenshot into a session running on another machine and have it
actually arrive.

## Why it is needed

A terminal session on a remote host has no clipboard of its own. SSH forwards
ports, not pasteboards, so inside a remote Claude Code session:

- `Ctrl+V` reads the **remote** clipboard. On a headless box there isn't one:
  no `xclip`, no `xsel`, no `wl-paste`, no `DISPLAY`. Nothing to read.
- `Cmd+V` pastes what macOS puts on the clipboard as text, which for a
  screenshot is a path like
  `/var/folders/…/T/…/pasted-image-20260921-112834.png`. That file is on your
  Mac. Claude opens it on the remote host and is told it does not exist.

The desktop app has no such problem: its SSH environment keeps the client on
your Mac, so the image is read locally and sent as image data.

This makes the terminal behave the same way. `Cmd+V`, then send.

## Read this before installing

While a session is open, **anything running on that host as your user can ask
your Mac for whatever is currently on your clipboard.** Not just images you
meant to paste: passwords, tokens, whatever you copied last.

The bridge listens on `127.0.0.1` only, and the sole route in is the reverse
tunnel csessions opens with a session, so it is reachable only while one is
open. Requests need a token stored `0600` on both ends. But the remote host is
trusted with your clipboard for as long as you are working on it, and on a box
with other accounts a root user can read that token file.

If that is not a trade you want, use the desktop app for screenshots instead.

## Install

**On your Mac**, start the bridge and note the port:

```sh
python3 server.py --install     # launchd agent, survives reboot
# or: python3 server.py         # foreground, to try it out
```

The first paste raises a macOS permission prompt for controlling your Mac.
That prompt is the pasteboard read; macOS only asks once.

**Tell csessions to carry it** in `~/.config/csessions/config.json`:

```json
{ "clipboard_port": 8477 }
```

Every remote session csessions opens now reverse-forwards that port. Sessions
you open by hand need `-R 8477:127.0.0.1:8477` on the ssh command.

**On each remote host**, install the token and the hook:

```sh
ssh you@host 'mkdir -p ~/.config/csessions ~/.claude/hooks'
scp ~/.config/csessions/clipboard-token you@host:.config/csessions/
scp ~/.config/csessions/clipboard-port  you@host:.config/csessions/
ssh you@host 'chmod 600 ~/.config/csessions/clipboard-token'
scp hook.py you@host:.claude/hooks/clipboard-bridge.py
```

Then add the hook to the remote `~/.claude/settings.json`, merging with what is
already there rather than replacing it:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      { "hooks": [ { "type": "command",
                     "command": "python3 ~/.claude/hooks/clipboard-bridge.py" } ] }
    ]
  }
}
```

## How it behaves

The hook looks at each prompt for a path to an image file that does not exist
on this machine. Finding one, it pulls the current clipboard image through the
tunnel, writes it to `~/.cache/csessions-clips/`, and tells Claude to read that
instead.

It stays quiet when it cannot help: no tunnel, no token, nothing on the
clipboard, or a path that resolves locally. The prompt goes through untouched,
so a host without the bridge behaves exactly as before.

It sends whatever is on the clipboard *now*, which is the image you just
copied. Paste a path you saved earlier and you will get your current clipboard,
not that older screenshot.

## Checking it works

With the bridge running on your Mac and an image copied:

```sh
ssh -R 8477:127.0.0.1:8477 you@host \
  "curl -s -o /tmp/c.png -w '%{http_code}\n' \
     -H \"X-Clip-Token: \$(cat ~/.config/csessions/clipboard-token)\" \
     http://127.0.0.1:8477/ && file /tmp/c.png"
```

`200` and `PNG image data` means the path is open. `404` means the clipboard
holds no image; `403` a token mismatch; a curl error means no tunnel.

## Removing it

```sh
launchctl unload ~/Library/LaunchAgents/local.csessions.clipboard.plist
rm ~/Library/LaunchAgents/local.csessions.clipboard.plist
rm ~/.config/csessions/clipboard-token ~/.config/csessions/clipboard-port
```

Drop `clipboard_port` from the config, and remove the hook and token from each
remote host.
