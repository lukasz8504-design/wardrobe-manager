import tkinter as tk
from tkinter import colorchooser, messagebox
import json
import os
from datetime import datetime
import re
import sys
from threading import Thread
import time
import winsound
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.11+ uses tomllib
    import tomli as tomllib


HISTORY_TIMESTAMP_FORMAT = "%d-%m-%Y %H:%M:%S"
OPERATOR_NUMBER_LENGTH = 4


class TomlConfig:
    """Provide ConfigParser-like access to a parsed TOML configuration."""

    def __init__(self, data):
        self.data = data

    def get(self, section, option, fallback=None):
        return self.data.get(section, {}).get(option, fallback)

    def getint(self, section, option):
        return int(self.data[section][option])


def format_toml_value(value):
    """Return a TOML representation for supported configuration values."""
    if isinstance(value, int):
        return str(value)
    return f'"{str(value).replace("\\", "\\\\").replace("\"", "\\\"")}"'


def calculate_remaining_time(insertion_time, initial_minutes, current_time=None):
    """Return the remaining timer seconds based on the insertion timestamp."""
    current_time = current_time or datetime.now()
    return max(0, initial_minutes * 60 - (current_time - insertion_time).total_seconds())


def is_valid_operator_number(operator_number):
    """Return whether an operator number has the required length."""
    return len(operator_number) == OPERATOR_NUMBER_LENGTH


