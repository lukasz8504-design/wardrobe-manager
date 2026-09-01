# Wardrobe Manager - Aplikacja do zarządzania szafą

Aplikacja do zarządzania szafą z systemem timera i historią wprowadzanych kwadratów.

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
- `num_columns` - Liczba kolumn na jednej półce (domyślnie 3)
- `squares_per_section` - Liczba kwadratów w każdej części (domyślnie 2)

### [TIMER]
- `initial_time` - Czas początkowy w minutach (domyślnie 100)
- `orange_threshold` - Czas rozpoczęcia pomarańczowego tła (domyślnie 5 minut)
- `red_threshold` - Czas rozpoczęcia czerwonego tła (domyślnie 1 minuta)

### [COLORS]
- Kolory tła i tekstu dla różnych stanów timera
- Format RGB (hex): #RRGGBB

### [APPEARANCE]
- Rozmiar okna i przycisków
- Rozmiar czcionek

### [FILES]
- `history_file` - Ścieżka do pliku historii (domyślnie `history.txt`)
- `state_file` - Ścieżka do pliku stanu szafy (domyślnie `wardrobe_state.json`)

## Użytkowanie

1. **Wpisz numer kwadratu** w pole tekstowe i naciśnij Enter lub kliknij "Potwierdź"
2. **Kliknij na półkę** aby umieścić kwadrat na wybranej pozycji
3. **Timer** automatycznie uruchomi się liczyć od 100 minut do 0
4. **Kolory timera**:
   - Normalny (szary) - gdy pozostało więcej niż 5 minut
   - Pomarańczowy - gdy pozostało od 5 minut do 1 minuty
   - Czerwony - gdy pozostało od 1 minuty do 0

5. **Historia** wszystkich operacji jest zapisywana w pliku `history.txt` ze znacznikami czasowymi
6. **Stan szafy** jest zapisywany w pliku `wardrobe_state.json` i przywracany przy restarcie aplikacji

## Pliki

- `wardrobe_manager.py` - Główny plik aplikacji
- `config.ini` - Plik konfiguracyjny
- `history.txt` - Historia wprowadzonych kwadratów (tworzona automatycznie)
- `wardrobe_state.json` - Stan obecny szafy (tworzyony automatycznie)
- `README.md` - Ten plik

## Uwagi

- Kliknięcie na zajętą pozycję usuwa kwadrat z tej pozycji
- Aplikacja automatycznie zapisuje historię i stan szafy
- Stan szafy jest przywracany przy każdym uruchomieniu aplikacji
- Wszystkie czasy są w formacie MM:SS (minuty:sekundy)

## Autor

Lukasz8504
