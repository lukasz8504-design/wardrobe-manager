import tkinter as tk
from tkinter import messagebox
import json
import os
from datetime import datetime
import re
from threading import Thread
import time
import winsound

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.11+ uses tomllib
    import tomli as tomllib


HISTORY_TIMESTAMP_FORMAT = "%d-%m-%Y %H:%M:%S"
OPERATOR_NUMBER_LENGTH = 4
CONFIG_FILE = "config.toml"
LEGACY_CONFIG_FILE = "config.ini"
APP_DIR = os.path.dirname(os.path.abspath(__file__))
TK_TCL_ERROR = getattr(tk, "TclError", None)


def calculate_remaining_time(insertion_time, initial_minutes, current_time=None):
    """Return the remaining timer seconds based on the insertion timestamp."""
    current_time = current_time or datetime.now()
    return max(0, initial_minutes * 60 - (current_time - insertion_time).total_seconds())


def is_valid_operator_number(operator_number):
    """Return whether an operator number has the required length."""
    return len(operator_number) == OPERATOR_NUMBER_LENGTH


def parse_history_line(line):
    """Parse a history line into its event data, or return None for old/invalid lines."""
    move_pattern = (
        r"^\[(?P<timestamp>[^\]]+)\]\s+JIG\s+#(?P<jig>\d+)\s+~>\s+"
        r"(?:Shelf|Półka)\s+(?P<from_shelf>\d+),\s+(?:Row|Rząd)\s+(?P<from_row>\d+),\s+"
        r"(?:Column|Kolumna)\s+(?P<from_col>\d+),\s+(?:Position|Pozycja)\s+(?P<from_position>\d+)\s+"
        r"->\s+(?:Shelf|Półka)\s+(?P<to_shelf>\d+),\s+(?:Row|Rząd)\s+(?P<to_row>\d+),\s+"
        r"(?:Column|Kolumna)\s+(?P<to_col>\d+),\s+(?:Position|Pozycja)\s+(?P<to_position>\d+)"
    )
    pattern = (
        r"^\[(?P<timestamp>[^\]]+)\]\s+JIG\s+#(?P<jig>\d+)\s+"
        r"(?P<action>->|<-)\s+(?:Shelf|Półka)\s+(?P<shelf>\d+),\s+(?:Row|Rząd)\s+(?P<row>\d+),\s+"
        r"(?:Column|Kolumna)\s+(?P<col>\d+),\s+(?:Position|Pozycja)\s+(?P<position>\d+)"
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
    }


def load_config(config_path=None):
    """Load application configuration from a TOML file."""
    config_path = (
        os.path.join(APP_DIR, CONFIG_FILE)
        if config_path is None else config_path
    )
    with open(config_path, "rb") as config_file:
        return tomllib.load(config_file)


def load_default_config(config_path=None):
    """Load the default application configuration and report legacy INI migration issues."""
    default_config_path = os.path.join(APP_DIR, CONFIG_FILE)
    config_path = (
        default_config_path
        if config_path is None else (
            config_path if os.path.isabs(config_path)
            else os.path.join(APP_DIR, config_path)
        )
    )
    legacy_config_path = os.path.join(os.path.dirname(config_path), LEGACY_CONFIG_FILE)
    using_default_path = config_path == default_config_path

    if not os.path.exists(config_path):
        if using_default_path and os.path.exists(legacy_config_path):
            raise FileNotFoundError(
                "Missing config.toml. Found legacy config.ini; rewrite it into valid TOML "
                "syntax and save it as config.toml."
            )
        missing_path = CONFIG_FILE if using_default_path else config_path
        raise FileNotFoundError(f"Missing configuration file: {missing_path}")

    return load_config(config_path)


