# Oven Manager - Aplikacja do zarządzania piecem

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
python oven_manager.py
```

### macOS / Linux

1. Pobierz repozytorium
2. Otwórz terminal w folderze aplikacji
3. Uruchom aplikację:
```bash
python3 oven_manager.py
```

## Konfiguracja

Wszystkie ustawienia znajdują się w pliku `config.toml`:

Można je również edytować graficznie z poziomu aplikacji przez przycisk **Settings**. Po zapisaniu ustawień uruchom aplikację ponownie, aby zastosować zmiany układu i wyglądu.

### [OVEN]
- `num_shelves` - Liczba półek w piecu (domyślnie 3)
- `num_rows` - Liczba rzędów na jednej półce (domyślnie 1)
- `num_columns` - Liczba kolumn na półce (domyślnie 3)
- `jigs_per_section` - Liczba JIG w każdej sekcji (domyślnie 2 - jeden nad drugim)

### [WINDOW]
- `width`, `height` - Szerokość i wysokość okna aplikacji. Aktualny rozmiar okna jest zapisywany automatycznie i przywracany po ponownym uruchomieniu.

### [TIMER]
- `initial_time` - Czas początkowy w minutach (domyślnie 100)
- `orange_threshold` - Czas rozpoczęcia pomarańczowego tła (domyślnie 5 minut)
- `red_threshold` - Czas rozpoczęcia czerwonego tła (domyślnie 1 minuta)

### [COLORS]
- Kolory tła i tekstu dla różnych stanów timera
- Format RGB (hex): #RRGGBB

### [FILES]
- `history_file` - Ścieżka do pliku historii (domyślnie `history.txt`)
- `state_file` - Ścieżka do pliku stanu pieca (domyślnie `oven_state.json`)

### [APPEARANCE]
- `jig_width` - Szerokość JIG w znakach (domyślnie 8)
- `jig_height` - Wysokość JIG w linijkach (domyślnie 2)
- `jig_font_size` - Rozmiar czcionki dla numerów JIG (domyślnie 10)

### [JIG_DISPLAY]
- `jig_number_color`, `jig_number_font_size` - Kolor i rozmiar numeru JIG.
- `remaining_time_color`, `remaining_time_font_size` - Kolor i rozmiar pozostałego czasu.
- `processing_text`, `processing_text_color`, `processing_text_font_size` - Tekst procesu, np. `W trakcie wygrzewania`, oraz jego wygląd.
- `not_removed_text`, `not_removed_text_color`, `not_removed_text_font_size` - Tekst wygasłego JIG-a oraz jego wygląd.

### [OPERATORS]
- `operator_1234 = "#1E90FF"` - Numer operatora i przypisany mu kolor JIG-ów.
- W **Settings** wpisz czteroznakowy numer, wybierz kolor i kliknij **Add**. Lista operatorów wraz z polami kolorów jest zapisywana po kliknięciu **Save settings**.

### [OVEN_TITLE] i [SHELF_LABELS]
- `text`, `color`, `font_size` - Nazwa pieca nad wszystkimi półkami oraz jej wygląd.
- `shelf_1`, `shelf_2`, ... - Indywidualne nazwy półek.
- `color`, `font_size` w `[SHELF_LABELS]` - Wspólny kolor i rozmiar czcionki nazw półek.

## Użytkowanie

1. **Wpisz numer JIG i numer operatora** w pola tekstowe, a następnie naciśnij Enter lub kliknij "Potwierdź". Numer operatora jest wymagany i musi zawierać dokładnie 4 znaki.
2. **Kliknij na pozycję na półce** aby umieścić JIG na wybranej pozycji
3. **Timer** automatycznie uruchomi się dla każdego JIG osobno - liczby od 100 minut do 0
4. **Każdy JIG wyświetla**:
   - Numer JIG
   - Konfigurowalny komunikat procesu
   - Pozostały czas (MM:SS)
   - Kolor zmieniający się na podstawie czasu:
     - Szary (normalny) - gdy pozostało więcej niż 5 minut
     - Pomarańczowy - gdy pozostało od 5 minut do 1 minuty
     - Czerwony - gdy pozostało od 1 minuty do 0

5. **Historia** wszystkich operacji jest zapisywana w pliku `history.txt` ze znacznikami czasowymi. `->` oznacza włożenie, a `<-` wyjęcie JIG-a.
6. **Stan pieca** jest zapisywany w pliku `oven_state.json` wraz z czasami dla każdego JIG i przywracany przy restarcie aplikacji
7. **Porównanie czasów** - Przy restarcie aplikacji system odczytuje ostatnie zdarzenie z historii, porównuje czas włożenia z aktualnym czasem i automatycznie oblicza pozostały czas dla każdego JIG. Po upływie `initial_time` JIG pozostaje widoczny jako `NIE WYJĘTY`, dopóki nie zostanie ręcznie wyjęty.

## Nowe cechy aplikacji (v3)

✅ **Responsywny interfejs** - Aplikacja automatycznie dostosowuje się do rozdzielczości ekranu
✅ **Pełny ekran** - Aplikacja uruchamia się w pełnym ekranie bez scrollowania
✅ **JIG ustawione jedno na drugim** - Każda pozycja wyświetla 2 JIG ustawione pionowo (jeden za drugim)
✅ **Indywidualne timery** - Każdy JIG ma własny timer liczący niezależnie od innych
✅ **Wyświetlanie czasu na każdym JIG** - Timer widoczny bezpośrednio na każdej pozycji z kolorystką
✅ **Zmniejszony rozmiar JIG** - Wszystkie półki widoczne bez konieczności scrollowania
✅ **Porównanie czasów przy restarcie** - System automatycznie oblicza pozostały czas dla każdego JIG na podstawie czasu włożenia
✅ **Terminologia JIG** - Wszystkie pozycje są określane jako JIG

## Pliki

- `oven_manager.py` - Główny plik aplikacji
- `config.toml` - Plik konfiguracyjny
- `history.txt` - Historia wprowadzonych JIG (tworzona automatycznie)
- `oven_state.json` - Stan obecny pieca z timerami i czasami włożenia JIG (tworzony automatycznie)
- `README.md` - Ten plik

## Uwagi

- Nie można włożyć JIG-a na zajętą pozycję; wyjątkiem jest potwierdzone przesunięcie JIG-a z kolumny 2 do kolumny 1.
- Aplikacja automatycznie zapisuje historię i stan pieca (razem z timerami dla każdego JIG)
- Stan pieca i czasy są przywracane przy każdym uruchomieniu aplikacji z uwzględnieniem upływu czasu
- Wszystkie czasy są w formacie MM:SS (minuty:sekundy)
- Jeśli aplikacja zostanie zamknięta i ponownie uruchomiona, system automatycznie obliczy jak dużo czasu upłynęło i dostosuje timery JIG

## Autor

Lukasz8504
