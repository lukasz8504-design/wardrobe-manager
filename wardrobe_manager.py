import tkinter as tk
from tkinter import messagebox
import configparser
import json
import os
from datetime import datetime
from threading import Thread
import time

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
        
        # Pliki
        self.history_file = self.config.get('FILES', 'history_file')
        self.state_file = self.config.get('FILES', 'state_file')
        
        # Maksymalizuj okno na pełny ekran
        self.root.state('zoomed')  # Windows
        self.root.resizable(True, True)
        self.root.bind('<Configure>', self.on_window_resize)
        
        # Stan timera - osobny timer dla każdego kwadratu
        self.square_timers = {}  # {pos_key: remaining_time_in_seconds}
        self.timer_threads = {}  # {pos_key: thread}
        self.current_square = None
        
        # Wczytanie stanu szafy
        self.wardrobe_state = self.load_state()
        
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
        
        # Input dla numeru kwadratu
        tk.Label(top_frame, text="Numer kwadratu:", bg='white', font=('Arial', 12, 'bold')).pack(side=tk.LEFT, padx=5)
        self.square_entry = tk.Entry(top_frame, width=10, font=('Arial', 12))
        self.square_entry.pack(side=tk.LEFT, padx=5)
        self.square_entry.bind('<Return>', lambda e: self.input_square())
        
        tk.Button(top_frame, text="Potwierdź", command=self.input_square, font=('Arial', 10)).pack(side=tk.LEFT, padx=5)
        tk.Button(top_frame, text="Wyczyść wszytko", command=self.clear_all, font=('Arial', 10)).pack(side=tk.LEFT, padx=5)
        
        # Status
        self.status_label = tk.Label(top_frame, text="Czekam na numer kwadratu...", 
                                     bg='lightyellow', font=('Arial', 10), relief=tk.SUNKEN, bd=1)
        self.status_label.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10)
        
        # Środkowa część - Półki z kanwą z scrollbarem
        canvas_frame = tk.Frame(main_frame, bg='white')
        canvas_frame.pack(fill=tk.BOTH, expand=True)
        
        # Canvas z scrollbarem
        self.canvas = tk.Canvas(canvas_frame, bg='white', highlightthickness=0)
        scrollbar = tk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas, bg='white')
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Bind mouse wheel
        self.canvas.bind_all("<MouseWheel>", self.on_mousewheel)
        self.canvas.bind_all("<Button-4>", self.on_mousewheel)
        self.canvas.bind_all("<Button-5>", self.on_mousewheel)
        
        self.shelf_buttons = {}
        
        for shelf_idx in range(self.num_shelves):
            shelf_label = tk.Label(self.scrollable_frame, text=f"Półka {shelf_idx + 1}", 
                                   bg='white', font=('Arial', 12, 'bold'))
            shelf_label.pack(pady=10)
            
            shelf_frame = tk.Frame(self.scrollable_frame, bg='lightgray', relief=tk.RAISED, bd=2)
            shelf_frame.pack(fill=tk.X, padx=10, pady=5)
            
            # Każda półka ma 2 wiersze (jeden na drugim) i 1 kolumnę
            for row_idx in range(self.num_rows):
                row_frame = tk.Frame(shelf_frame, bg='lightgray')
                row_frame.pack(fill=tk.X, padx=5, pady=5)
                
                for col_idx in range(self.num_columns):
                    # Kontener na kwadraty (dwa na sobie)
                    section_frame = tk.Frame(row_frame, bg='white', relief=tk.SUNKEN, bd=2)
                    section_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
                    
                    # Kwadraty ustawione pionowo (jeden nad drugim)
                    for square_idx in range(self.squares_per_section):
                        square_btn = tk.Button(
                            section_frame, 
                            text="", 
                            font=('Arial', 16, 'bold'),
                            bg='white', 
                            relief=tk.RAISED, 
                            bd=2,
                            width=15,
                            height=4,
                            command=lambda s=shelf_idx, r=row_idx, c=col_idx, sq=square_idx: 
                            self.select_position(s, r, c, sq)
                        )
                        
                        square_btn.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
                        
                        pos_key = (shelf_idx, row_idx, col_idx, square_idx)
                        self.shelf_buttons[pos_key] = square_btn
        
        self.update_display()
    
    def on_window_resize(self, event):
        """Obsługa zmiany rozmiaru okna"""
        pass
    
    def on_mousewheel(self, event):
        """Obsługa scrollowania myszą"""
        if event.num == 5 or event.delta < 0:
            self.canvas.yview_scroll(1, "units")
        elif event.num == 4 or event.delta > 0:
            self.canvas.yview_scroll(-1, "units")
    
    def input_square(self):
        """Wczytanie numeru kwadratu"""
        try:
            square_num = int(self.square_entry.get())
            if square_num < 0:
                messagebox.showerror("Błąd", "Numer kwadratu musi być dodatni")
                return
            
            self.current_square = square_num
            self.square_entry.delete(0, tk.END)
            self.status_label.config(text=f"Wybrałeś kwadrat #{square_num}. Teraz kliknij na pozycję na półce.", 
                                    bg='lightyellow')
        except ValueError:
            messagebox.showerror("Błąd", "Wprowadź prawidłowy numer kwadratu")
    
    def select_position(self, shelf, row, col, square):
        """Wybór pozycji na półce"""
        if self.current_square is None:
            messagebox.showwarning("Ostrzeżenie", "Najpierw wprowadź numer kwadratu")
            return
        
        pos_key = (shelf, row, col, square)
        
        # Jeśli pozycja jest już zajęta, usuń poprzedni kwadrat
        if pos_key in self.wardrobe_state:
            del self.wardrobe_state[pos_key]
            # Zatrzymaj timer dla tego kwadratu
            if pos_key in self.square_timers:
                del self.square_timers[pos_key]
            if pos_key in self.timer_threads:
                del self.timer_threads[pos_key]
        else:
            # Dodaj nowy kwadrat
            self.wardrobe_state[pos_key] = self.current_square
            
            # Inicjalizuj timer dla tego kwadratu
            self.square_timers[pos_key] = self.initial_time * 60
            
            # Zapisz do historii
            self.save_to_history(self.current_square, shelf, row, col, square)
            
            # Uruchom timer dla tego kwadratu
            self.start_square_timer(pos_key)
        
        self.save_state()
        self.update_display()
        self.current_square = None
        self.status_label.config(text="Pozycja zaktualizowana. Wpisz następny kwadrat.", bg='lightgreen')
    
    def start_square_timer(self, pos_key):
        """Uruchomienie timera dla konkretnego kwadratu"""
        if pos_key not in self.timer_threads:
            timer_thread = Thread(target=self.run_square_timer, args=(pos_key,), daemon=True)
            self.timer_threads[pos_key] = timer_thread
            timer_thread.start()
    
    def run_square_timer(self, pos_key):
        """Działanie timera dla konkretnego kwadratu"""
        while pos_key in self.square_timers and self.square_timers[pos_key] > 0:
            self.square_timers[pos_key] -= 1
            self.update_display()
            time.sleep(1)
        
        # Czasami usun timer
        if pos_key in self.square_timers and self.square_timers[pos_key] <= 0:
            messagebox.showinfo("Timer", f"Czas się skończył dla kwadratu na pozycji {pos_key}!")
            if pos_key in self.wardrobe_state:
                del self.wardrobe_state[pos_key]
                del self.square_timers[pos_key]
                self.save_state()
                self.update_display()
    
    def start_all_timers(self):
        """Uruchomienie wszystkich timerów dla kwadratów z poprzedniej sesji"""
        for pos_key in self.wardrobe_state.keys():
            if pos_key not in self.square_timers:
                self.square_timers[pos_key] = self.initial_time * 60
            self.start_square_timer(pos_key)
    
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
                square_num = self.wardrobe_state[pos_key]
                remaining_time = self.square_timers.get(pos_key, self.initial_time * 60)
                time_str = self.format_time(remaining_time)
                
                # Kolorowanie na podstawie czasu
                bg_color, text_color = self.get_color_for_time(remaining_time)
                
                btn.config(
                    text=f"#{square_num}\n{time_str}", 
                    bg=bg_color, 
                    fg=text_color
                )
            else:
                btn.config(text="", bg='white', fg='black')
    
    def clear_all(self):
        """Czyszczenie wszystkiego"""
        self.square_timers.clear()
        self.timer_threads.clear()
        self.current_square = None
        self.wardrobe_state.clear()
        self.save_state()
        self.update_display()
        self.status_label.config(text="Czyszczenie zakończone. Gotów na nowy numer.", bg='lightyellow')
        self.square_entry.delete(0, tk.END)
    
    def save_to_history(self, square_num, shelf, row, col, square_idx):
        """Zapis do pliku historii"""
        now = datetime.now()
        timestamp = now.strftime("%d-%m-%Y %H:%M:%S")
        
        history_entry = f"[{timestamp}] Kwadrat #{square_num} -> Półka {shelf + 1}, Rząd {row + 1}, Kolumna {col + 1}, Pozycja {square_idx + 1}\n"
        
        with open(self.history_file, 'a', encoding='utf-8') as f:
            f.write(history_entry)
    
    def save_state(self):
        """Zapis stanu szafy do JSON"""
        state_dict = {}
        timers_dict = {}
        
        for pos, square_num in self.wardrobe_state.items():
            state_dict[str(pos)] = square_num
            if pos in self.square_timers:
                timers_dict[str(pos)] = self.square_timers[pos]
        
        with open(self.state_file, 'w', encoding='utf-8') as f:
            json.dump({"state": state_dict, "timers": timers_dict}, f, indent=2)
    
    def load_state(self):
        """Wczytanie stanu szafy z JSON"""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    state_dict = data.get("state", {})
                    timers_dict = data.get("timers", {})
                    
                    state = {}
                    for pos_str, square_num in state_dict.items():
                        pos = eval(pos_str)
                        state[pos] = square_num
                        
                        # Wczytaj timery
                        if pos_str in timers_dict:
                            self.square_timers[pos] = timers_dict[pos_str]
                        else:
                            self.square_timers[pos] = self.initial_time * 60
                    
                    return state
            except:
                pass
        return {}

if __name__ == "__main__":
    root = tk.Tk()
    app = WardrobeManager(root)
    root.mainloop()
