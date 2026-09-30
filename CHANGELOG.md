# Changelog

## 1.2.2

- Tightened permissions on existing command-button settings during upgrades, not only after the next settings save.
- Made command-button removal target the matching label and command instead of a potentially stale menu index.


## 1.2.1

- Fixed the portable graphical Install/Uninstall `.desktop` launchers so they validate correctly and locate their sibling scripts without hard-coded user paths.
- Made the installed graphical uninstaller independent of Terminal+ being functional as the current default terminal.
- Removed the redundant `DO_NOT_REAP_CHILD` spawn flag that caused a VTE runtime warning; VTE adds it internally for `spawn_sync`.
- Hardened persistent command-button settings permissions.
- Improved synchronization between multiple already-open Terminal+ windows and reduced stale shared-button overwrites.


## 1.2.0

- Added a terminal right-click context menu.
- Added per-window terminal background color selection; color is not persisted.
- Added automatic light/dark text contrast after choosing a background color.
- Added persistent custom command buttons after Reset and Copy All.
- Added optional command-button labels and one-click command execution.
- Command buttons are shared through `~/.config/terminal-plus/settings.json`.
- Already-open Terminal+ windows monitor the shared settings and refresh their command buttons.
- Added command-button removal from the terminal context menu and by right-clicking a command button.
- Command-button labels are capped at 32 characters to keep the compact title bar usable.
- Uninstall now removes the shared Terminal+ command-button settings.


## 1.1.2

- Improved `.run` installer/uninstaller fallbacks so a graphical double-click opens a terminal window when needed.
- Re-ran packaged install/uninstall simulation using a clean temporary HOME.


## 1.1.1

- Fixed executable permissions in the release ZIP.
- Reworked portable `.desktop` installer/uninstaller launch commands to use Desktop Entry-compatible quoting.
- Added `.run` installer/uninstaller fallbacks.
- Large Copy All output now clears the clipboard by storing an explicit empty clipboard value after the `.txt` file is written.
- Large-log filenames now truncate custom terminal titles to avoid filename-length failures.
- Copy All failures now show in the button tooltip as well as stdout.


## 1.1.0

- Changed Copy All handling for very large terminal histories.
- Histories of 300,000 characters or fewer are copied to the clipboard.
- Histories over 300,000 characters are written to a timestamped `.txt` file on the user's Desktop.
- The clipboard is cleared after a large-history file is written successfully.
- Large files use the current per-window terminal name in the filename when possible.
- Removed accidental Python `__pycache__` build artifacts from the release ZIP.

## 1.0.1

- Added Cinnamon/default-terminal command execution compatibility.
- Added persistent graphical uninstaller.
- Added GNOME Terminal fallback launcher.
