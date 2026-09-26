# Changelog

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
