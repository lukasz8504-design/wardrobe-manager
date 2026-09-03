import tkinter as tk
from tkinter import messagebox
import configparser
import json
import os
from datetime import datetime
import re
from threading import Thread
import time


HISTORY_TIMESTAMP_FORMAT = "%d-%m-%Y %H:%M:%S"
UNKNOWN_OPERATOR_ID = "BRAK"
OPERATOR_ID_PATTERN = re.compile(r"^[A-Za-z0-9]{4}$")


def calculate_remaining_time(insertion_time, initial_minutes, current_time=None):
    """Return the remaining timer seconds based on the insertion timestamp."""
    current_time = current_time or datetime.now()
    return max(0, initial_minutes * 60 - (current_time - insertion_time).total_seconds())


def parse_history_line(line):
    """Parse a history line into its event data, or return None for old/invalid lines."""
    pattern = (
        r"^\[(?P<timestamp>[^\]]+)\]\s+JIG\s+#(?P<jig>\d+)\s+"
        r"(?:\|\s+OPERATOR\s+ID:\s+(?P<operator_id>[A-Za-z0-9]{4})\s+)?"
        r"(?P<action>->|<-)\s+Półka\s+(?P<shelf>\d+),\s+Rząd\s+(?P<row>\d+),\s+"
        r"Kolumna\s+(?P<col>\d+),\s+Pozycja\s+(?P<position>\d+)"
    )
    match = re.match(pattern, line.strip())
    if not match:
        return None
    try:
        timestamp = datetime.strptime(match.group("timestamp"), HISTORY_TIMESTAMP_FORMAT)
    except ValueError:
        return None
    return {
        "timestamp": timestamp,
        "jig": int(match.group("jig")),
        "operator_id": match.group("operator_id"),
        "position": (
            int(match.group("shelf")) - 1,
            int(match.group("row")) - 1,
            int(match.group("col")) - 1,
            int(match.group("position")) - 1,
        ),
        "action": "insert" if match.group("action") == "->" else "remove",
    }


def validate_operator_id(operator_id):
    """Return a cleaned operator id or raise ValueError when it is invalid."""
    normalized_operator_id = operator_id.strip()
    if not OPERATOR_ID_PATTERN.fullmatch(normalized_operator_id):
        raise ValueError("OPERATOR ID musi mieć dokładnie 4 znaki alfanumeryczne")
    return normalized_operator_id


def format_history_entry(jig_num, shelf, row, col, jig_idx, action="insert", operator_id=None, timestamp=None):
    """Build a single history entry line in the current history format."""
    timestamp = (timestamp or datetime.now()).strftime(HISTORY_TIMESTAMP_FORMAT)
    marker = "->" if action == "insert" else "<-"
    operator_fragment = f" | OPERATOR ID: {operator_id}" if operator_id else ""
    return (
        f"[{timestamp}] JIG #{jig_num}{operator_fragment} {marker} "
        f"Półka {shelf + 1}, Rząd {row + 1}, Kolumna {col + 1}, Pozycja {jig_idx + 1}\n"
    )


