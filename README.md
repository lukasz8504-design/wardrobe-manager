# Wardrobe Manager - Aplikacja do zarządzania szafą

Aplikacja do zarządzania szafą z systemem timerów dla każdego kwadratu i historią wprowadzanych danych.

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
- `num_columns` - Liczba kolumn (zawsze 1 - kwadraty są ustawione jeden nad drugim)
- `squares_per_section` - Liczba kwadratów w każdej pozycji (domyślnie 2 - jeden za drugim)

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

## Użytkowanie

1. **Wpisz numer kwadratu** w pole tekstowe i naciśnij Enter lub kliknij "Potwierdź"
2. **Kliknij na pozycję na półce** aby umieścić kwadrat na wybranej pozycji
3. **Timer** automatycznie uruchomi się dla każdego kwadratu osobno - liczby od 100 minut do 0
4. **Każdy kwadrat wyświetla**:
   - Numer kwadratu
   - Pozostały czas (MM:SS)
   - Kolor zmieniający się na podstawie czasu:
     - Szary (normalny) - gdy pozostało więcej niż 5 minut
     - Pomarańczowy - gdy pozostało od 5 minut do 1 minuty
     - Czerwony - gdy pozostało od 1 minuty do 0

5. **Historia** wszystkich operacji jest zapisywana w pliku `history.txt` ze znacznikami czasowymi
6. **Stan szafy** jest zapisywany w pliku `wardrobe_state.json` wraz z czasami dla każdego kwadratu i przywracany przy restarcie aplikacji

## Nowe cechy aplikacji (v2)

✅ **Responsywny interfejs** - Aplikacja automatycznie dostosowuje się do rozdzielczości ekranu  
✅ **Pełny ekran** - Aplikacja uruchamia się w pełnym ekranie z możliwością scrollowania  
✅ **Kwadraty ułożone jedno na drugim** - Każda pozycja wyświetla 2 kwadraty ustawione pionowo (jeden za drugim)  
✅ **Indywidualne timery** - Każdy kwadrat ma własny timer liczący niezależnie od innych  
✅ **Wyświetlanie czasu na każdym kwadracie** - Timer widoczny bezpośrednio na każdej pozycji z kolorystką  
✅ **Scrollowanie** - Możliwość przewijania listy półek za pomocą scrollbara lub kółka myszy  

## Pliki

- `wardrobe_manager.py` - Główny plik aplikacji
- `config.ini` - Plik konfiguracyjny
- `history.txt` - Historia wprowadzonych kwadratów (tworzona automatycznie)
- `wardrobe_state.json` - Stan obecny szafy z timerami (tworzony automatycznie)
- `README.md` - Ten plik

## Uwagi

- Kliknięcie na zajętą pozycję usuwa kwadrat z tej pozycji (i zatrzymuje jego timer)
- Aplikacja automatycznie zapisuje historię i stan szafy (razem z timerami dla każdego kwadratu)
- Stan szafy i czasy są przywracane przy każdym uruchomieniu aplikacji
- Wszystkie czasy są w formacie MM:SS (minuty:sekundy)
- Aplikacja obsługuje scrollowanie myszą

## Autor

Lukasz8504
