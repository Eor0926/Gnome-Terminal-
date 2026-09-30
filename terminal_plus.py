#!/usr/bin/env python3

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Vte", "2.91")

from gi.repository import Gtk, Gdk, Gio, GLib, Vte

import json
import os
import shlex
import signal
import sys
from pathlib import Path


APP_NAME = "Terminal+"

# Copy All: above this size, save to a Desktop .txt file instead of
# filling the clipboard. 300,000 characters is intentionally conservative
# for pasting large terminal logs into chat/model input boxes.
COPY_TO_FILE_CHAR_LIMIT = 300_000

CONFIG_DIR = Path(GLib.get_user_config_dir()) / "terminal-plus"
SETTINGS_FILE = CONFIG_DIR / "settings.json"

DEFAULT_BACKGROUND = "#202124"
DEFAULT_FOREGROUND = "#F1F1F1"


def parse_launch_args(argv):
    """Parse the small GNOME/Cinnamon-compatible argument subset we support."""
    cwd = None
    command = None
    title = None

    i = 1
    while i < len(argv):
        arg = argv[i]

        if arg in ("-x", "--execute"):
            command = argv[i + 1:]
            break

        if arg == "--":
            command = argv[i + 1:]
            break

        if arg in ("--working-directory",):
            if i + 1 < len(argv):
                cwd = argv[i + 1]
                i += 2
                continue

        if arg.startswith("--working-directory="):
            cwd = arg.split("=", 1)[1]
            i += 1
            continue

        if arg in ("--title",):
            if i + 1 < len(argv):
                title = argv[i + 1]
                i += 2
                continue

        if arg.startswith("--title="):
            title = arg.split("=", 1)[1]
            i += 1
            continue

        # Compatibility with terminal launchers that use: -e "command ..."
        if arg in ("-e", "--command"):
            if i + 1 < len(argv):
                command = shlex.split(argv[i + 1])
            break

        # Ignore common terminal-emulator options that do not affect the
        # command we need to execute.
        if arg in ("--disable-factory", "--wait"):
            i += 1
            continue

        i += 1

    return cwd, command, title


