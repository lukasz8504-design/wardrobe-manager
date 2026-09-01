import tkinter as tk
from tkinter import messagebox, simpledialog
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
        
        # Wygląd
        self.window_width = self.config.getint('APPEARANCE', 'window_width')
        self.window_height = self.config.getint('APPEARANCE', 'window_height')
        self.button_width = self.config.getint('APPEARANCE', 'button_width')
        self.button_height = self.config.getint('APPEARANCE', 'button_height')
        self.timer_font_size = self.config.getint('APPEARANCE', 'timer_font_size')
        self.square_font_size = self.config.getint('APPEARANCE', 'square_font_size')
        
        # Pliki
        self.history_file = self.config.get('FILES', 'history_file')
        self.state_file = self.config.get('FILES', 'state_file')
        
        # Ustawienia okna
        self.root.geometry(f"{self.window_width}x{self.window_height}")
        self.root.resizable(False, False)
        
        # Stan timera
        self.timer_running = False
        self.remaining_time = self.initial_time * 60  # konwersja na sekundy
        self.current_square = None
        self.current_position = None
        
        # Wczytanie stanu szafy
        self.wardrobe_state = self.load_state()
        
        # GUI
        self.setup_ui()
        
    def setup_ui(self):
        """Tworzenie interfejsu użytkownika"""
        # Główna ramka
        main_frame = tk.Frame(self.root, bg='white')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Górna część - Input + Timer
        top_frame = tk.Frame(main_frame, bg='white')
        top_frame.pack(fill=tk.X, pady=10)
        
        # Input dla numeru kwadratu
        tk.Label(top_frame, text="Numer kwadratu:", bg='white', font=('Arial', 12)).pack(side=tk.LEFT, padx=5)
        self.square_entry = tk.Entry(top_frame, width=10, font=('Arial', 12))
        self.square_entry.pack(side=tk.LEFT, padx=5)
        self.square_entry.bind('<Return>', lambda e: self.input_square())
        
        tk.Button(top_frame, text="Potwierdź", command=self.input_square).pack(side=tk.LEFT, padx=5)
        tk.Button(top_frame, text="Wyczyść", command=self.clear_all).pack(side=tk.LEFT, padx=5)
        
        # Timer
        self.timer_label = tk.Label(top_frame, text="", font=('Arial', self.timer_font_size, 'bold'), 
                                     bg=self.normal_bg, fg=self.normal_text, padx=20, pady=10)
        self.timer_label.pack(side=tk.RIGHT, padx=20)
        
        # Środkowa część - Półki
        shelves_frame = tk.Frame(main_frame, bg='white')
        shelves_frame.pack(fill=tk.BOTH, expand=True)
        
        self.shelf_buttons = {}
        
        for shelf_idx in range(self.num_shelves):
            shelf_label = tk.Label(shelves_frame, text=f"Półka {shelf_idx + 1}", 
                                   bg='white', font=('Arial', 10, 'bold'))
            shelf_label.pack(pady=5)
            
            shelf_frame = tk.Frame(shelves_frame, bg='lightgray', relief=tk.RAISED, bd=2)
            shelf_frame.pack(fill=tk.X, padx=10, pady=5)
            
            for row_idx in range(self.num_rows):
                row_frame = tk.Frame(shelf_frame, bg='lightgray')
                row_frame.pack(fill=tk.X, padx=5, pady=5)
                
                for col_idx in range(self.num_columns):
                    section_frame = tk.Frame(row_frame, bg='white', relief=tk.SUNKEN, bd=1)
                    section_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=3, pady=3)
                    
                    # Podział na kwadraty
                    squares_frame = tk.Frame(section_frame, bg='white')
                    squares_frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
                    
                    for square_idx in range(self.squares_per_section):
                        square_btn = tk.Button(squares_frame, text="", 
                                              width=int(self.button_width/8), 
                                              height=int(self.button_height/20),
                                              font=('Arial', self.square_font_size),
                                              bg='white', relief=tk.RAISED, bd=1,
                                              command=lambda s=shelf_idx, r=row_idx, c=col_idx, sq=square_idx: 
                                              self.select_position(s, r, c, sq))
                        
                        square_btn.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=1, pady=1)
                        
                        pos_key = (shelf_idx, row_idx, col_idx, square_idx)
                        self.shelf_buttons[pos_key] = square_btn
        
        # Dolna część - Status
        self.status_label = tk.Label(main_frame, text="Czekam na numer kwadratu...", 
                                     bg='lightyellow', font=('Arial', 10), relief=tk.SUNKEN, bd=1)
        self.status_label.pack(fill=tk.X, pady=10)
        
        self.update_display()
    
    def input_square(self):
        """Wczytanie numeru kwadratu"""
        try:
            square_num = int(self.square_entry.get())
            if square_num < 0:
                messagebox.showerror("Błąd", "Numer kwadratu musi być dodatni")
                return
            
            self.current_square = square_num
            self.square_entry.delete(0, tk.END)
            self.status_label.config(text=f"Wybrałeś kwadrat #{square_num}. Teraz kliknij na półkę.", 
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
        else:
            # Dodaj nowy kwadrat
            self.wardrobe_state[pos_key] = self.current_square
            
            # Zapisz do historii
            self.save_to_history(self.current_square, shelf, row, col, square)
            
            # Uruchom timer
            self.start_timer()
        
        self.save_state()
        self.update_display()
        self.current_square = None
        self.status_label.config(text=f"Kwadrat #{self.current_square} umieszczony na półce", bg='lightgreen')
    
    def start_timer(self):
        """Uruchomienie timera"""
        if not self.timer_running:
            self.timer_running = True
            self.remaining_time = self.initial_time * 60
            timer_thread = Thread(target=self.run_timer, daemon=True)
            timer_thread.start()
    
    def run_timer(self):
        """Działanie timera"""
        while self.timer_running and self.remaining_time > 0:
            self.remaining_time -= 1
            self.update_timer_display()
            time.sleep(1)
        
        if self.remaining_time <= 0:
            self.timer_running = False
            self.remaining_time = 0
            messagebox.showinfo("Timer", "Czas się skończył!")
            self.clear_all()
    
    def update_timer_display(self):
        """Aktualizacja wyświetlania timera"""
        minutes = self.remaining_time // 60
        seconds = self.remaining_time % 60
        time_str = f"{minutes:02d}:{seconds:02d}"
        
        # Wybór koloru na podstawie pozostałego czasu (w minutach)
        remaining_minutes = self.remaining_time / 60
        
        if remaining_minutes <= self.red_threshold:
            bg_color = self.red_bg
            text_color = self.red_text
        elif remaining_minutes <= self.orange_threshold:
            bg_color = self.orange_bg
            text_color = self.orange_text
        else:
            bg_color = self.normal_bg
            text_color = self.normal_text
        
        self.timer_label.config(text=time_str, bg=bg_color, fg=text_color)
    
    def update_display(self):
        """Aktualizacja wyświetlania przycisków"""
        for pos_key, btn in self.shelf_buttons.items():
            if pos_key in self.wardrobe_state:
                square_num = self.wardrobe_state[pos_key]
                btn.config(text=str(square_num), bg='lightblue', fg='black')
            else:
                btn.config(text="", bg='white', fg='black')
        
        self.update_timer_display()
    
    def clear_all(self):
        """Czyszczenie wszystkiego"""
        self.timer_running = False
        self.remaining_time = self.initial_time * 60
        self.current_square = None
        self.wardrobe_state.clear()
        self.save_state()
        self.update_display()
        self.status_label.config(text="Czyszczenie zakończone. Gotów na nowy numer.", bg='lightyellow')
    
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
        for pos, square_num in self.wardrobe_state.items():
            state_dict[str(pos)] = square_num
        
        with open(self.state_file, 'w', encoding='utf-8') as f:
            json.dump(state_dict, f, indent=2)
    
    def load_state(self):
        """Wczytanie stanu szafy z JSON"""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    state_dict = json.load(f)
                    state = {}
                    for pos_str, square_num in state_dict.items():
                        pos = eval(pos_str)
                        state[pos] = square_num
                    return state
            except:
                pass
        return {}

if __name__ == "__main__":
    root = tk.Tk()
    app = WardrobeManager(root)
    root.mainloop()