class WardrobeManager:
    def __init__(self, root):
        self.root = root
        self.root.title("Ocen Manager - Szafa")
        
        # Wczytanie konfiguracji
        self.apply_config(load_default_config(), APP_DIR)
        
        # Maksymalizuj okno
        state_method = getattr(self.root, "state", None)
        if callable(state_method):
            if TK_TCL_ERROR is None:
                state_method('zoomed')  # Windows
            else:
                try:
                    state_method('zoomed')  # Windows
                except TK_TCL_ERROR:
                    pass
        self.root.resizable(True, True)
        
        # Stan timera - osobny timer dla każdego JIG
        self.jig_timers = {}  # {pos_key: remaining_time_in_seconds}
        self.jig_insertion_times = {}  # {pos_key: insertion_timestamp}
        self.timer_threads = {}  # {pos_key: thread}
        self.expired_jigs = set()
        self.warning_sound_played = set()
        self.blink_expired = False
        self.current_jig = None
        
        # Wczytanie stanu szafy
        self.wardrobe_state = self.load_state()
        self.load_history()
        
        # GUI
        self.setup_ui()
        self.start_all_timers()
        self.schedule_expired_blink()

    def apply_config(self, config, config_dir=None):
        """Apply parsed configuration data to instance attributes."""
        self.config = config
        config_dir = config_dir or APP_DIR

        # Parametry szafy
        self.num_shelves = self.config['WARDROBE']['num_shelves']
        self.num_rows = self.config['WARDROBE']['num_rows']
        self.num_columns = self.config['WARDROBE']['num_columns']
        self.squares_per_section = self.config['WARDROBE']['squares_per_section']

        # Parametry timera
        self.initial_time = self.config['TIMER']['initial_time']
        self.orange_threshold = self.config['TIMER']['orange_threshold']
        self.red_threshold = self.config['TIMER']['red_threshold']

        # Kolory
        self.normal_bg = self.config['COLORS']['normal_bg']
        self.orange_bg = self.config['COLORS']['orange_bg']
        self.red_bg = self.config['COLORS']['red_bg']
        self.normal_text = self.config['COLORS']['normal_text']
        self.orange_text = self.config['COLORS']['orange_text']
        self.red_text = self.config['COLORS']['red_text']
        self.empty_bg = self.config['COLORS']['empty_bg']
        self.empty_text = self.config['COLORS']['empty_text']
        self.blink_red_bg = self.config['COLORS']['blink_red_bg']
        self.blink_orange_bg = self.config['COLORS']['blink_orange_bg']
        self.blink_text = self.config['COLORS']['blink_text']

        # Wygląd
        self.jig_width = self.config['APPEARANCE']['square_width']
        self.jig_height = self.config['APPEARANCE']['square_height']
        self.jig_font_size = self.config['APPEARANCE']['square_font_size']
        self.wardrobe_name = self.config['WARDROBE_TITLE']['text']
        self.wardrobe_name_color = self.config['WARDROBE_TITLE']['color']
        self.wardrobe_name_font_size = self.config['WARDROBE_TITLE']['font_size']
        self.near_expiry_seconds = self.config['ALERTS']['near_expiry_seconds']
        self.blink_interval_ms = self.config['ALERTS']['blink_interval_ms']
        self.empty_sound_file = self.config['SOUNDS']['empty_sound_file']
        self.occupied_sound_file = self.config['SOUNDS']['occupied_sound_file']
        self.expired_sound_file = self.config['SOUNDS']['expired_sound_file']

        # Pliki
        self.history_file = self.resolve_config_path(
            self.config['FILES']['history_file'], config_dir
        )
        self.state_file = self.resolve_config_path(
            self.config['FILES']['state_file'], config_dir
        )

    @staticmethod
    def resolve_config_path(path_value, config_dir):
        """Resolve relative config file paths against the configuration directory."""
        if os.path.isabs(path_value):
            return path_value
        return os.path.join(config_dir, path_value)
        
    def setup_ui(self):
        """Tworzenie interfejsu użytkownika"""
        # Główna ramka
        main_frame = tk.Frame(self.root, bg='white')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Górna część - Input
        top_frame = tk.Frame(main_frame, bg='white')
        top_frame.pack(fill=tk.X, pady=10)
        
        # Input dla numeru JIG
        tk.Label(top_frame, text="JIG number:", bg='white', font=('Arial', 12, 'bold')).pack(side=tk.LEFT, padx=5)
        self.jig_entry = tk.Entry(top_frame, width=10, font=('Arial', 12))
        self.jig_entry.pack(side=tk.LEFT, padx=5)
        self.jig_entry.bind('<Return>', self.focus_operator_entry)

        tk.Label(top_frame, text="Operator number:", bg='white', font=('Arial', 12, 'bold')).pack(side=tk.LEFT, padx=5)
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
        tk.Button(top_frame, text="Clear all", command=self.clear_all, font=('Arial', 10)).pack(side=tk.LEFT, padx=5)
        
        # Status
        self.status_label = tk.Label(top_frame, text="Waiting for JIG number...", 
                                     bg='lightyellow', font=('Arial', 10), relief=tk.SUNKEN, bd=1)
        self.status_label.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10)
        
        # Środkowa część - Półki bez scrollbara
        shelves_frame = tk.Frame(main_frame, bg='white')
        shelves_frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            shelves_frame,
            text=self.wardrobe_name,
            bg='white',
            fg=self.wardrobe_name_color,
            font=('Arial', self.wardrobe_name_font_size, 'bold')
        ).pack(pady=(0, 10))

        self.shelf_buttons = {}
        
        for shelf_idx in range(self.num_shelves):
            shelf_label = tk.Label(
                shelves_frame,
                text=f"Shelf {shelf_idx + 1}",
                bg='white',
                font=('Arial', 10, 'bold')
            )
            shelf_label.pack(pady=5)
            
            shelf_frame = tk.Frame(shelves_frame, bg='lightgray', relief=tk.RAISED, bd=2)
            shelf_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
            
            # Każda półka ma 2 wiersze (jeden na drugim) i 1 kolumnę
            for row_idx in range(self.num_rows):
                row_frame = tk.Frame(shelf_frame, bg='lightgray')
                row_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
                
                for col_idx in range(self.num_columns):
                    # Kontener na JIG (dwa na sobie)
                    section_frame = tk.Frame(row_frame, bg='white', relief=tk.SUNKEN, bd=2)
                    section_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
                    
                    # JIG ustawione pionowo (jeden nad drugim)
                    for jig_idx in range(self.squares_per_section):
                        jig_btn = tk.Button(
                            section_frame, 
                            text="", 
                            font=('Arial', self.jig_font_size, 'bold'),
                            bg='white', 
                            relief=tk.RAISED, 
                            bd=2,
                            width=self.jig_width,
                            height=self.jig_height,
                            command=lambda s=shelf_idx, r=row_idx, c=col_idx, j=jig_idx: 
                            self.select_position(s, r, c, j)
                        )
                        
                        jig_btn.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
                        
                        pos_key = (shelf_idx, row_idx, col_idx, jig_idx)
                        self.shelf_buttons[pos_key] = jig_btn
        
        self.update_display()

    def validate_operator_number_length(self, value):
        """Prevent entering more than the required number of operator characters."""
        return len(value) <= OPERATOR_NUMBER_LENGTH

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
            self.jig_entry.delete(0, tk.END)
            self.operator_entry.delete(0, tk.END)
            imminent_positions = self.get_imminent_expiry_positions()
            if imminent_positions:
                positions = ", ".join(imminent_positions)
                messagebox.showwarning(
                    "Time almost expired",
                    "JIG at "
                    f"{positions} will need to be removed soon. Wait to remove it and "
                    "insert the new JIG at the same time to avoid losing temperature."
                )
            self.status_label.config(text=f"JIG #{jig_num} selected. Click a shelf position.", 
                                    bg='lightyellow')
        except ValueError:
            messagebox.showerror("Error", "Enter a valid JIG number")
    
    def select_position(self, shelf, row, col, jig):
        """Wybór pozycji na półce"""
        pos_key = (shelf, row, col, jig)

        # Expired JIGs can be removed without entering a new JIG number.
        if pos_key in self.wardrobe_state and pos_key in self.expired_jigs:
            self.save_to_history(
                self.wardrobe_state[pos_key], shelf, row, col, jig, action="remove"
            )
            del self.wardrobe_state[pos_key]
            self.jig_timers.pop(pos_key, None)
            self.jig_insertion_times.pop(pos_key, None)
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

        if col == 0 and self.has_jig_in_next_column(shelf, row, jig):
            if messagebox.askyesno(
                "JIG move",
                "Was the JIG from column 2 moved to column 1, with the new JIG "
                "inserted in column 2?"
            ):
                self.move_jig_to_previous_column(shelf, row, jig)
                pos_key = (shelf, row, 1, jig)
        
        # Jeśli pozycja jest już zajęta, usuń poprzedni JIG
        if pos_key in self.wardrobe_state:
            self.save_to_history(
                self.wardrobe_state[pos_key], shelf, row, col, jig, action="remove"
            )
            del self.wardrobe_state[pos_key]
            # Zatrzymaj timer dla tego JIG
            if pos_key in self.jig_timers:
                del self.jig_timers[pos_key]
            if pos_key in self.jig_insertion_times:
                del self.jig_insertion_times[pos_key]
            if pos_key in self.timer_threads:
                del self.timer_threads[pos_key]
            self.expired_jigs.discard(pos_key)
            self.play_sound(self.empty_sound_file)
            self.warning_sound_played.discard(pos_key)
        else:
            # Dodaj nowy JIG
            self.wardrobe_state[pos_key] = self.current_jig
            
            # Inicjalizuj timer dla tego JIG
            self.jig_timers[pos_key] = self.initial_time * 60
            
            # Zapisz czas włożenia JIG
            self.jig_insertion_times[pos_key] = datetime.now()
            
            # Zapisz do historii
            self.save_to_history(self.current_jig, shelf, row, col, jig, action="insert")
            
            # Uruchom timer dla tego JIG
            self.start_jig_timer(pos_key)
        
        self.save_state()
        self.update_display()
        self.current_jig = None
        self.status_label.config(text="Position updated. Enter the next JIG.", bg='lightgreen')

    def get_imminent_expiry_positions(self):
        """Return descriptions of occupied positions that are near expiry."""
        positions = []
        for pos_key, remaining_seconds in self.jig_timers.items():
            if 0 < remaining_seconds <= self.near_expiry_seconds:
                positions.append(
                    f"Shelf {pos_key[0] + 1}, Row {pos_key[1] + 1}, "
                    f"Column {pos_key[2] + 1}, Position {pos_key[3] + 1}"
                )
        return positions

    def has_jig_in_next_column(self, shelf, row, jig):
        """Return whether the matching position in column 2 is occupied."""
        return (shelf, row, 1, jig) in self.wardrobe_state

    def move_jig_to_previous_column(self, shelf, row, jig):
        """Move a JIG from column 2 to column 1 without resetting its timer."""
        source = (shelf, row, 1, jig)
        destination = (shelf, row, 0, jig)
        jig_num = self.wardrobe_state.pop(source)
        self.wardrobe_state[destination] = jig_num
        for collection in (
            self.jig_timers,
            self.jig_insertion_times,
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
        self.save_move_to_history(jig_num, source, destination)
    
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
        for pos_key in list(self.wardrobe_state):
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
        if sound_file and os.path.isfile(sound_file):
            winsound.PlaySound(sound_file, winsound.SND_FILENAME | winsound.SND_ASYNC)
    
    def get_color_for_time(self, remaining_seconds):
        """Zwraca kolory na podstawie pozostałego czasu"""
        remaining_minutes = remaining_seconds / 60
        
        if remaining_minutes <= self.red_threshold:
            return self.red_bg, self.red_text
        elif remaining_minutes <= self.orange_threshold:
            return self.orange_bg, self.orange_text
        else:
            return self.normal_bg, self.normal_text
    
    def format_time(self, seconds):
        """Konwertuje sekundy do formatu MM:SS"""
        minutes = int(seconds) // 60
        secs = int(seconds) % 60
        return f"{minutes:02d}:{secs:02d}"
    
    def update_display(self):
        """Aktualizacja wyświetlania przycisków"""
        for pos_key, btn in self.shelf_buttons.items():
            if pos_key in self.wardrobe_state:
                jig_num = self.wardrobe_state[pos_key]
                remaining_time = self.jig_timers.get(pos_key, self.initial_time * 60)
                time_str = self.format_time(remaining_time)
                if pos_key in self.expired_jigs:
                    time_str += "\nNOT REMOVED"
                    bg_color = (
                        self.blink_red_bg if self.blink_expired else self.blink_orange_bg
                    )
                    text_color = self.blink_text
                else:
                    bg_color, text_color = self.get_color_for_time(remaining_time)
                
                btn.config(
                    text=f"#{jig_num}\n{time_str}", 
                    bg=bg_color, 
                    fg=text_color
                )
            else:
                btn.config(text="", bg=self.empty_bg, fg=self.empty_text)
    
    def clear_all(self):
        """Czyszczenie wszystkiego"""
        for pos_key, jig_num in list(self.wardrobe_state.items()):
            self.save_to_history(
                jig_num, pos_key[0], pos_key[1], pos_key[2], pos_key[3], action="remove"
            )
            self.play_sound(self.empty_sound_file)
        self.jig_timers.clear()
        self.jig_insertion_times.clear()
        self.timer_threads.clear()
        self.current_jig = None
        self.wardrobe_state.clear()
        self.expired_jigs.clear()
        self.warning_sound_played.clear()
        self.save_state()
        self.update_display()
        self.status_label.config(text="Clearing complete. Ready for a new number.", bg='lightyellow')
        self.jig_entry.delete(0, tk.END)
        self.operator_entry.delete(0, tk.END)
    
    def save_to_history(self, jig_num, shelf, row, col, jig_idx, action="insert"):
        """Zapis do pliku historii"""
        now = datetime.now()
        timestamp = now.strftime(HISTORY_TIMESTAMP_FORMAT)
        marker = "->" if action == "insert" else "<-"
        
        history_entry = (
            f"[{timestamp}] JIG #{jig_num} {marker} Shelf {shelf + 1}, "
            f"Row {row + 1}, Column {col + 1}, Position {jig_idx + 1}\n"
        )
        
        with open(self.history_file, 'a', encoding='utf-8') as f:
            f.write(history_entry)

    def save_move_to_history(self, jig_num, source, destination):
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
            history.write(
                f"[{timestamp}] JIG #{jig_num} ~> {source_text} -> {destination_text}\n"
            )
    
    def save_state(self):
        """Zapis stanu szafy do JSON"""
        state_dict = {}
        timers_dict = {}
        insertion_times_dict = {}
        
        for pos, jig_num in self.wardrobe_state.items():
            state_dict[str(pos)] = jig_num
            if pos in self.jig_timers:
                timers_dict[str(pos)] = self.jig_timers[pos]
            if pos in self.jig_insertion_times:
                insertion_times_dict[str(pos)] = self.jig_insertion_times[pos].isoformat()
        
        with open(self.state_file, 'w', encoding='utf-8') as f:
            json.dump({
                "state": state_dict, 
                "timers": timers_dict,
                "insertion_times": insertion_times_dict
            }, f, indent=2)
    
    def load_state(self):
        """Wczytanie stanu szafy z JSON"""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    state_dict = data.get("state", {})
                    timers_dict = data.get("timers", {})
                    insertion_times_dict = data.get("insertion_times", {})
                    
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
                    
                    return state
            except:
                pass
        return {}

    def load_history(self):
        """Restore active insertion timestamps and apply recorded removals."""
        # No history means there are no JIGs to restore from a previous session.
        self.wardrobe_state.clear()
        self.jig_timers.clear()
        self.jig_insertion_times.clear()
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
                self.wardrobe_state.pop(pos_key, None)
                self.jig_timers.pop(pos_key, None)
                self.jig_insertion_times.pop(pos_key, None)
                self.expired_jigs.discard(pos_key)
            elif event["action"] == "move":
                source = event["from_position"]
                if source in self.wardrobe_state:
                    self.wardrobe_state[pos_key] = self.wardrobe_state.pop(source)
                    self.jig_insertion_times[pos_key] = self.jig_insertion_times.pop(source)
            else:
                self.wardrobe_state[pos_key] = event["jig"]
                self.jig_insertion_times[pos_key] = event["timestamp"]

if __name__ == "__main__":
    root = tk.Tk()
    app = WardrobeManager(root)
    root.mainloop()
