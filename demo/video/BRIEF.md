---
workflow: general-video
flow: automation
storyboard: no
---

# csessions demo

**Message.** One list shows every Claude Code session on every machine you use,
and you can start another from it.

**Concept angle.** The footage is the product, so nothing is drawn on top of it:
the only authored layer is a camera that looks where a person would look.

**Format.** 1920x1180 (the browse capture's native 1.627 ratio, so the terminal
is never cropped or pillarboxed), 36.6s, no narration, no music, MP4 for a
GitHub README.

## Assets

- `assets/browse.mp4` (2486x1528, 24.56s): browsing the session list, opening a
  preview, fuzzy searching.
- `assets/new.mp4` (1780x510, 12s): the two new-session pickers, captured in a
  short terminal so they fill the frame at native size.

Both are rendered from asciicasts in the csessions repo (`demo/record.py`),
recorded against fabricated data.

## Customizations

- Camera moves are translate + scale with a fixed centre origin, cut to the beat
  timestamps of each capture.
- Scene 2 drifts rather than punches, because it was recaptured at a size that
  needs no magnification.
