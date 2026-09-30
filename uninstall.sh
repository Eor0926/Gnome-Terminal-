#!/usr/bin/env bash
set -euo pipefail

APP_DIR="$HOME/.local/share/terminal-plus"
BIN="$HOME/.local/bin/terminal-plus"
DESKTOP_DIR="$HOME/.local/share/applications"
STATE="$APP_DIR/install-state"

echo "Uninstalling Terminal+..."

# Restore the terminal setting that existed before the first install, but only
# if Terminal+ is still the selected default.
if [[ -f "$STATE" ]] && command -v gsettings >/dev/null 2>&1; then
    if gsettings list-schemas | grep -qx 'org.cinnamon.desktop.default-applications.terminal'; then
        # shellcheck disable=SC1090
        source "$STATE"

        CURRENT_EXEC="$(gsettings get org.cinnamon.desktop.default-applications.terminal exec 2>/dev/null || true)"
        EXPECTED_EXEC="'$BIN'"

        if [[ "$CURRENT_EXEC" == "$EXPECTED_EXEC" ]]; then
            if [[ -n "${PREV_EXEC:-}" ]]; then
                gsettings set org.cinnamon.desktop.default-applications.terminal exec "$PREV_EXEC"
            else
                gsettings set org.cinnamon.desktop.default-applications.terminal exec 'gnome-terminal'
            fi

            if [[ -n "${PREV_EXEC_ARG:-}" ]]; then
                gsettings set org.cinnamon.desktop.default-applications.terminal exec-arg "$PREV_EXEC_ARG"
            else
                gsettings set org.cinnamon.desktop.default-applications.terminal exec-arg '-x'
            fi

            echo "Restored the previous Cinnamon terminal preference."
        else
            echo "Cinnamon's terminal preference was changed after installation; leaving it untouched."
        fi
    fi
fi

rm -f "$BIN"
rm -f "$DESKTOP_DIR/terminal-plus.desktop"
rm -f "$DESKTOP_DIR/terminal-plus-uninstall.desktop"
rm -f "$DESKTOP_DIR/gnome-terminal-fallback.desktop"
rm -rf "$APP_DIR"
rm -rf "$HOME/.config/terminal-plus"

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true
fi

echo
echo "Terminal+ uninstalled."