def calculate_display_font_size(base_size, text_length, available_width, available_height):
    """Fit one display line within the available JIG position dimensions."""
    if available_width <= 0 or available_height <= 0:
        return base_size

    width_limit = max(5, available_width // max(1, int(text_length * 0.65)))
    height_limit = max(5, available_height // 6)
    return max(5, min(base_size, width_limit, height_limit))


def get_contrast_text_color(background_color):
    """Return black or white text that remains readable on a HEX background."""
    red = int(background_color[1:3], 16)
    green = int(background_color[3:5], 16)
    blue = int(background_color[5:7], 16)
    brightness = red * 0.299 + green * 0.587 + blue * 0.114
    return "#000000" if brightness >= 160 else "#FFFFFF"


def parse_history_line(line):
    """Parse a history line into its event data, or return None for old/invalid lines."""
    operator_suffix = r"(?:,\s+Operator\s+#(?P<operator>[^,\r\n]+))?"
    move_pattern = (
        r"^\[(?P<timestamp>[^\]]+)\]\s+JIG\s+#(?P<jig>\d+)\s+~>\s+"
        r"(?:Shelf|Półka)\s+(?P<from_shelf>\d+),\s+(?:Row|Rząd)\s+(?P<from_row>\d+),\s+"
        r"(?:Column|Kolumna)\s+(?P<from_col>\d+),\s+(?:Position|Pozycja)\s+(?P<from_position>\d+)\s+"
        r"->\s+(?:Shelf|Półka)\s+(?P<to_shelf>\d+),\s+(?:Row|Rząd)\s+(?P<to_row>\d+),\s+"
        r"(?:Column|Kolumna)\s+(?P<to_col>\d+),\s+(?:Position|Pozycja)\s+(?P<to_position>\d+)"
        + operator_suffix + r"$"
    )
    pattern = (
        r"^\[(?P<timestamp>[^\]]+)\]\s+JIG\s+#(?P<jig>\d+)\s+"
        r"(?P<action>->|<-)\s+(?:Shelf|Półka)\s+(?P<shelf>\d+),\s+(?:Row|Rząd)\s+(?P<row>\d+),\s+"
        r"(?:Column|Kolumna)\s+(?P<col>\d+),\s+(?:Position|Pozycja)\s+(?P<position>\d+)"
        + operator_suffix + r"$"
    )
    line = line.strip()
    match = re.match(move_pattern, line)
    if match:
        try:
            timestamp = datetime.strptime(match.group("timestamp"), HISTORY_TIMESTAMP_FORMAT)
        except ValueError:
            return None
        return {
            "timestamp": timestamp,
            "jig": int(match.group("jig")),
            "from_position": tuple(
                int(match.group(name)) - 1
                for name in ("from_shelf", "from_row", "from_col", "from_position")
            ),
            "position": tuple(
                int(match.group(name)) - 1
                for name in ("to_shelf", "to_row", "to_col", "to_position")
            ),
            "action": "move",
            "operator": match.group("operator"),
        }

    match = re.match(pattern, line)
    if not match:
        return None
    try:
        timestamp = datetime.strptime(match.group("timestamp"), HISTORY_TIMESTAMP_FORMAT)
    except ValueError:
        return None
    return {
        "timestamp": timestamp,
        "jig": int(match.group("jig")),
        "position": (
            int(match.group("shelf")) - 1,
            int(match.group("row")) - 1,
            int(match.group("col")) - 1,
            int(match.group("position")) - 1,
        ),
        "action": "insert" if match.group("action") == "->" else "remove",
        "operator": match.group("operator"),
    }


class OvenManager:
    def __init__(self, root):
        self.root = root
        self.root.title("Oven Manager")

        self.application_dir = Path(
            sys.executable if getattr(sys, "frozen", False) else __file__
        ).parent

        # Wczytanie konfiguracji
        config_path = self.application_dir / 'config.toml'
        with open(config_path, 'rb') as config_file:
            self.config = TomlConfig(tomllib.load(config_file))
        
        # Parametry pieca
        self.num_shelves = self.config.getint('OVEN', 'num_shelves')
        self.num_rows = self.config.getint('OVEN', 'num_rows')
        self.num_columns = self.config.getint('OVEN', 'num_columns')
        self.jigs_per_section = self.config.getint('OVEN', 'jigs_per_section')
        
        # Parametry timera
        self.initial_time = self.config.getint('TIMER', 'initial_time')
        self.orange_threshold = self.config.getint('TIMER', 'orange_threshold')
        self.red_threshold = self.config.getint('TIMER', 'red_threshold')
        
        # Kolory
        self.normal_bg = self.config.get('COLORS', 'normal_bg')
        self.orange_bg = self.config.get('COLORS', 'orange_bg')
        self.red_bg = self.config.get('COLORS', 'red_bg')
        self.normal_text = self.config.get('COLORS', 'normal_text')
        self.orange_text = self.config.get('COLORS', 'orange_text')
        self.red_text = self.config.get('COLORS', 'red_text')
        self.empty_bg = self.config.get('COLORS', 'empty_bg')
        self.empty_text = self.config.get('COLORS', 'empty_text')
        self.blink_red_bg = self.config.get('COLORS', 'blink_red_bg')
        self.blink_orange_bg = self.config.get('COLORS', 'blink_orange_bg')
        self.blink_text = self.config.get('COLORS', 'blink_text')
        self.app_bg = self.config.get('APPLICATION', 'background_color')
        
        # Wygląd
        self.jig_width = self.config.getint('APPEARANCE', 'jig_width')
        self.jig_height = self.config.getint('APPEARANCE', 'jig_height')
        self.jig_font_size = self.config.getint('APPEARANCE', 'jig_font_size')
        self.jig_number_color = self.config.get('JIG_DISPLAY', 'jig_number_color')
        self.jig_number_font_size = self.config.getint('JIG_DISPLAY', 'jig_number_font_size')
        self.remaining_time_color = self.config.get('JIG_DISPLAY', 'remaining_time_color')
        self.remaining_time_font_size = self.config.getint('JIG_DISPLAY', 'remaining_time_font_size')
        self.processing_text = self.config.get('JIG_DISPLAY', 'processing_text')
        self.processing_text_color = self.config.get('JIG_DISPLAY', 'processing_text_color')
        self.processing_text_font_size = self.config.getint('JIG_DISPLAY', 'processing_text_font_size')
        self.not_removed_text = self.config.get('JIG_DISPLAY', 'not_removed_text')
        self.not_removed_text_color = self.config.get('JIG_DISPLAY', 'not_removed_text_color')
        self.not_removed_text_font_size = self.config.getint(
            'JIG_DISPLAY', 'not_removed_text_font_size'
        )
        self.operator_colors = {
            option.removeprefix('operator_'): color
            for option, color in self.config.data.get('OPERATORS', {}).items()
        }
        self.oven_name = self.config.get('OVEN_TITLE', 'text')
        self.oven_name_color = self.config.get('OVEN_TITLE', 'color')
        self.oven_name_font_size = self.config.getint('OVEN_TITLE', 'font_size')
        self.shelf_names = [
            self.config.get(
                'SHELF_LABELS',
                f'shelf_{shelf_number}',
                fallback=f'SHELF {shelf_number}'
            )
            for shelf_number in range(1, self.num_shelves + 1)
        ]
        self.shelf_label_color = self.config.get('SHELF_LABELS', 'color')
        self.shelf_label_font_size = self.config.getint('SHELF_LABELS', 'font_size')
        self.near_expiry_seconds = self.config.getint('ALERTS', 'near_expiry_seconds')
        self.blink_interval_ms = self.config.getint('ALERTS', 'blink_interval_ms')
        self.empty_sound_file = self.config.get('SOUNDS', 'empty_sound_file')
        self.occupied_sound_file = self.config.get('SOUNDS', 'occupied_sound_file')
        self.expired_sound_file = self.config.get('SOUNDS', 'expired_sound_file')
        self.window_width = self.config.getint('WINDOW', 'width')
        self.window_height = self.config.getint('WINDOW', 'height')
        
        # Pliki
        self.history_file = self.get_data_file_path('history_file')
        self.state_file = self.get_data_file_path('state_file')
        
        self.root.geometry(f'{self.window_width}x{self.window_height}')
        self.root.resizable(True, True)
        self.root.configure(bg=self.app_bg)
        self.window_resize_job = None
        self.root.bind('<Configure>', self.schedule_window_size_save, add='+')
        
        # Stan timera - osobny timer dla każdego JIG
        self.jig_timers = {}  # {pos_key: remaining_time_in_seconds}
        self.jig_insertion_times = {}  # {pos_key: insertion_timestamp}
        self.jig_operator_numbers = {}  # {pos_key: operator_number}
        self.timer_threads = {}  # {pos_key: thread}
        self.expired_jigs = set()
        self.warning_sound_played = set()
        self.blink_expired = False
        self.current_jig = None
        self.current_operator_number = None
        
        # Wczytanie stanu pieca
        self.oven_state = self.load_state()
        self.load_history()
        
        # GUI
        self.setup_ui()
        self.start_all_timers()
        self.schedule_expired_blink()
        
    def setup_ui(self):
        """Tworzenie interfejsu użytkownika"""
        # Główna ramka
        main_frame = tk.Frame(self.root, bg=self.app_bg)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Górna część - Input
        top_frame = tk.Frame(main_frame, bg=self.app_bg)
        top_frame.pack(fill=tk.X, pady=10)
        
        # Input dla numeru JIG
        tk.Label(top_frame, text="JIG number:", bg=self.app_bg, font=('Arial', 12, 'bold')).pack(side=tk.LEFT, padx=5)
        self.jig_entry = tk.Entry(top_frame, width=10, font=('Arial', 12))
        self.jig_entry.pack(side=tk.LEFT, padx=5)
        self.jig_entry.bind('<Return>', self.focus_operator_entry)

        tk.Label(top_frame, text="Operator number:", bg=self.app_bg, font=('Arial', 12, 'bold')).pack(side=tk.LEFT, padx=5)
        validate_operator_number = self.root.register(self.validate_operator_number_length)
        self.operator_entry = tk.Entry(
            top_frame,
            width=4,
            font=('Arial', 12),
            validate='key',
            validatecommand=(validate_operator_number, '%P')
        )
        self.operator_entry.pack(side=tk.LEFT, padx=5)
        self.operator_entry.bind('<Return>', lambda e: self.input_jig())

        tk.Button(top_frame, text="Confirm", command=self.input_jig, font=('Arial', 10)).pack(side=tk.LEFT, padx=5)
        tk.Button(
            top_frame,
            text="Settings",
            command=self.open_settings,
            font=('Arial', 10)
        ).pack(side=tk.LEFT, padx=5)
        tk.Button(
            top_frame,
            text="Clear fields",
            command=self.clear_input_fields,
            font=('Arial', 10)
        ).pack(side=tk.LEFT, padx=5)
        
        # Status
        self.status_label = tk.Label(top_frame, text="Waiting for JIG number...", 
                                     bg='lightyellow', font=('Arial', 10), relief=tk.SUNKEN, bd=1)
        self.status_label.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10)
        
        # Środkowa część - Półki bez scrollbara
        shelves_frame = tk.Frame(main_frame, bg=self.app_bg)
        shelves_frame.pack(fill=tk.BOTH, expand=True)
        shelves_frame.columnconfigure(0, weight=1)

        tk.Label(
            shelves_frame,
            text=self.oven_name,
            bg=self.app_bg,
            fg=self.oven_name_color,
            font=('Arial', self.oven_name_font_size, 'bold')
        ).grid(row=0, column=0, pady=(0, 10), sticky='ew')

        self.shelf_buttons = {}
        
        for shelf_idx in range(self.num_shelves):
            shelf_grid_row = shelf_idx * 2 + 1
            shelves_frame.rowconfigure(shelf_grid_row + 1, weight=1)
            shelf_label = tk.Label(
                shelves_frame,
                text=self.shelf_names[shelf_idx],
                bg=self.app_bg,
                fg=self.shelf_label_color,
                font=('Arial', self.shelf_label_font_size, 'bold')
            )
            shelf_label.grid(
                row=shelf_grid_row,
                column=0,
                pady=(5, 0),
                sticky='ew'
            )
            
            shelf_frame = tk.Frame(shelves_frame, bg='lightgray', relief=tk.RAISED, bd=2)
            shelf_frame.columnconfigure(0, weight=1)
            shelf_frame.grid(
                row=shelf_grid_row + 1,
                column=0,
                sticky='nsew',
                padx=10,
                pady=(0, 5)
            )
            
            for row_idx in range(self.num_rows):
                shelf_frame.rowconfigure(row_idx, weight=1)
                row_frame = tk.Frame(shelf_frame, bg='lightgray')
                row_frame.rowconfigure(0, weight=1)
                row_frame.grid(
                    row=row_idx,
                    column=0,
                    sticky='nsew',
                    padx=5,
                    pady=5
                )
                
                for col_idx in range(self.num_columns):
                    row_frame.columnconfigure(
                        col_idx,
                        weight=1,
                        uniform=f"shelf_{shelf_idx}_row_{row_idx}"
                    )
                    section_frame = tk.Frame(row_frame, bg='white', relief=tk.SUNKEN, bd=2)
                    section_frame.columnconfigure(0, weight=1)
                    section_frame.grid_propagate(False)
                    section_frame.grid(
                        row=0,
                        column=col_idx,
                        sticky='nsew',
                        padx=5,
                        pady=5
                    )
                    
                    for jig_idx in range(self.jigs_per_section):
                        section_frame.rowconfigure(jig_idx, weight=1)
                        jig_frame = tk.Frame(
                            section_frame,
                            bg=self.empty_bg,
                            relief=tk.RAISED,
                            bd=2,
                        )
                        jig_frame.pack_propagate(False)
                        jig_frame.grid(
                            row=jig_idx,
                            column=0,
                            sticky='nsew',
                            padx=2,
                            pady=2
                        )
                        number_label = tk.Label(
                            jig_frame, bg=self.empty_bg
                        )
                        processing_label = tk.Label(jig_frame, bg=self.empty_bg)
                        time_label = tk.Label(jig_frame, bg=self.empty_bg)
                        status_label = tk.Label(jig_frame, bg=self.empty_bg)
                        for label in (number_label, processing_label, time_label, status_label):
                            label.pack(fill=tk.X)
                        callback = lambda event, s=shelf_idx, r=row_idx, c=col_idx, j=jig_idx: (
                            self.select_position(s, r, c, j)
                        )
                        for widget in (
                            jig_frame, number_label, processing_label, time_label, status_label
                        ):
                            widget.bind('<Button-1>', callback)
                        pos_key = (shelf_idx, row_idx, col_idx, jig_idx)
                        self.shelf_buttons[pos_key] = {
                            "frame": jig_frame,
                            "number": number_label,
                            "processing": processing_label,
                            "time": time_label,
                            "status": status_label,
                        }
                        jig_frame.bind(
                            '<Configure>',
                            lambda event, key=pos_key: self.resize_jig_display(key)
                        )
        
        self.update_display()
        self.root.bind('<Configure>', self.resize_all_jig_displays, add='+')

    def resize_all_jig_displays(self, event=None):
        """Resize JIG text after the application window changes size."""
        for pos_key in self.shelf_buttons:
            self.resize_jig_display(pos_key)

    def resize_jig_display(self, pos_key):
        """Scale JIG text to fit the current width and height of its position."""
        display = self.shelf_buttons[pos_key]
        frame = display["frame"]
        available_width = frame.winfo_width() - 8
        available_height = frame.winfo_height() - 8
        label_sizes = {
            "number": calculate_display_font_size(
                self.jig_number_font_size, 10, available_width, available_height
            ),
            "processing": calculate_display_font_size(
                self.processing_text_font_size,
                len(self.processing_text),
                available_width,
                available_height
            ),
            "time": calculate_display_font_size(
                self.remaining_time_font_size, 5, available_width, available_height
            ),
            "status": calculate_display_font_size(
                self.not_removed_text_font_size,
                len(self.not_removed_text),
                available_width,
                available_height
            ),
        }
        for label_name, font_size in label_sizes.items():
            display[label_name].config(
                font=('Arial', font_size, 'bold' if label_name != "processing" else 'normal'),
                wraplength=0
            )

    def validate_operator_number_length(self, value):
        """Prevent entering more than the required number of operator characters."""
        return len(value) <= OPERATOR_NUMBER_LENGTH

    def get_data_file_path(self, option):
        """Return a configured data-file path relative to the application directory."""
        path = Path(self.config.get('FILES', option))
        return str(path if path.is_absolute() else self.application_dir / path)

    def write_config(self, config_data):
        """Write configuration data to config.toml."""
        config_path = self.application_dir / 'config.toml'
        with open(config_path, 'w', encoding='utf-8', newline='\n') as config_file:
            for section, options in config_data.items():
                config_file.write(f'[{section}]\n')
                for option, value in options.items():
                    config_file.write(f'{option} = {format_toml_value(value)}\n')
                config_file.write('\n')

    def schedule_window_size_save(self, event):
        """Save the final user-selected application size after a resize."""
        if event.widget is not self.root:
            return
        if self.window_resize_job is not None:
            self.root.after_cancel(self.window_resize_job)
        self.window_resize_job = self.root.after(500, self.save_window_size)

    def save_window_size(self):
        """Persist the current application width and height to config.toml."""
        self.window_resize_job = None
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        if width < 400 or height < 300:
            return
        updated_config = {
            section: dict(options) for section, options in self.config.data.items()
        }
        updated_config.setdefault('WINDOW', {})['width'] = width
        updated_config['WINDOW']['height'] = height
        try:
            self.write_config(updated_config)
        except OSError:
            return
        self.config = TomlConfig(updated_config)

    def focus_operator_entry(self, event=None):
        """Move to the operator-number field after confirming a JIG number."""
        self.operator_entry.focus_set()
        return "break"

    def input_jig(self):
        """Wczytanie numeru JIG"""
        operator_number = self.operator_entry.get()
        if not is_valid_operator_number(operator_number):
            messagebox.showerror(
                "Error",
                f"Operator number must contain exactly {OPERATOR_NUMBER_LENGTH} characters."
            )
            self.operator_entry.focus_set()
            return

        try:
            jig_num = int(self.jig_entry.get())
            if jig_num < 0:
                messagebox.showerror("Error", "JIG number must be positive")
                return
            
            self.current_jig = jig_num
            self.current_operator_number = operator_number
            self.jig_entry.delete(0, tk.END)
            self.operator_entry.delete(0, tk.END)
            self.status_label.config(text=f"JIG #{jig_num} selected. Click a shelf position.", 
                                    bg='lightyellow')
        except ValueError:
            messagebox.showerror("Error", "Enter a valid JIG number")
    
    def select_position(self, shelf, row, col, jig):
        """Wybór pozycji na półce"""
        pos_key = (shelf, row, col, jig)

        # Expired JIGs can be removed without entering a new JIG number.
        if pos_key in self.oven_state and pos_key in self.expired_jigs:
            self.save_to_history(
                self.oven_state[pos_key],
                shelf,
                row,
                col,
                jig,
                action="remove",
                operator_number=self.jig_operator_numbers.get(pos_key),
            )
            del self.oven_state[pos_key]
            self.jig_timers.pop(pos_key, None)
            self.jig_insertion_times.pop(pos_key, None)
            self.jig_operator_numbers.pop(pos_key, None)
            self.timer_threads.pop(pos_key, None)
            self.expired_jigs.discard(pos_key)
            self.play_sound(self.empty_sound_file)
            self.save_state()
            self.update_display()
            self.status_label.config(
                text="Expired JIG removed from the position.",
                bg='lightgreen'
            )
            return

        if self.current_jig is None:
            messagebox.showwarning("Warning", "Enter a JIG number first")
            return

        source_row = self.get_adjacent_occupied_row(shelf, row, col, jig)
        if source_row is not None:
            moved_jig = messagebox.askyesno(
                "JIG move",
                f"Was the JIG from row {source_row + 1} moved to row {row + 1}, "
                f"with the new JIG inserted in row {source_row + 1}?"
            )
            if not moved_jig:
                self.status_label.config(
                    text="JIG insertion cancelled. Confirm the physical move first.",
                    bg='lightyellow'
                )
                return
            self.move_jig_to_adjacent_row(shelf, source_row, row, col, jig)
            pos_key = (shelf, source_row, col, jig)

        if pos_key in self.oven_state:
            messagebox.showwarning(
                "Position occupied",
                "Remove the JIG from this position before inserting a new one."
            )
            return

        # Dodaj nowy JIG
        self.oven_state[pos_key] = self.current_jig

        # Inicjalizuj timer dla tego JIG
        self.jig_timers[pos_key] = self.initial_time * 60

        # Zapisz czas włożenia JIG
        self.jig_insertion_times[pos_key] = datetime.now()
        self.jig_operator_numbers[pos_key] = self.current_operator_number

        # Zapisz do historii
        self.save_to_history(
            self.current_jig,
            pos_key[0],
            pos_key[1],
            pos_key[2],
            pos_key[3],
            action="insert",
            operator_number=self.current_operator_number,
        )

        # Uruchom timer dla tego JIG
        self.start_jig_timer(pos_key)
        
        self.save_state()
        self.update_display()
        self.current_jig = None
        self.current_operator_number = None
        self.status_label.config(text="Position updated. Enter the next JIG.", bg='lightgreen')
        self.jig_entry.focus_set()

    def get_adjacent_occupied_row(self, shelf, row, col, jig):
        """Return the only occupied adjacent row in the same shelf and column."""
        adjacent_rows = [
            adjacent_row
            for adjacent_row in (row - 1, row + 1)
            if 0 <= adjacent_row < self.num_rows
            and (shelf, adjacent_row, col, jig) in self.oven_state
        ]
        if len(adjacent_rows) == 1:
            return adjacent_rows[0]
        return None

    def move_jig_to_adjacent_row(self, shelf, source_row, destination_row, col, jig):
        """Move a JIG vertically within the same shelf and column."""
        source = (shelf, source_row, col, jig)
        destination = (shelf, destination_row, col, jig)
        jig_num = self.oven_state.pop(source)
        self.oven_state[destination] = jig_num
        for collection in (
            self.jig_timers,
            self.jig_insertion_times,
            self.jig_operator_numbers,
            self.timer_threads,
        ):
            if source in collection:
                collection[destination] = collection.pop(source)
        if source in self.expired_jigs:
            self.expired_jigs.remove(source)
            self.expired_jigs.add(destination)
        if source in self.warning_sound_played:
            self.warning_sound_played.remove(source)
            self.warning_sound_played.add(destination)
        self.save_move_to_history(
            jig_num, source, destination, self.jig_operator_numbers.get(destination)
        )
    
    def start_jig_timer(self, pos_key):
        """Uruchomienie timera dla konkretnego JIG"""
        if pos_key not in self.timer_threads:
            timer_thread = Thread(target=self.run_jig_timer, args=(pos_key,), daemon=True)
            self.timer_threads[pos_key] = timer_thread
            timer_thread.start()
    
    def run_jig_timer(self, pos_key):
        """Działanie timera dla konkretnego JIG"""
        while pos_key in self.jig_timers and self.jig_timers[pos_key] > 0:
            insertion_time = self.jig_insertion_times.get(pos_key)
            if insertion_time is not None:
                self.jig_timers[pos_key] = calculate_remaining_time(
                    insertion_time, self.initial_time
                )
            else:
                self.jig_timers[pos_key] -= 1
            self.update_display()
            if (
                0 < self.jig_timers[pos_key] <= self.near_expiry_seconds
                and pos_key not in self.warning_sound_played
            ):
                self.warning_sound_played.add(pos_key)
                self.play_sound(self.occupied_sound_file)
            time.sleep(1)
        
        # Czasami usun timer
        if pos_key in self.jig_timers and self.jig_timers[pos_key] <= 0:
            self.expired_jigs.add(pos_key)
            self.play_sound(self.expired_sound_file)
            self.save_state()
            self.update_display()
    
    def start_all_timers(self, current_time=None):
        """Uruchomienie wszystkich timerów dla JIG z poprzedniej sesji"""
        current_time = current_time or datetime.now()
        for pos_key in list(self.oven_state):
            insertion_time = self.jig_insertion_times.get(pos_key)
            if insertion_time is None:
                self.jig_timers[pos_key] = self.initial_time * 60
            else:
                self.jig_timers[pos_key] = calculate_remaining_time(
                    insertion_time, self.initial_time, current_time
                )

            if self.jig_timers[pos_key] <= 0:
                self.expired_jigs.add(pos_key)
            else:
                self.start_jig_timer(pos_key)

        self.update_display()

    def schedule_expired_blink(self):
        """Toggle the display color of expired JIGs at the configured interval."""
        self.blink_expired = not self.blink_expired
        self.update_display()
        self.root.after(self.blink_interval_ms, self.schedule_expired_blink)

    def play_sound(self, sound_file):
        """Play a configured WAV file when its path is provided."""
        if not sound_file:
            return
        path = Path(sound_file)
        sound_path = path if path.is_absolute() else self.application_dir / path
        if sound_path.is_file():
            winsound.PlaySound(str(sound_path), winsound.SND_FILENAME | winsound.SND_ASYNC)
    
    def get_color_for_time(self, remaining_seconds):
        """Zwraca kolory na podstawie pozostałego czasu"""
        remaining_minutes = remaining_seconds / 60
        
        if remaining_minutes <= self.red_threshold:
            return self.red_bg, self.red_text
        elif remaining_minutes <= self.orange_threshold:
            return self.orange_bg, self.orange_text
        else:
            return self.normal_bg, self.normal_text

    def get_jig_display_colors(self, pos_key, remaining_seconds):
        """Return the background and text colors for a JIG and its operator."""
        operator_color = self.operator_colors.get(self.jig_operator_numbers.get(pos_key))
        default_background, default_text = self.get_color_for_time(remaining_seconds)
        if not operator_color:
            return default_background, default_text

        if remaining_seconds <= self.red_threshold * 60:
            background = self.red_bg if self.blink_expired else operator_color
        elif remaining_seconds <= self.orange_threshold * 60:
            background = self.orange_bg if self.blink_expired else operator_color
        else:
            background = operator_color
        return background, get_contrast_text_color(background)
    
    def format_time(self, seconds):
        """Konwertuje sekundy do formatu MM:SS"""
        minutes = int(seconds) // 60
        secs = int(seconds) % 60
        return f"{minutes:02d}:{secs:02d}"
    
    def update_display(self):
        """Aktualizacja wyświetlania przycisków"""
        for pos_key, btn in self.shelf_buttons.items():
            if pos_key in self.oven_state:
                jig_num = self.oven_state[pos_key]
                remaining_time = self.jig_timers.get(pos_key, self.initial_time * 60)
                time_str = self.format_time(remaining_time)
                if pos_key in self.expired_jigs:
                    operator_color = self.operator_colors.get(
                        self.jig_operator_numbers.get(pos_key)
                    )
                    bg_color = self.red_bg if self.blink_expired else (
                        operator_color or self.blink_orange_bg
                    )
                    text_color = get_contrast_text_color(bg_color)
                    status_text = self.not_removed_text
                else:
                    bg_color, text_color = self.get_jig_display_colors(
                        pos_key, remaining_time
                    )
                    status_text = ""
                display = self.shelf_buttons[pos_key]
                display["frame"].config(bg=bg_color)
                display["number"].config(
                    text=f"#{jig_num}",
                    bg=bg_color,
                    fg=text_color,
                )
                display["processing"].config(
                    text=self.processing_text,
                    bg=bg_color,
                    fg=text_color,
                )
                display["time"].config(
                    text=time_str,
                    bg=bg_color,
                    fg=text_color,
                )
                display["status"].config(
                    text=status_text,
                    bg=bg_color,
                    fg=text_color,
                )
                self.resize_jig_display(pos_key)
            else:
                display = self.shelf_buttons[pos_key]
                display["frame"].config(bg=self.empty_bg)
                for label in display.values():
                    if label is not display["frame"]:
                        label.config(text="", bg=self.empty_bg, fg=self.empty_text)
    
    def clear_input_fields(self):
        """Clear the JIG and operator input fields without changing the oven."""
        self.current_jig = None
        self.current_operator_number = None
        self.status_label.config(
            text="Fields cleared. Ready for a new JIG number.",
            bg='lightyellow'
        )
        self.jig_entry.delete(0, tk.END)
        self.operator_entry.delete(0, tk.END)

    def open_settings(self):
        """Open a graphical editor for every option in config.toml."""
        settings_window = tk.Toplevel(self.root)
        settings_window.title("Settings")
        settings_window.configure(bg=self.app_bg)
        settings_window.geometry("760x700")

        canvas = tk.Canvas(settings_window, bg=self.app_bg, highlightthickness=0)
        scrollbar = tk.Scrollbar(settings_window, orient=tk.VERTICAL, command=canvas.yview)
        content = tk.Frame(canvas, bg=self.app_bg)
        content.bind(
            '<Configure>',
            lambda event: canvas.configure(scrollregion=canvas.bbox('all'))
        )
        canvas.create_window((0, 0), window=content, anchor='nw')
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        entries = {}
        pending_operator_colors = {}
        section_names = (
            ["OVEN_TITLE", "SHELF_LABELS"]
            + [
                section
                for section in self.config.data
                if section not in {"OVEN_TITLE", "SHELF_LABELS"}
            ]
        )
        for section in section_names:
            options = self.config.data[section]
            section_frame = tk.LabelFrame(
                content,
                text=section,
                bg=self.app_bg,
                padx=10,
                pady=8,
                font=('Arial', 10, 'bold')
            )
            section_frame.pack(fill=tk.X, padx=12, pady=6)
            section_frame.columnconfigure(1, weight=1)
            if section == "OPERATORS":
                self.create_operator_settings(
                    section_frame,
                    options,
                    entries,
                    pending_operator_colors,
                )
                continue

            for row, (option, value) in enumerate(options.items()):
                if section == "OVEN_TITLE" and option == "text":
                    label_text = "Oven name:"
                elif section == "SHELF_LABELS" and option.startswith("shelf_"):
                    label_text = f"Shelf name {option.removeprefix('shelf_')}:"
                else:
                    label_text = option.replace('_', ' ') + ':'
                tk.Label(
                    section_frame,
                    text=label_text,
                    bg=self.app_bg,
                    anchor='w'
                ).grid(row=row, column=0, sticky='w', padx=(0, 8), pady=3)
                entry = tk.Entry(section_frame)
                entry.insert(0, str(value))
                entry.grid(row=row, column=1, sticky='ew', pady=3)
                entries[(section, option)] = entry
                if isinstance(value, str) and value.startswith('#'):
                    tk.Button(
                        section_frame,
                        text="Color...",
                        command=lambda field=entry: self.choose_color(field)
                    ).grid(row=row, column=2, padx=(8, 0), pady=3)

        actions = tk.Frame(settings_window, bg=self.app_bg)
        actions.pack(fill=tk.X, padx=12, pady=10)
        tk.Button(
            actions,
            text="Save settings",
            command=lambda: self.save_settings(
                entries,
                settings_window,
                pending_operator_colors,
            ),
            font=('Arial', 10, 'bold')
        ).pack(side=tk.RIGHT, padx=(8, 0))
        tk.Button(
            actions,
            text="Cancel",
            command=settings_window.destroy,
            font=('Arial', 10)
        ).pack(side=tk.RIGHT)

    def create_operator_settings(
        self, section_frame, operators, entries, pending_operator_colors
    ):
        """Create an editable operator list and fields for adding a new operator."""
        tk.Label(
            section_frame,
            text="Operator number",
            bg=self.app_bg,
            anchor='w',
            font=('Arial', 9, 'bold'),
        ).grid(row=0, column=0, sticky='w', padx=(0, 8), pady=(0, 3))
        tk.Label(
            section_frame,
            text="Color",
            bg=self.app_bg,
            anchor='w',
            font=('Arial', 9, 'bold'),
        ).grid(row=0, column=1, sticky='w', pady=(0, 3))

        operator_list = tk.Frame(section_frame, bg=self.app_bg)
        operator_list.grid(row=1, column=0, columnspan=3, sticky='ew')
        operator_list.columnconfigure(1, weight=1)
        for row, (option, color) in enumerate(sorted(operators.items())):
            self.add_operator_row(operator_list, row, option, color, entries)

        add_row = 2
        tk.Label(
            section_frame,
            text="New operator number:",
            bg=self.app_bg,
            anchor='w',
        ).grid(row=add_row, column=0, sticky='w', padx=(0, 8), pady=(10, 3))
        operator_number_entry = tk.Entry(section_frame)
        operator_number_entry.grid(
            row=add_row, column=1, sticky='ew', pady=(10, 3)
        )
        tk.Label(
            section_frame,
            text="New operator color:",
            bg=self.app_bg,
            anchor='w',
        ).grid(row=add_row + 1, column=0, sticky='w', padx=(0, 8), pady=3)
        operator_color_entry = tk.Entry(section_frame)
        operator_color_entry.insert(0, "#FFFFFF")
        operator_color_entry.grid(row=add_row + 1, column=1, sticky='ew', pady=3)
        tk.Button(
            section_frame,
            text="Color...",
            command=lambda: self.choose_color(operator_color_entry),
        ).grid(row=add_row + 1, column=2, padx=(8, 0), pady=3)
        tk.Button(
            section_frame,
            text="Add",
            command=lambda: self.add_operator_to_settings(
                operator_list,
                entries,
                pending_operator_colors,
                operator_number_entry,
                operator_color_entry,
            ),
        ).grid(row=add_row + 2, column=1, sticky='e', pady=(3, 0))

    def add_operator_row(self, operator_list, row, option, color, entries):
        """Append one operator and its editable color to the settings list."""
        operator_number = option.removeprefix("operator_")
        tk.Label(
            operator_list,
            text=operator_number,
            bg=self.app_bg,
            anchor='w',
        ).grid(row=row, column=0, sticky='w', padx=(0, 8), pady=3)
        color_entry = tk.Entry(operator_list)
        color_entry.insert(0, color)
        color_entry.grid(row=row, column=1, sticky='ew', pady=3)
        tk.Button(
            operator_list,
            text="Color...",
            command=lambda: self.choose_color(color_entry),
        ).grid(row=row, column=2, padx=(8, 0), pady=3)
        entries[("OPERATORS", option)] = color_entry

    def add_operator_to_settings(
        self,
        operator_list,
        entries,
        pending_operator_colors,
        operator_number_entry,
        operator_color_entry,
    ):
        """Validate and add a new operator to the settings list."""
        operator_number = operator_number_entry.get().strip()
        operator_color = operator_color_entry.get().strip().upper()
        option = f"operator_{operator_number}"
        if not is_valid_operator_number(operator_number):
            messagebox.showerror(
                "Invalid operator",
                "New operator number must contain exactly 4 characters.",
                parent=operator_number_entry.winfo_toplevel(),
            )
            return
        if not re.fullmatch(r'#[0-9A-F]{6}', operator_color):
            messagebox.showerror(
                "Invalid operator",
                "New operator color must use the #RRGGBB format.",
                parent=operator_number_entry.winfo_toplevel(),
            )
            return
        if ("OPERATORS", option) in entries:
            messagebox.showerror(
                "Duplicate operator",
                "This operator is already on the list. Change its color in the list.",
                parent=operator_number_entry.winfo_toplevel(),
            )
            return

        self.add_operator_row(
            operator_list,
            sum(1 for section, _ in entries if section == "OPERATORS"),
            option,
            operator_color,
            entries,
        )
        pending_operator_colors[option] = operator_color
        operator_number_entry.delete(0, tk.END)
        operator_color_entry.delete(0, tk.END)
        operator_color_entry.insert(0, "#FFFFFF")

    def choose_color(self, entry):
        """Set a configuration color field using the native color picker."""
        color = colorchooser.askcolor(color=entry.get(), parent=entry.winfo_toplevel())[1]
        if color:
            entry.delete(0, tk.END)
            entry.insert(0, color.upper())

    def save_settings(
        self,
        entries,
        settings_window,
        pending_operator_colors=None,
    ):
        """Validate and write graphical settings to config.toml."""
        updated_config = {}
        for section, options in self.config.data.items():
            updated_config[section] = {}
            for option, original_value in options.items():
                value = entries[(section, option)].get().strip()
                if isinstance(original_value, int):
                    try:
                        value = int(value)
                    except ValueError:
                        messagebox.showerror(
                            "Invalid setting",
                            f"{section}.{option} must be a whole number.",
                            parent=settings_window
                        )
                        return
                    if value < 0:
                        messagebox.showerror(
                            "Invalid setting",
                            f"{section}.{option} cannot be negative.",
                            parent=settings_window
                        )
                        return
                updated_config[section][option] = value

        if pending_operator_colors:
            for option in pending_operator_colors:
                operator_color = entries[("OPERATORS", option)].get().strip().upper()
                if not re.fullmatch(r'#[0-9A-F]{6}', operator_color):
                    messagebox.showerror(
                        "Invalid setting",
                        f"OPERATORS.{option} must use the #RRGGBB format.",
                        parent=settings_window,
                    )
                    return
                updated_config.setdefault("OPERATORS", {})[option] = operator_color

        try:
            self.write_config(updated_config)
        except OSError as error:
            messagebox.showerror(
                "Save failed",
                f"Unable to save settings:\n{error}",
                parent=settings_window
            )
            return

        self.config = TomlConfig(updated_config)
        settings_window.destroy()
        messagebox.showinfo(
            "Settings saved",
            "Settings have been saved. Restart the application to apply them.",
            parent=self.root
        )
    
    def save_to_history(
        self, jig_num, shelf, row, col, jig_idx, action="insert", operator_number=None
    ):
        """Zapis do pliku historii"""
        now = datetime.now()
        timestamp = now.strftime(HISTORY_TIMESTAMP_FORMAT)
        marker = "->" if action == "insert" else "<-"
        
        history_entry = (
            f"[{timestamp}] JIG #{jig_num} {marker} Shelf {shelf + 1}, "
            f"Row {row + 1}, Column {col + 1}, Position {jig_idx + 1}"
        )
        if operator_number:
            history_entry += f", Operator #{operator_number}"
        history_entry += "\n"
        
        with open(self.history_file, 'a', encoding='utf-8') as f:
            f.write(history_entry)

    def save_move_to_history(self, jig_num, source, destination, operator_number=None):
        """Record a position change without treating the JIG as newly inserted."""
        timestamp = datetime.now().strftime(HISTORY_TIMESTAMP_FORMAT)
        source_text = (
            f"Shelf {source[0] + 1}, Row {source[1] + 1}, "
            f"Column {source[2] + 1}, Position {source[3] + 1}"
        )
        destination_text = (
            f"Shelf {destination[0] + 1}, Row {destination[1] + 1}, "
            f"Column {destination[2] + 1}, Position {destination[3] + 1}"
        )
        with open(self.history_file, 'a', encoding='utf-8') as history:
            entry = f"[{timestamp}] JIG #{jig_num} ~> {source_text} -> {destination_text}"
            if operator_number:
                entry += f", Operator #{operator_number}"
            history.write(entry + "\n")
    
    def save_state(self):
        """Zapis stanu pieca do JSON"""
        state_dict = {}
        timers_dict = {}
        insertion_times_dict = {}
        operator_numbers_dict = {}
        
        for pos, jig_num in self.oven_state.items():
            state_dict[str(pos)] = jig_num
            if pos in self.jig_timers:
                timers_dict[str(pos)] = self.jig_timers[pos]
            if pos in self.jig_insertion_times:
                insertion_times_dict[str(pos)] = self.jig_insertion_times[pos].isoformat()
            if pos in self.jig_operator_numbers:
                operator_numbers_dict[str(pos)] = self.jig_operator_numbers[pos]
        
        with open(self.state_file, 'w', encoding='utf-8') as f:
            json.dump({
                "state": state_dict, 
                "timers": timers_dict,
                "insertion_times": insertion_times_dict,
                "operator_numbers": operator_numbers_dict,
            }, f, indent=2)
    
    def load_state(self):
        """Wczytanie stanu pieca z JSON"""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    state_dict = data.get("state", {})
                    timers_dict = data.get("timers", {})
                    insertion_times_dict = data.get("insertion_times", {})
                    operator_numbers_dict = data.get("operator_numbers", {})
                    
                    state = {}
                    for pos_str, jig_num in state_dict.items():
                        pos = eval(pos_str)
                        state[pos] = jig_num
                        
                        # Wczytaj timery
                        if pos_str in timers_dict:
                            self.jig_timers[pos] = timers_dict[pos_str]
                        else:
                            self.jig_timers[pos] = self.initial_time * 60
                        
                        # Wczytaj czasy włożenia JIG
                        if pos_str in insertion_times_dict:
                            try:
                                self.jig_insertion_times[pos] = datetime.fromisoformat(insertion_times_dict[pos_str])
                            except:
                                self.jig_insertion_times[pos] = datetime.now()
                        if pos_str in operator_numbers_dict:
                            self.jig_operator_numbers[pos] = operator_numbers_dict[pos_str]
                    
                    return state
            except:
                pass
        return {}

    def load_history(self):
        """Restore active insertion timestamps and apply recorded removals."""
        # No history means there are no JIGs to restore from a previous session.
        self.oven_state.clear()
        self.jig_timers.clear()
        self.jig_insertion_times.clear()
        self.jig_operator_numbers.clear()
        self.expired_jigs.clear()

        if not os.path.exists(self.history_file):
            return
        try:
            with open(self.history_file, "r", encoding="utf-8") as history:
                events = [parse_history_line(line) for line in history]
        except OSError:
            return

        for event in events:
            if event is None:
                continue
            pos_key = event["position"]
            if event["action"] == "remove":
                self.oven_state.pop(pos_key, None)
                self.jig_timers.pop(pos_key, None)
                self.jig_insertion_times.pop(pos_key, None)
                self.jig_operator_numbers.pop(pos_key, None)
                self.expired_jigs.discard(pos_key)
            elif event["action"] == "move":
                source = event["from_position"]
                if source in self.oven_state:
                    self.oven_state[pos_key] = self.oven_state.pop(source)
                    self.jig_insertion_times[pos_key] = self.jig_insertion_times.pop(source)
                    if source in self.jig_operator_numbers:
                        self.jig_operator_numbers[pos_key] = self.jig_operator_numbers.pop(source)
                    elif event["operator"]:
                        self.jig_operator_numbers[pos_key] = event["operator"]
            else:
                self.oven_state[pos_key] = event["jig"]
                self.jig_insertion_times[pos_key] = event["timestamp"]
                if event["operator"]:
                    self.jig_operator_numbers[pos_key] = event["operator"]

if __name__ == "__main__":
    root = tk.Tk()
    app = OvenManager(root)
    root.mainloop()
