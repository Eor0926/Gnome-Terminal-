# Terminal+ 1.2.2

Terminal+ is a compact GTK3/VTE terminal for Linux Mint/Cinnamon.

## Features

- Compact title bar
- Clickable per-window terminal name
  - New windows start as `Terminal+`
  - A renamed window keeps its name through Reset
  - Closing the window discards the custom name
- Reset button
  - Stops the terminal process and its child processes
  - Clears the terminal
  - Starts a fresh shell in the same window
  - Attempts to preserve the working directory
- Copy All button copies the terminal contents and scrollback
  - Up to 300,000 characters: copied normally to the clipboard
  - Over 300,000 characters: saved automatically as a `.txt` file on the Desktop
  - When a large log is saved to a file, the clipboard is cleared
- Right-click terminal menu
  - **Change Terminal Color...** changes only the current terminal window
  - **Reset Terminal Color** restores the default dark background
  - Bright backgrounds automatically switch to dark text for readability
  - Terminal color is intentionally not persisted
- Persistent command buttons
  - Right-click the terminal and choose **Add Command Button...**
  - Enter any one-line shell command and an optional button label
  - The button appears directly after Reset and Copy All
  - Clicking the button types the command into the terminal and presses Enter
  - Command buttons are shared across Terminal+ windows and future launches
  - Already-open Terminal+ windows refresh when the shared command-button settings change
  - Right-click a command button to remove it
  - Button labels are capped at 32 characters to keep the title bar usable
  - Command buttons are stored in `~/.config/terminal-plus/settings.json`
  - The settings directory/file are written with user-only permissions when Terminal+ saves them
- Always on top by default
- 100,000 lines of scrollback
- Cinnamon/default-terminal command execution support (`-x`, `--execute`, `-e`)
- Shortcuts:
  - `Ctrl+C` = copy selected text
  - `Ctrl+V` = paste
  - `Ctrl+Shift+C` = terminal interrupt / traditional Ctrl+C
  - `Ctrl+Shift+V` = traditional terminal Ctrl+V / quoted insert
  - `Shift+Insert` = paste

## Supported automatic install

The installer targets Linux Mint / Ubuntu / Debian-style systems using `apt`.

Dependencies:

- Python 3
- `python3-gi`
- `gir1.2-gtk-3.0`
- `gir1.2-vte-2.91`

## Install

Extract the ZIP first.

### Graphical

Double-click:

`Install Terminal+.desktop`

Nemo may ask you to trust/run the launcher the first time. Choose **Run** or **Trust and Launch**.

If your file manager refuses to launch the `.desktop` file, run `Install-TerminalPlus.run` instead. When double-clicked outside a terminal, the `.run` launcher opens a terminal window for the installer.

### Terminal

```bash
chmod +x install.sh uninstall.sh
./install.sh
```

The installer:

- Installs missing dependencies when needed
- Installs Terminal+ under `~/.local/share/terminal-plus/`
- Creates `~/.local/bin/terminal-plus`
- Adds **Terminal+** to the Cinnamon application menu
- Makes Terminal+ Cinnamon's default terminal
- Adds **Uninstall Terminal+** to the application menu
- Keeps GNOME Terminal installed
- Adds **GNOME Terminal (Fallback)** when GNOME Terminal is available
- Saves the previous Cinnamon terminal preference so uninstall can restore it

## Uninstall

After installation, search the Cinnamon menu for:

`Uninstall Terminal+`

Or use the `Uninstall Terminal+.desktop` file from this package.

Or run:

```bash
~/.local/share/terminal-plus/uninstall.sh
```

Uninstalling also removes the saved command-button settings in `~/.config/terminal-plus/`.

## Pinning to the panel

Search the Cinnamon menu for **Terminal+**, right-click it, and choose **Add to panel**.

The installer intentionally does not rewrite the user's panel layout automatically.

## Emergency fallback

If Terminal+ is broken, press `Alt+F2` and run:

```text
gnome-terminal --window
```

The installer also adds **GNOME Terminal (Fallback)** to the application menu when GNOME Terminal is installed.

## GitHub

Commit the contents of this directory to the Git repository. Use the ZIP as a GitHub Release download.

```bash
git init
git add .
git commit -m "Initial Terminal+ release"
```
