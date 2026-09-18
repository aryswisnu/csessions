-- Opens a dedicated iTerm window running csessions, sized to half the screen.
-- Login shell so Homebrew's PATH (fzf) is present; pause on error so the window
-- does not vanish before the message can be read.
use framework "AppKit"
use scripting additions

set f to current application's NSScreen's mainScreen()'s frame()
set scrW to (item 1 of item 2 of f) as integer
set scrH to (item 2 of item 2 of f) as integer

tell application "iTerm"
	set win to (create window with default profile command "/bin/bash -lc 'csessions -a || { echo; echo \"[csessions exited $?] press any key\"; read -n 1 -s; }'")
	set bounds of win to {0, 25, (scrW / 2) as integer, scrH}
	activate
end tell