class TerminalPlus(Gtk.Window):
    def __init__(self, initial_cwd=None, initial_command=None, initial_title=None):
        super().__init__()

        self.shell_pid = None
        self.resetting = False
        self.reset_cwd = initial_cwd or str(Path.home())
        self.initial_command = initial_command

        # Color is intentionally per-window only and is never written to disk.
        self.terminal_background = self.rgba_from_hex(DEFAULT_BACKGROUND)
        self.terminal_foreground = self.rgba_from_hex(DEFAULT_FOREGROUND)

        # Command buttons are shared/persistent across Terminal+ windows.
        self.command_buttons = []
        self.settings_monitor = None
        self.settings_reload_source = None
        self.load_shared_settings()

        # Per-window name only. Reset preserves it because Reset keeps this
        # window alive. Closing the window discards it.
        self.custom_name = initial_title or APP_NAME

        self.set_title(self.custom_name)
        self.set_default_size(900, 560)

        # Helps Cinnamon associate the window with terminal-plus.desktop on X11.
        try:
            self.set_wmclass("terminal-plus", "TerminalPlus")
        except Exception:
            pass

        # Terminal+ windows stay above normal windows by default.
        self.set_keep_above(True)

        self.connect("destroy", Gtk.main_quit)

        self.build_header()
        self.build_terminal()
        self.start_settings_monitor()

        self.terminal.connect(
            "key-press-event",
            self.on_terminal_key_press
        )

        self.apply_css()

        self.show_all()

        if self.initial_command:
            self.spawn_process(self.initial_command, self.reset_cwd)
        else:
            self.spawn_shell(self.reset_cwd)

    # ---------------------------------------------------------
    # Header
    # ---------------------------------------------------------

    def build_header(self):
        self.header = Gtk.HeaderBar()
        self.header.set_size_request(-1, 26)
        self.header.set_show_close_button(True)
        self.header.set_has_subtitle(False)
        self.set_titlebar(self.header)

        self.reset_button = Gtk.Button()
        self.reset_button.set_size_request(28, 22)
        self.reset_button.set_tooltip_text(
            "Stop the current terminal session and start a fresh one"
        )
        self.reset_button.add(
            Gtk.Image.new_from_icon_name(
                "view-refresh-symbolic",
                Gtk.IconSize.BUTTON
            )
        )
        self.reset_button.connect("clicked", self.on_reset_clicked)
        self.header.pack_start(self.reset_button)

        self.copy_button = Gtk.Button()
        self.copy_button.set_size_request(28, 22)
        self.copy_button.set_tooltip_text(
            "Copy the entire terminal contents and scrollback"
        )
        self.copy_button.add(
            Gtk.Image.new_from_icon_name(
                "edit-copy-symbolic",
                Gtk.IconSize.BUTTON
            )
        )
        self.copy_button.connect("clicked", self.on_copy_all_clicked)
        self.header.pack_start(self.copy_button)

        # Persistent custom command buttons appear immediately to the right
        # of Reset and Copy All.
        self.command_button_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=0
        )
        self.header.pack_start(self.command_button_box)
        self.rebuild_command_buttons()

        self.title_stack = Gtk.Stack()
        self.title_stack.set_size_request(-1, 22)
        self.title_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.title_stack.set_transition_duration(100)

        self.title_button = Gtk.Button(label=self.custom_name)
        self.title_button.set_name("editable-title")
        self.title_button.set_tooltip_text("Click to rename this terminal")
        self.title_button.connect("clicked", self.begin_title_edit)

        self.title_entry = Gtk.Entry()
        self.title_entry.set_name("title-entry")
        self.title_entry.set_text(self.custom_name)
        self.title_entry.set_alignment(0.5)
        self.title_entry.connect("activate", self.finish_title_edit)
        self.title_entry.connect("focus-out-event", self.finish_title_edit_focus)
        self.title_entry.connect("key-press-event", self.title_entry_key)

        self.title_stack.add_named(self.title_button, "display")
        self.title_stack.add_named(self.title_entry, "edit")
        self.title_stack.set_visible_child_name("display")

        self.header.set_custom_title(self.title_stack)

    def begin_title_edit(self, _button):
        self.title_entry.set_text(self.custom_name)
        self.title_stack.set_visible_child_name("edit")
        self.title_entry.grab_focus()
        self.title_entry.select_region(0, -1)

    def finish_title_edit(self, entry):
        name = entry.get_text().strip()
        if name:
            self.custom_name = name

        self.title_button.set_label(self.custom_name)
        self.set_title(self.custom_name)
        self.title_stack.set_visible_child_name("display")
        self.terminal.grab_focus()

    def finish_title_edit_focus(self, entry, _event):
        self.finish_title_edit(entry)
        return False

    def title_entry_key(self, entry, event):
        if event.keyval == Gdk.KEY_Escape:
            entry.set_text(self.custom_name)
            self.title_stack.set_visible_child_name("display")
            self.terminal.grab_focus()
            return True
        return False

    # ---------------------------------------------------------
    # Terminal
    # ---------------------------------------------------------

    def build_terminal(self):
        self.terminal = Vte.Terminal()

        self.terminal.set_scrollback_lines(100000)
        self.terminal.set_scroll_on_output(False)
        self.terminal.set_scroll_on_keystroke(True)
        self.terminal.set_mouse_autohide(True)
        self.terminal.set_cursor_shape(Vte.CursorShape.BLOCK)

        self.apply_terminal_colors()

        self.terminal.connect("child-exited", self.on_child_exited)
        self.terminal.connect(
            "button-press-event",
            self.on_terminal_button_press
        )

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.add(self.terminal)

        self.add(scroller)

    def spawn_process(self, argv, cwd=None):
        if not argv:
            self.spawn_shell(cwd)
            return

        if not cwd or not os.path.isdir(cwd):
            cwd = str(Path.home())

        try:
            result, pid = self.terminal.spawn_sync(
                Vte.PtyFlags.DEFAULT,
                cwd,
                argv,
                None,
                GLib.SpawnFlags.DEFAULT,
                None,
                None,
                None
            )

            if result:
                self.shell_pid = pid
                self.terminal.grab_focus()
            else:
                self.shell_pid = None

        except Exception as exc:
            self.shell_pid = None
            print("Failed to start process:", exc)

    def spawn_shell(self, cwd=None):
        shell = os.environ.get("SHELL", "/bin/bash")
        self.spawn_process([shell], cwd)

    # ---------------------------------------------------------
    # Shared settings / command buttons
    # ---------------------------------------------------------

    @staticmethod
    def rgba_from_hex(value):
        rgba = Gdk.RGBA()
        if not rgba.parse(value):
            rgba.parse(DEFAULT_BACKGROUND)
        return rgba

    def load_shared_settings(self):
        self.command_buttons = []

        try:
            if not SETTINGS_FILE.exists():
                return

            data = json.loads(
                SETTINGS_FILE.read_text(encoding="utf-8")
            )

            raw_buttons = data.get("command_buttons", [])
            if not isinstance(raw_buttons, list):
                return

            cleaned = []

            for item in raw_buttons:
                if not isinstance(item, dict):
                    continue

                command = str(item.get("command", "")).strip()
                label = str(item.get("label", "")).strip()

                if not command:
                    continue

                if not label:
                    label = self.default_button_label(command)

                cleaned.append({"label": label[:32], "command": command})

            self.command_buttons = cleaned

        except Exception as exc:
            print("Could not load Terminal+ settings:", exc)

    def save_shared_settings(self):
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            try:
                CONFIG_DIR.chmod(0o700)
            except OSError:
                pass

            payload = {"command_buttons": self.command_buttons}

            temp_file = SETTINGS_FILE.with_suffix(".json.tmp")
            temp_file.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
            try:
                temp_file.chmod(0o600)
            except OSError:
                pass
            temp_file.replace(SETTINGS_FILE)

        except Exception as exc:
            print("Could not save Terminal+ settings:", exc)

    def start_settings_monitor(self):
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            config_dir_file = Gio.File.new_for_path(str(CONFIG_DIR))
            self.settings_monitor = config_dir_file.monitor_directory(
                Gio.FileMonitorFlags.NONE,
                None
            )
            self.settings_monitor.connect(
                "changed",
                self.on_settings_directory_changed
            )
        except Exception as exc:
            print("Could not monitor Terminal+ settings:", exc)

    def on_settings_directory_changed(self, _monitor, file_obj, other_file, _event_type):
        changed_names = set()

        for candidate in (file_obj, other_file):
            try:
                candidate_path = candidate.get_path() if candidate else None
            except Exception:
                candidate_path = None

            if candidate_path:
                changed_names.add(Path(candidate_path).name)

        if SETTINGS_FILE.name not in changed_names:
            return

        if self.settings_reload_source is not None:
            GLib.source_remove(self.settings_reload_source)

        self.settings_reload_source = GLib.timeout_add(
            150,
            self.reload_shared_settings
        )

    def reload_shared_settings(self):
        self.settings_reload_source = None
        self.load_shared_settings()
        if hasattr(self, "command_button_box"):
            self.rebuild_command_buttons()
        return False

    @staticmethod
    def default_button_label(command):
        collapsed = " ".join(command.split())
        if not collapsed:
            return "Command"
        if len(collapsed) <= 24:
            return collapsed
        return collapsed[:21] + "..."

    def rebuild_command_buttons(self):
        if not hasattr(self, "command_button_box"):
            return

        for child in self.command_button_box.get_children():
            self.command_button_box.remove(child)
            child.destroy()

        for item in self.command_buttons:
            label = item.get("label", "Command")
            command = item.get("command", "")

            button = Gtk.Button(label=label)
            button.set_size_request(-1, 22)
            button.set_tooltip_text(
                f"{command}\nRight-click this button to remove it"
            )
            button.connect("clicked", self.on_command_button_clicked, command)
            button.connect(
                "button-press-event",
                self.on_command_button_press,
                label,
                command
            )
            self.command_button_box.pack_start(button, False, False, 0)

        self.command_button_box.show_all()

    def on_command_button_clicked(self, _button, command):
        if not command:
            return
        try:
            self.terminal.feed_child((command + "\n").encode("utf-8"))
            self.terminal.grab_focus()
        except Exception as exc:
            print("Could not run command button:", exc)

    def on_command_button_press(self, _button, event, label, command):
        if event.button != 3:
            return False

        menu = Gtk.Menu()
        remove_item = Gtk.MenuItem(label="Remove Command Button")
        remove_item.connect(
            "activate",
            self.remove_command_button,
            label,
            command
        )
        menu.append(remove_item)
        menu.show_all()
        menu.popup_at_pointer(event)
        return True

    def remove_command_button(self, _menu_item, label, command):
        # Refresh from disk first so an older open window does not overwrite
        # command buttons that were added from another Terminal+ window.
        self.load_shared_settings()

        for index, item in enumerate(self.command_buttons):
            if (
                item.get("label") == label
                and item.get("command") == command
            ):
                del self.command_buttons[index]
                self.save_shared_settings()
                self.rebuild_command_buttons()
                return

    def add_command_button_dialog(self, _menu_item=None):
        dialog = Gtk.Dialog(
            title="Add Command Button",
            transient_for=self,
            modal=True
        )
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("Add", Gtk.ResponseType.OK)
        dialog.set_default_response(Gtk.ResponseType.OK)

        content = dialog.get_content_area()
        content.set_spacing(8)
        content.set_border_width(12)

        grid = Gtk.Grid()
        grid.set_row_spacing(8)
        grid.set_column_spacing(10)

        label_label = Gtk.Label(label="Button label:")
        label_label.set_halign(Gtk.Align.START)
        label_entry = Gtk.Entry()
        label_entry.set_placeholder_text("Optional — command text is used if blank")

        command_label = Gtk.Label(label="Command:")
        command_label.set_halign(Gtk.Align.START)
        command_entry = Gtk.Entry()
        command_entry.set_placeholder_text("Example: sudo apt update")
        command_entry.set_activates_default(True)
        command_entry.set_width_chars(50)

        grid.attach(label_label, 0, 0, 1, 1)
        grid.attach(label_entry, 1, 0, 1, 1)
        grid.attach(command_label, 0, 1, 1, 1)
        grid.attach(command_entry, 1, 1, 1, 1)
        content.add(grid)
        dialog.show_all()

        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            command = command_entry.get_text().strip()
            label = label_entry.get_text().strip()
            if command:
                if not label:
                    label = self.default_button_label(command)

                # Pull in changes made by other open Terminal+ windows before
                # appending this new shared button.
                self.load_shared_settings()
                self.command_buttons.append(
                    {"label": label[:32], "command": command}
                )
                self.save_shared_settings()
                self.rebuild_command_buttons()

        dialog.destroy()
        self.terminal.grab_focus()

    # ---------------------------------------------------------
    # Per-window terminal color
    # ---------------------------------------------------------

    def apply_terminal_colors(self):
        self.terminal.set_color_background(self.terminal_background)
        self.terminal.set_color_foreground(self.terminal_foreground)

    def update_foreground_for_background(self):
        bg = self.terminal_background
        luminance = 0.2126 * bg.red + 0.7152 * bg.green + 0.0722 * bg.blue
        if luminance > 0.58:
            self.terminal_foreground = self.rgba_from_hex("#101010")
        else:
            self.terminal_foreground = self.rgba_from_hex(DEFAULT_FOREGROUND)

    def choose_terminal_color(self, _menu_item=None):
        dialog = Gtk.ColorChooserDialog(title="Terminal Color", parent=self)
        dialog.set_rgba(self.terminal_background)
        dialog.set_use_alpha(False)
        response = dialog.run()

        if response == Gtk.ResponseType.OK:
            self.terminal_background = dialog.get_rgba()
            self.terminal_background.alpha = 1.0
            self.update_foreground_for_background()
            self.apply_terminal_colors()

        dialog.destroy()
        self.terminal.grab_focus()

    def reset_terminal_color(self, _menu_item=None):
        self.terminal_background = self.rgba_from_hex(DEFAULT_BACKGROUND)
        self.terminal_foreground = self.rgba_from_hex(DEFAULT_FOREGROUND)
        self.apply_terminal_colors()
        self.terminal.grab_focus()

    # ---------------------------------------------------------
    # Terminal right-click menu
    # ---------------------------------------------------------

    def on_terminal_button_press(self, _terminal, event):
        if event.button != 3:
            return False

        menu = Gtk.Menu()

        color_item = Gtk.MenuItem(label="Change Terminal Color...")
        color_item.connect("activate", self.choose_terminal_color)
        menu.append(color_item)

        reset_color_item = Gtk.MenuItem(label="Reset Terminal Color")
        reset_color_item.connect("activate", self.reset_terminal_color)
        menu.append(reset_color_item)

        menu.append(Gtk.SeparatorMenuItem())

        add_command_item = Gtk.MenuItem(label="Add Command Button...")
        add_command_item.connect("activate", self.add_command_button_dialog)
        menu.append(add_command_item)

        if self.command_buttons:
            remove_menu = Gtk.Menu()
            remove_parent = Gtk.MenuItem(label="Remove Command Button")

            for item in self.command_buttons:
                label = item.get("label", "Command")
                command = item.get("command", "")
                remove_item = Gtk.MenuItem(label=label)
                remove_item.connect(
                    "activate",
                    self.remove_command_button,
                    label,
                    command
                )
                remove_menu.append(remove_item)

            remove_parent.set_submenu(remove_menu)
            menu.append(remove_parent)

        menu.show_all()
        menu.popup_at_pointer(event)
        return True

    # ---------------------------------------------------------
    # Process tree handling
    # ---------------------------------------------------------

    def get_process_table(self):
        table = {}

        for item in Path("/proc").iterdir():
            if not item.name.isdigit():
                continue

            try:
                pid = int(item.name)
                parent_pid = None

                with open(
                    item / "status",
                    "r",
                    encoding="utf-8",
                    errors="replace"
                ) as f:
                    for line in f:
                        if line.startswith("PPid:"):
                            parent_pid = int(line.split()[1])
                            break

                if parent_pid is not None:
                    table[pid] = parent_pid
            except Exception:
                continue

        return table

    def descendants_of(self, root_pid):
        table = self.get_process_table()
        descendants = []
        frontier = [root_pid]

        while frontier:
            parent = frontier.pop()
            children = [
                pid
                for pid, ppid in table.items()
                if ppid == parent
            ]
            descendants.extend(children)
            frontier.extend(children)

        return descendants

    def signal_processes(self, pids, sig):
        for pid in reversed(pids):
            try:
                os.kill(pid, sig)
            except (ProcessLookupError, PermissionError):
                pass
            except Exception:
                pass

    # ---------------------------------------------------------
    # Reset
    # ---------------------------------------------------------

    def on_reset_clicked(self, _button):
        if self.resetting:
            return

        if not self.shell_pid:
            self.terminal.reset(True, True)
            self.spawn_shell(str(Path.home()))
            return

        self.resetting = True
        self.reset_button.set_sensitive(False)

        try:
            self.reset_cwd = os.readlink(f"/proc/{self.shell_pid}/cwd")
        except Exception:
            self.reset_cwd = str(Path.home())

        descendants = self.descendants_of(self.shell_pid)
        self.signal_processes(descendants, signal.SIGTERM)

        try:
            os.kill(self.shell_pid, signal.SIGTERM)
        except Exception:
            pass

        GLib.timeout_add(400, self.force_reset_kill)

    def force_reset_kill(self):
        if not self.resetting:
            return False

        if self.shell_pid:
            descendants = self.descendants_of(self.shell_pid)
            self.signal_processes(descendants, signal.SIGKILL)

            try:
                os.kill(self.shell_pid, signal.SIGKILL)
            except Exception:
                pass

        return False

    def on_child_exited(self, _terminal, _status):
        self.shell_pid = None

        if self.resetting:
            self.terminal.reset(True, True)
            GLib.idle_add(self.finish_reset)
        else:
            self.destroy()

    def finish_reset(self):
        # Reset always creates a fresh shell rather than rerunning a command
        # that may have been supplied by a Terminal=true desktop launcher.
        self.initial_command = None
        self.spawn_shell(self.reset_cwd)
        self.resetting = False
        self.reset_button.set_sensitive(True)
        return False

    # ---------------------------------------------------------
    # Copy All
    # ---------------------------------------------------------

    def on_copy_all_clicked(self, _button):
        try:
            stream = Gio.MemoryOutputStream.new_resizable()

            self.terminal.write_contents_sync(
                stream,
                Vte.WriteFlags.DEFAULT,
                None
            )

            stream.close(None)

            data = stream.steal_as_bytes().get_data()

            if isinstance(data, tuple):
                data = data[0]
            if isinstance(data, memoryview):
                data = data.tobytes()
            if not isinstance(data, bytes):
                data = bytes(data)

            text = data.decode("utf-8", errors="replace")
            clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)

            # Large terminal histories are more useful as a text file than as
            # an enormous clipboard payload. The clipboard is cleared only
            # after the file has been written successfully.
            if len(text) > COPY_TO_FILE_CHAR_LIMIT:
                desktop = GLib.get_user_special_dir(
                    GLib.UserDirectory.DIRECTORY_DESKTOP
                )

                if not desktop:
                    desktop = str(Path.home() / "Desktop")

                desktop_path = Path(desktop)
                desktop_path.mkdir(parents=True, exist_ok=True)

                safe_title = "".join(
                    ch if ch.isalnum() or ch in ("-", "_") else "_"
                    for ch in self.custom_name
                ).strip("_")

                if not safe_title:
                    safe_title = "Terminal"

                # Keep the generated filename comfortably below common
                # filesystem filename-length limits.
                safe_title = safe_title[:80]

                timestamp = GLib.DateTime.new_now_local().format(
                    "%Y-%m-%d_%H-%M-%S"
                )

                file_path = desktop_path / (
                    f"TerminalPlus_{safe_title}_{timestamp}.txt"
                )

                # Avoid replacing an existing file if the button is clicked
                # more than once in the same second.
                suffix = 2
                while file_path.exists():
                    file_path = desktop_path / (
                        f"TerminalPlus_{safe_title}_{timestamp}_{suffix}.txt"
                    )
                    suffix += 1

                file_path.write_text(
                    text,
                    encoding="utf-8"
                )

                # Replace the clipboard with an explicitly empty value.
                # Gtk.Clipboard.clear() is intended mainly for cases where
                # this application already owns the clipboard, so setting and
                # storing an empty string is more deterministic here.
                clipboard.set_text("", -1)
                clipboard.store()

                self.copy_button.set_tooltip_text(
                    f"Saved {len(text):,} characters to "
                    f"{file_path.name}; clipboard cleared"
                )

                GLib.timeout_add(
                    3500,
                    self.restore_copy_tooltip
                )

                print(
                    f"Copy All: terminal contents were too large for the "
                    f"clipboard ({len(text):,} characters). "
                    f"Saved to: {file_path}"
                )

                return

            clipboard.set_text(text, -1)
            clipboard.store()

            self.copy_button.set_tooltip_text(
                f"Copied {len(text):,} characters to clipboard"
            )

            GLib.timeout_add(
                1500,
                self.restore_copy_tooltip
            )

        except Exception as exc:
            self.copy_button.set_tooltip_text(
                f"Copy All failed: {exc}"
            )
            GLib.timeout_add(
                3500,
                self.restore_copy_tooltip
            )
            print("Copy All failed:", exc)

    def restore_copy_tooltip(self):
        self.copy_button.set_tooltip_text(
            "Copy the entire terminal contents and scrollback"
        )
        return False

    # ---------------------------------------------------------
    # Keyboard shortcuts
    # ---------------------------------------------------------

    def on_terminal_key_press(self, _widget, event):
        state = event.state

        ctrl = bool(state & Gdk.ModifierType.CONTROL_MASK)
        shift = bool(state & Gdk.ModifierType.SHIFT_MASK)
        key = event.keyval

        # Ctrl+C = copy selected text.
        if ctrl and not shift and key in (Gdk.KEY_c, Gdk.KEY_C):
            if self.terminal.get_has_selection():
                self.terminal.copy_clipboard_format(Vte.Format.TEXT)
            return True

        # Ctrl+V = paste.
        if ctrl and not shift and key in (Gdk.KEY_v, Gdk.KEY_V):
            self.terminal.paste_clipboard()
            return True

        # Ctrl+Shift+C = normal terminal Ctrl+C / interrupt.
        if ctrl and shift and key in (Gdk.KEY_c, Gdk.KEY_C):
            self.terminal.feed_child(b"\x03")
            return True

        # Ctrl+Shift+V = normal terminal Ctrl+V / quoted insert.
        if ctrl and shift and key in (Gdk.KEY_v, Gdk.KEY_V):
            self.terminal.feed_child(b"\x16")
            return True

        # Shift+Insert = paste.
        if shift and not ctrl and key == Gdk.KEY_Insert:
            self.terminal.paste_clipboard()
            return True

        return False

    # ---------------------------------------------------------
    # Styling
    # ---------------------------------------------------------

    def apply_css(self):
        css = b"""
        headerbar,
        headerbar.titlebar {
            min-height: 0px;
            padding: 0px;
            margin: 0px;
            border-width: 0px;
        }

        headerbar box {
            min-height: 0px;
            padding-top: 0px;
            padding-bottom: 0px;
            margin-top: 0px;
            margin-bottom: 0px;
        }

        headerbar button,
        headerbar button.titlebutton {
            min-height: 18px;
            min-width: 24px;
            padding: 0px 4px;
            margin: 1px;
            border-width: 0px;
        }

        headerbar button image {
            min-height: 14px;
            min-width: 14px;
            padding: 0px;
            margin: 0px;
        }

        #editable-title {
            background: transparent;
            border: none;
            box-shadow: none;
            min-height: 18px;
            padding: 0px 10px;
            margin: 0px;
        }

        #editable-title:hover {
            background: rgba(255,255,255,0.08);
        }

        #title-entry {
            min-width: 200px;
            min-height: 20px;
            padding-top: 0px;
            padding-bottom: 0px;
            margin: 1px 0px;
        }
        """

        provider = Gtk.CssProvider()
        provider.load_from_data(css)

        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )


if __name__ == "__main__":
    GLib.set_application_name(APP_NAME)
    Gtk.Window.set_default_icon_name("utilities-terminal")

    launch_cwd, launch_command, launch_title = parse_launch_args(sys.argv)

    window = TerminalPlus(
        initial_cwd=launch_cwd,
        initial_command=launch_command,
        initial_title=launch_title
    )
    Gtk.main()
