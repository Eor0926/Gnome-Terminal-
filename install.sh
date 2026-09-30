#!/usr/bin/env bash
set -euo pipefail

APP_NAME="Terminal+"
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$HOME/.local/share/terminal-plus"
BIN_DIR="$HOME/.local/bin"
DESKTOP_DIR="$HOME/.local/share/applications"
BIN="$BIN_DIR/terminal-plus"
STATE="$APP_DIR/install-state"
CONFIG_DIR="$HOME/.config/terminal-plus"
SETTINGS_FILE="$CONFIG_DIR/settings.json"

echo "Installing $APP_NAME..."

if command -v apt-get >/dev/null 2>&1 && command -v dpkg-query >/dev/null 2>&1; then
    REQUIRED=(
        python3
        python3-gi
        gir1.2-gtk-3.0
        gir1.2-vte-2.91
    )

    MISSING=()
    for pkg in "${REQUIRED[@]}"; do
        if ! dpkg-query -W -f='${Status}' "$pkg" 2>/dev/null | grep -q "install ok installed"; then
            MISSING+=("$pkg")
        fi
    done

    if ((${#MISSING[@]})); then
        echo
        echo "Installing required packages:"
        printf '  %s\n' "${MISSING[@]}"
        sudo apt-get update
        sudo apt-get install -y "${MISSING[@]}"
    fi
else
    echo "Warning: automatic dependency installation is only configured for apt-based systems."
    echo "Required: Python 3, PyGObject/GTK3 bindings, and VTE 2.91 introspection bindings."
fi

mkdir -p "$APP_DIR" "$BIN_DIR" "$DESKTOP_DIR"

# Tighten permissions for command-button settings created by older releases.
if [[ -d "$CONFIG_DIR" ]]; then
    chmod 0700 "$CONFIG_DIR" 2>/dev/null || true
fi
if [[ -f "$SETTINGS_FILE" ]]; then
    chmod 0600 "$SETTINGS_FILE" 2>/dev/null || true
fi

# Preserve the pre-install Cinnamon terminal choice. Reinstalls do not replace
# this original backup.
if [[ ! -f "$STATE" ]] && command -v gsettings >/dev/null 2>&1; then
    if gsettings list-schemas | grep -qx 'org.cinnamon.desktop.default-applications.terminal'; then
        {
            printf 'PREV_EXEC=%q\n' "$(gsettings get org.cinnamon.desktop.default-applications.terminal exec 2>/dev/null || true)"
            printf 'PREV_EXEC_ARG=%q\n' "$(gsettings get org.cinnamon.desktop.default-applications.terminal exec-arg 2>/dev/null || true)"
        } > "$STATE"
    fi
fi

install -m 0755 "$HERE/terminal_plus.py" "$APP_DIR/terminal_plus.py"
install -m 0755 "$HERE/uninstall.sh" "$APP_DIR/uninstall.sh"

cat > "$BIN" <<EOF
#!/usr/bin/env bash
exec python3 "$APP_DIR/terminal_plus.py" "\$@"
EOF
chmod 0755 "$BIN"

cat > "$DESKTOP_DIR/terminal-plus.desktop" <<EOF
[Desktop Entry]
Name=Terminal+
Comment=Custom GTK/VTE terminal emulator
Exec="$BIN"
TryExec=$BIN
Icon=utilities-terminal
Terminal=false
Type=Application
Categories=System;TerminalEmulator;
StartupNotify=true
StartupWMClass=TerminalPlus
EOF
chmod 0644 "$DESKTOP_DIR/terminal-plus.desktop"

# Keep the original GNOME Terminal visible as a repair fallback.
if command -v gnome-terminal >/dev/null 2>&1; then
    GNOME_TERMINAL="$(command -v gnome-terminal)"
    cat > "$DESKTOP_DIR/gnome-terminal-fallback.desktop" <<EOF
[Desktop Entry]
Name=GNOME Terminal (Fallback)
Comment=Original GNOME Terminal
Exec="$GNOME_TERMINAL"
TryExec=$GNOME_TERMINAL
Icon=utilities-terminal
Terminal=false
Type=Application
Categories=System;TerminalEmulator;
StartupNotify=true
EOF
    chmod 0644 "$DESKTOP_DIR/gnome-terminal-fallback.desktop"
fi

# Install a persistent graphical uninstaller so the extracted ZIP is not
# required later.
cat > "$DESKTOP_DIR/terminal-plus-uninstall.desktop" <<EOF
[Desktop Entry]
Name=Uninstall Terminal+
Comment=Remove Terminal+ and restore the previous terminal preference
Exec=/usr/bin/x-terminal-emulator -e /bin/bash "$APP_DIR/uninstall.sh"
TryExec=/usr/bin/x-terminal-emulator
Icon=edit-delete
Terminal=false
Type=Application
Categories=Utility;
StartupNotify=true
EOF
chmod 0644 "$DESKTOP_DIR/terminal-plus-uninstall.desktop"

# Make Terminal+ Cinnamon's normal terminal. -x lets Cinnamon launch commands
# inside it for Terminal=true desktop applications.
if command -v gsettings >/dev/null 2>&1; then
    if gsettings list-schemas | grep -qx 'org.cinnamon.desktop.default-applications.terminal'; then
        gsettings set org.cinnamon.desktop.default-applications.terminal exec "$BIN"
        gsettings set org.cinnamon.desktop.default-applications.terminal exec-arg '-x'
        echo "Set Terminal+ as Cinnamon's default terminal."
    fi
fi

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true
fi

echo
echo "Terminal+ installed."
echo "Launcher: $BIN"
echo "Menu entry: Terminal+"
echo "Menu uninstaller: Uninstall Terminal+"
if command -v gnome-terminal >/dev/null 2>&1; then
    echo "Fallback entry: GNOME Terminal (Fallback)"
fi
echo
echo "Ctrl+Alt+T should now open Terminal+."

if [[ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]]; then
    nohup "$BIN" >/dev/null 2>&1 &
fi

[executed on device: Eor-Computer (91ab0d1e-cc1b-440e-9d8f-d32b7879a54f)]