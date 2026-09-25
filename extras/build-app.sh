#!/usr/bin/env bash
# Build "Claude Sessions.app": a Dock app that opens csessions in its own iTerm
# window, sized to half the screen.
#
#   extras/build-app.sh              # into ~/Applications
#   extras/build-app.sh /some/dir    # somewhere else
#
# The steps must run in this order. osacompile signs the bundle, and macOS ties
# the app's permission to control iTerm to that signature, so any change after
# signing (the icon, the bundle id) silently revokes it. Signing goes last.
set -euo pipefail

here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
dest=${1:-$HOME/Applications}
app="$dest/Claude Sessions.app"
plist="$app/Contents/Info.plist"
res="$app/Contents/Resources"

[ -d /Applications/iTerm.app ] || echo "warning: iTerm not found; the app opens its window in iTerm" >&2
# the app starts csessions from a login shell, so that is the PATH that matters
bash -lc 'command -v csessions' >/dev/null ||
  echo "warning: csessions is not on your login shell's PATH; the app will not find it" >&2

mkdir -p "$dest"
rm -rf "$app"
osacompile -o "$app" "$here/launcher.applescript"

if python3 -c 'import PIL' 2>/dev/null; then
  python3 "$here/icon.py" "$res/applet.icns"
  # osacompile also writes an asset catalogue, which outranks applet.icns
  rm -f "$res/Assets.car"
  /usr/libexec/PlistBuddy -c "Delete :CFBundleIconName" "$plist" 2>/dev/null || true
else
  echo "Pillow is not installed (pip3 install pillow); keeping the default icon" >&2
fi

/usr/libexec/PlistBuddy -c "Set :CFBundleIdentifier local.csessions.app" "$plist" 2>/dev/null ||
  /usr/libexec/PlistBuddy -c "Add :CFBundleIdentifier string local.csessions.app" "$plist"

codesign --force --deep --sign - "$app"
touch "$app"   # prompts Finder and the Dock to reread the icon

echo "built $app"
echo "open it once from Finder; macOS asks once for permission to control iTerm"
