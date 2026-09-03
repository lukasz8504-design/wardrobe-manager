# Wardrobe Manager - Aplikacja do zarządzania szafą

Aplikacja do zarządzania szafą z systemem timerów dla każdego JIG i historią wprowadzanych danych.

## Wymagania

- Python 3.7+
- Biblioteka `tkinter` (zwykle wbudowana w Python)

## Instalacja i uruchomienie

### Windows

1. Pobierz repozytorium
2. Otwórz terminal w folderze aplikacji
3. Uruchom aplikację:
```bash
python wardrobe_manager.py
```

### macOS / Linux

1. Pobierz repozytorium
2. Otwórz terminal w folderze aplikacji
3. Uruchom aplikację:
```bash
python3 wardrobe_manager.py
```

## Konfiguracja

Wszystkie ustawienia znajdują się w pliku `config.ini`:

### [WARDROBE]
- `num_shelves` - Liczba półek w szafie (domyślnie 3)
- `num_rows` - Liczba rzędów na jednej półce (domyślnie 3)
- `num_columns` - Liczba kolumn (zawsze 1 - JIG są ustawione jeden nad drugim)
- `squares_per_section` - Liczba JIG w każdej pozycji (domyślnie 2 - jeden za drugim)

### [TIMER]
- `initial_time` - Czas początkowy w minutach (domyślnie 100)
- `orange_threshold` - Czas rozpoczęcia pomarańczowego tła (domyślnie 5 minut)
- `red_threshold` - Czas rozpoczęcia czerwonego tła (domyślnie 1 minuta)

### [COLORS]
- Kolory tła i tekstu dla różnych stanów timera
- Format RGB (hex): #RRGGBB

### [FILES]
- `history_file` - Ścieżka do pliku historii (domyślnie `history.txt`)
- `state_file` - Ścieżka do pliku stanu szafy (domyślnie `wardrobe_state.json`)

### [APPEARANCE]
- `square_width` - Szerokość JIG w znakach (domyślnie 8)
- `square_height` - Wysokość JIG w linijkach (domyślnie 2)
- `square_font_size` - Rozmiar czcionki dla numerów JIG (domyślnie 10)

## Użytkowanie

1. **Wpisz numer JIG** w pole tekstowe i naciśnij Enter lub kliknij "Potwierdź"
2. **Kliknij na pozycję na półce** aby umieścić JIG na wybranej pozycji
3. **Timer** automatycznie uruchomi się dla każdego JIG osobno - liczby od 100 minut do 0
4. **Każdy JIG wyświetla**:
   - Numer JIG
   - Pozostały czas (MM:SS)
   - Kolor zmieniający się na podstawie czasu:
     - Szary (normalny) - gdy pozostało więcej niż 5 minut
     - Pomarańczowy - gdy pozostało od 5 minut do 1 minuty
     - Czerwony - gdy pozostało od 1 minuty do 0

5. **Historia** wszystkich operacji jest zapisywana w pliku `history.txt` ze znacznikami czasowymi. `->` oznacza włożenie, a `<-` wyjęcie JIG-a.
6. **Stan szafy** jest zapisywany w pliku `wardrobe_state.json` wraz z czasami dla każdego JIG i przywracany przy restarcie aplikacji
7. **Porównanie czasów** - Przy restarcie aplikacji system odczytuje ostatnie zdarzenie z historii, porównuje czas włożenia z aktualnym czasem i automatycznie oblicza pozostały czas dla każdego JIG. Po upływie `initial_time` JIG pozostaje widoczny jako `NIE WYJĘTY`, dopóki nie zostanie ręcznie wyjęty.

## Nowe cechy aplikacji (v3)

✅ **Responsywny interfejs** - Aplikacja automatycznie dostosowuje się do rozdzielczości ekranu  
✅ **Pełny ekran** - Aplikacja uruchamia się w pełnym ekranie bez scrollowania  
✅ **JIG ustawione jedno na drugim** - Każda pozycja wyświetla 2 JIG ustawione pionowo (jeden za drugim)  
✅ **Indywidualne timery** - Każdy JIG ma własny timer liczący niezależnie od innych  
✅ **Wyświetlanie czasu na każdym JIG** - Timer widoczny bezpośrednio na każdej pozycji z kolorystką  
✅ **Zmniejszony rozmiar JIG** - Wszystkie półki widoczne bez konieczności scrollowania  
✅ **Porównanie czasów przy restarcie** - System automatycznie oblicza pozostały czas dla każdego JIG na podstawie czasu włożenia  
✅ **Terminologia JIG** - Całe słowo "kwadrat" zastąpione terminem "JIG"

## Pliki

- `wardrobe_manager.py` - Główny plik aplikacji
- `config.ini` - Plik konfiguracyjny
- `history.txt` - Historia wprowadzonych JIG (tworzona automatycznie)
- `wardrobe_state.json` - Stan obecny szafy z timerami i czasami włożenia JIG (tworzony automatycznie)
- `README.md` - Ten plik

## Uwagi

- Kliknięcie na zajętą pozycję usuwa JIG z tej pozycji (i zatrzymuje jego timer)
- Aplikacja automatycznie zapisuje historię i stan szafy (razem z timerami dla każdego JIG)
- Stan szafy i czasy są przywracane przy każdym uruchomieniu aplikacji z uwzględnieniem upływu czasu
- Wszystkie czasy są w formacie MM:SS (minuty:sekundy)
- Jeśli aplikacja zostanie zamknięta i ponownie uruchomiona, system automatycznie obliczy jak dużo czasu upłynęło i dostosuje timery JIG

## Autor

Lukasz8504