class WardrobeManager:
    def __init__(self, root):
        self.root = root
        self.root.title("Wardrobe Manager - Szafa")
        
        # Wczytanie konfiguracji
        self.config = configparser.ConfigParser()
        self.config.read('config.ini')
        
        # Parametry szafy
        self.num_shelves = self.config.getint('WARDROBE', 'num_shelves')
        self.num_rows = self.config.getint('WARDROBE', 'num_rows')
        self.num_columns = self.config.getint('WARDROBE', 'num_columns')
        self.squares_per_section = self.config.getint('WARDROBE', 'squares_per_section')
        
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
        self.empty_bg = self.config.get('COLORS', 'empty_bg', fallback='white')
        self.empty_text = self.config.get('COLORS', 'empty_text', fallback='black')
        
        # Wygląd
        self.jig_width = self.config.getint('APPEARANCE', 'square_width')
        self.jig_height = self.config.getint('APPEARANCE', 'square_height')
        self.jig_font_size = self.config.getint('APPEARANCE', 'square_font_size')
        
        # Pliki
        self.history_file = self.config.get('FILES', 'history_file')
        self.state_file = self.config.get('FILES', 'state_file')
        
        # Maksymalizuj okno
        self.root.state('zoomed')  # Windows
        self.root.resizable(True, True)
        
        # Stan timera - osobny timer dla każdego JIG
        self.jig_timers = {}  # {pos_key: remaining_time_in_seconds}
        self.jig_insertion_times = {}  # {pos_key: insertion_timestamp}
        self.timer_threads = {}  # {pos_key: thread}
        self.expired_jigs = set()
        self.current_jig = None
        self.current_operator_id = None
        self.jig_operator_ids = {}
        self.input_stage = "jig"
        
        # Wczytanie stanu szafy
        self.wardrobe_state = self.load_state()
        self.load_history()
        
        # GUI
        self.setup_ui()
        self.start_all_timers()
        
    def setup_ui(self):
        """Tworzenie interfejsu użytkownika"""
        # Główna ramka
        main_frame = tk.Frame(self.root, bg='white')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Górna część - Input
        top_frame = tk.Frame(main_frame, bg='white')
        top_frame.pack(fill=tk.X, pady=10)
        
        # Input dla numeru JIG
        tk.Label(top_frame, text="Numer JIG:", bg='white', font=('Arial', 12, 'bold')).pack(side=tk.LEFT, padx=5)
        self.jig_entry = tk.Entry(top_frame, width=10, font=('Arial', 12))
        self.jig_entry.pack(side=tk.LEFT, padx=5)
        self.jig_entry.bind('<Return>', lambda e: self.input_jig())

        tk.Label(top_frame, text="OPERATOR ID:", bg='white', font=('Arial', 12, 'bold')).pack(side=tk.LEFT, padx=5)
        self.operator_entry = tk.Entry(top_frame, width=10, font=('Arial', 12))
        self.operator_entry.pack(side=tk.LEFT, padx=5)
        self.operator_entry.bind('<Return>', lambda e: self.input_operator())
         
        tk.Button(top_frame, text="Potwierdź", command=self.confirm_current_step, font=('Arial', 10)).pack(side=tk.LEFT, padx=5)
        tk.Button(top_frame, text="Wyczyść wszystko", command=self.clear_all, font=('Arial', 10)).pack(side=tk.LEFT, padx=5)
        
        # Status
        self.status_label = tk.Label(top_frame, text="Czekam na numer JIG...", 
                                     bg='lightyellow', font=('Arial', 10), relief=tk.SUNKEN, bd=1)
        self.status_label.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10)
        
        # Środkowa część - Półki bez scrollbara
        shelves_frame = tk.Frame(main_frame, bg='white')
        shelves_frame.pack(fill=tk.BOTH, expand=True)
        
        self.shelf_buttons = {}
        
        for shelf_idx in range(self.num_shelves):
            shelf_label = tk.Label(shelves_frame, text=f"Półka {shelf_idx + 1}", 
                                   bg='white', font=('Arial', 10, 'bold'))
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
        self.set_input_stage("jig")

    def confirm_current_step(self):
        """Confirm the currently expected input step."""
        if self.input_stage == "jig":
            self.input_jig()
        elif self.input_stage == "operator":
            self.input_operator()
        else:
            self.status_label.config(
                text="Dane zapisane. Kliknij pozycję na półce, aby zakończyć operację.",
                bg='lightyellow'
            )

    def set_input_stage(self, stage, status_text=None, status_bg='lightyellow'):
        """Update the active input stage and keep entry fields in sync with it."""
        self.input_stage = stage
        self.jig_entry.config(state=tk.NORMAL if stage == "jig" else tk.DISABLED)
        self.operator_entry.config(state=tk.NORMAL if stage == "operator" else tk.DISABLED)

        if stage == "jig":
            self.jig_entry.focus_set()
        elif stage == "operator":
            self.operator_entry.focus_set()
        elif hasattr(self, "root"):
            self.root.focus_set()

        if status_text is None:
            if stage == "jig":
                status_text = "Czekam na numer JIG..."
            elif stage == "operator":
                status_text = f"JIG #{self.current_jig} zapisany. Wprowadź OPERATOR ID (dokładnie 4 znaki)."
            else:
                status_text = (
                    f"JIG #{self.current_jig} / OPERATOR ID {self.current_operator_id}. "
                    "Kliknij pozycję na półce."
                )

        self.status_label.config(text=status_text, bg=status_bg)
     
    def input_jig(self):
        """Wczytanie numeru JIG"""
        if self.input_stage != "jig":
            if self.input_stage == "operator":
                self.status_label.config(
                    text=f"JIG #{self.current_jig} zapisany. Wprowadź OPERATOR ID (dokładnie 4 znaki).",
                    bg='lightyellow'
                )
            else:
                self.status_label.config(
                    text="Dane zapisane. Kliknij pozycję na półce, aby zakończyć operację.",
                    bg='lightyellow'
                )
            return

        try:
            jig_num = int(self.jig_entry.get())
            if jig_num < 0:
                messagebox.showerror("Błąd", "Numer JIG musi być dodatni")
                return
             
            self.current_jig = jig_num
            self.jig_entry.delete(0, tk.END)
            self.set_input_stage("operator")
        except ValueError:
            messagebox.showerror("Błąd", "Wprowadź prawidłowy numer JIG")

    def input_operator(self):
        """Wczytanie identyfikatora operatora."""
        if self.input_stage != "operator":
            if self.input_stage == "jig":
                self.status_label.config(text="Najpierw wprowadź numer JIG.", bg='lightyellow')
            else:
                self.status_label.config(
                    text="Dane zapisane. Kliknij pozycję na półce, aby zakończyć operację.",
                    bg='lightyellow'
                )
            return

        try:
            self.current_operator_id = validate_operator_id(self.operator_entry.get())
        except ValueError as exc:
            messagebox.showerror("Błąd", str(exc))
            return

        self.operator_entry.delete(0, tk.END)
        self.set_input_stage("position")
     
    def select_position(self, shelf, row, col, jig):
        """Wybór pozycji na półce"""
        if self.current_jig is None:
            messagebox.showwarning("Ostrzeżenie", "Najpierw wprowadź numer JIG")
            return
        if self.current_operator_id is None:
            messagebox.showwarning("Ostrzeżenie", "Najpierw wprowadź OPERATOR ID")
            return
        
        pos_key = (shelf, row, col, jig)
        
        # Jeśli pozycja jest już zajęta, usuń poprzedni JIG
        if pos_key in self.wardrobe_state:
            self.save_to_history(
                self.wardrobe_state[pos_key],
                shelf,
                row,
                col,
                jig,
                action="remove",
                operator_id=self.jig_operator_ids.get(pos_key, UNKNOWN_OPERATOR_ID),
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
            self.jig_operator_ids.pop(pos_key, None)
        else:
            # Dodaj nowy JIG
            self.wardrobe_state[pos_key] = self.current_jig
            self.jig_operator_ids[pos_key] = self.current_operator_id
             
            # Inicjalizuj timer dla tego JIG
            self.jig_timers[pos_key] = self.initial_time * 60
            
            # Zapisz czas włożenia JIG
            self.jig_insertion_times[pos_key] = datetime.now()
             
            # Zapisz do historii
            self.save_to_history(
                self.current_jig,
                shelf,
                row,
                col,
                jig,
                action="insert",
                operator_id=self.current_operator_id,
            )
             
            # Uruchom timer dla tego JIG
            self.start_jig_timer(pos_key)
        
        self.save_state()
        self.update_display()
        self.current_jig = None
        self.current_operator_id = None
        self.set_input_stage(
            "jig",
            status_text="Pozycja zaktualizowana. Wpisz następny numer JIG.",
            status_bg='lightgreen'
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
            time.sleep(1)
        
        # Czasami usun timer
        if pos_key in self.jig_timers and self.jig_timers[pos_key] <= 0:
            messagebox.showinfo("Timer", f"Czas się skończył dla JIG na pozycji {pos_key}!")
            self.expired_jigs.add(pos_key)
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
                    time_str += "\nNIE WYJĘTY"
                
                # Kolorowanie na podstawie czasu
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
                jig_num,
                pos_key[0],
                pos_key[1],
                pos_key[2],
                pos_key[3],
                action="remove",
                operator_id=self.jig_operator_ids.get(pos_key, UNKNOWN_OPERATOR_ID),
            )
        self.jig_timers.clear()
        self.jig_insertion_times.clear()
        self.timer_threads.clear()
        self.current_jig = None
        self.current_operator_id = None
        self.jig_operator_ids.clear()
        self.wardrobe_state.clear()
        self.save_state()
        self.update_display()
        self.jig_entry.delete(0, tk.END)
        self.operator_entry.delete(0, tk.END)
        self.set_input_stage(
            "jig",
            status_text="Czyszczenie zakończone. Gotów na nowy numer JIG.",
            status_bg='lightyellow'
        )
     
    def save_to_history(self, jig_num, shelf, row, col, jig_idx, action="insert", operator_id=None):
        """Zapis do pliku historii"""
        with open(self.history_file, 'a', encoding='utf-8') as f:
            f.write(
                format_history_entry(
                    jig_num, shelf, row, col, jig_idx, action=action, operator_id=operator_id
                )
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
        self.jig_operator_ids.clear()

        if not os.path.exists(self.history_file):
            return
        try:
            with open(self.history_file, "r", encoding="utf-8") as history:
                events = [parse_history_line(line) for line in history]
        except OSError:
            return

        latest_events = {}
        for event in events:
            if event is not None and (
                event["position"] not in latest_events
                or event["timestamp"] >= latest_events[event["position"]]["timestamp"]
            ):
                latest_events[event["position"]] = event

        for pos_key, event in latest_events.items():
            if event["action"] == "remove":
                if pos_key in self.wardrobe_state:
                    del self.wardrobe_state[pos_key]
                self.jig_timers.pop(pos_key, None)
                self.jig_insertion_times.pop(pos_key, None)
                self.expired_jigs.discard(pos_key)
                self.jig_operator_ids.pop(pos_key, None)
            else:
                self.wardrobe_state[pos_key] = event["jig"]
                self.jig_insertion_times[pos_key] = event["timestamp"]
                self.jig_operator_ids[pos_key] = event["operator_id"] or UNKNOWN_OPERATOR_ID

if __name__ == "__main__":
    root = tk.Tk()
    app = WardrobeManager(root)
    root.mainloop()
