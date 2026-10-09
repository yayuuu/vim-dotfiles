# Neovim: układ VS Code, skróty Notepad++

Uruchom `nvim` lub `nvim /ścieżka/do/projektu`. W VTM użyj skrótu Neovim.
Drzewo projektu jest po lewej, pliki na kartach u góry, terminal na dole pod sekcją kodu.
W zakładce Files pod drzewem katalogów jest lista funkcji, metod i klas bieżącego pliku (Aerial).
Rozpoznaje język automatycznie, aktualizuje się po zmianie pliku i pozwala przejść do definicji kliknięciem.
Klikalne menu na samej górze całego Neovim: File, Edit, Search, View, Project, Git, Debug, Terminal, Help.
File > Open folder... wybiera katalog, aktualizuje drzewo, wyszukiwanie i katalog terminalu.
Zakładka Projects w pierwszym panelu pokazuje ostatnio otwierane katalogi, od najnowszego.
Dodaje katalog startowy Neovima, katalog przekazany jako argument i katalogi otwarte z menu;
katalog domowy jest pomijany, a ponowne otwarcie projektu przenosi go na górę bez duplikatu.
Pojedyncze kliknięcie projektu otwiera go i przełącza panel na Files.
Zakładki lewego panelu mają kolejność Projects, Files, Git, Tabs i zmieniają cały panel:
Projects pokazuje wyłącznie projekty, Files — pliki i symbole, Git — zmiany i graf commitów
od aktualnego HEAD, Tabs — dokumenty i osobną listę terminali. Kliknięcie terminala
przywraca jego dolne okno pod kodem, zachowując dokument w edytorze.
Uruchomienie w katalogu domowym otwiera Projects; inny katalog lub katalog przekazany
jako argument otwiera Files. Graf commitów ma własny przycisk odświeżenia i podgląd po kliknięciu commita.
Każdy projekt pamięta własne karty plików, ich kolejność i ostatnio aktywny plik z pozycją kursora.
Odtwarza je przy wyborze projektu oraz przy uruchomieniu Neovima w tym katalogu.
Czyste karty poprzedniego projektu chowają się; niezapisane zmiany pozostają dostępne.
Usunięte pliki są pomijane przy odtwarzaniu. Niezapisana treść nie jest zapisywana w historii projektów.
Pliki otwierają się w trybie wpisywania. Esc przełącza do trybu Vim; i wraca do wpisywania.
Kliknij miejsce kursora, przeciągnij zaznaczenie, użyj kółka do przewijania.
Pojedyncze kliknięcie w drzewie otwiera plik w sekcji kodu albo rozwija/zwija katalog. Prawy klik otwiera menu.
Karty, zamykanie kart, zakładki Projects/Files/Git/Tabs i kontrolki debuggera są klikalne.
Każdy otwarty plik ma własną kartę. Pusta, niezmieniona karta „No Name” znika po otwarciu
pierwszego pliku; dokument z wpisanym tekstem pozostaje. Lewy klik wybiera kartę,
prawy otwiera jej menu, a środkowy lub × zamyka. Przy zamykaniu zmienionego pliku
możesz zapisać, odrzucić zmiany albo anulować; zapis nowego dokumentu pyta o nazwę.
Proporcje drzewa, listy symboli i dolnego terminalu są zapisywane automatycznie,
także po przeciągnięciu separatora, i przywracane po ponownym uruchomieniu.
Skalowanie okna VTM zmienia rozmiary paneli proporcjonalnie. Przy bardzo małym
oknie obowiązują minimalne rozmiary; powiększenie przywraca wybrane proporcje.

## Pliki i edycja

| Skrót | Działanie |
| --- | --- |
| Ctrl+N | Nowy plik |
| Ctrl+O | Wyszukaj i otwórz plik projektu |
| Ctrl+S | Zapisz; nowy plik pyta o nazwę |
| Ctrl+Shift+S / Alt+S | Zapisz jako |
| Ctrl+W | Zamknij plik; niezapisane zmiany wymagają decyzji |
| Ctrl+A | Zaznacz wszystko |
| Ctrl+C / Ctrl+X / Ctrl+V | Kopiuj / wytnij / wklej; bez zaznaczenia kopiuj/wytnij linię |
| Ctrl+Z / Ctrl+Y | Cofnij / ponów |
| Ctrl+D | Duplikuj linię lub zaznaczenie |
| Ctrl+Shift+↑ / Ctrl+Shift+↓ | Przesuń bieżącą linię lub zaznaczony blok w górę / w dół |
| Shift+Home / Shift+End | Zaznacz od kursora do początku / końca linii |
| Tab / Shift+Tab przy zaznaczeniu | Zwiększ / zmniejsz wcięcie zaznaczonych linii |
| Ctrl+L | Usuń linię |
| Ctrl+Q | Komentuj/odkomentuj linię lub zaznaczenie |
| Ctrl+F | Szukaj tekstu w pliku |
| F3 / Shift+F3 | Następny / poprzedni wynik |
| Ctrl+H | Panel zamiany w bieżącym pliku (Grug Far) |
| Ctrl+Shift+F / Alt+F | Szukaj w projekcie |
| Ctrl+G | Idź do linii |
| Ctrl+Tab / Ctrl+Shift+Tab | Następna / poprzednia karta |
| Ctrl+PageDown / Ctrl+PageUp | Alternatywne przełączanie kart |
| F1 | Ten przewodnik |
| Ctrl+Shift+P / Alt+P | Paleta poleceń |

Ctrl+H otwiera panel Grug Far z ograniczeniem do bieżącego pliku.
W panelu zamiany naciśnij Esc, a następnie \r, aby wykonać zamianę; domyślnie obsługuje wyrażenia regularne.
Formatowanie jest dostępne z menu myszy; zapis nie formatuje automatycznie.

## Minimapa kodu

Po prawej stronie sekcji kodu działa Neominimap. Znaki braille pokazują strukturę
pliku; tło wyróżnia widoczny fragment, a bieżąca linia ma dodatkowe zaznaczenie.
Kliknięcie minimapy przenosi kursor do wskazanego miejsca, kółko przewija kod.
Przytrzymaj lewy przycisk myszy na podświetlonym fragmencie i przeciągnij w górę
lub w dół, aby przewijać kod jak suwakiem. W już otwartej sesji można wczytać
obsługę przeciągania poleceniem `:lua require("config.minimap").setup()`.
Gest działa również po kliknięciu
innego fragmentu minimapy; przeciąganie w samym kodzie nadal zaznacza tekst.
Znaczniki pokazują diagnostykę, zmiany Git i wyniki wyszukiwania.
Menu View > Toggle code minimap włącza lub wyłącza podgląd.
Minimapa mieści się nad dolnym terminalem i nie występuje w panelach bocznych.
Przy bardzo wąskim edytorze chowa się automatycznie. Długie pliki mają
przewijany podgląd o stałej skali, podobnie jak minimapa VS Code.

## Podpowiedzi językowe

Podpowiedzi uruchamiają się automatycznie; Ctrl+Space wywołuje je ręcznie.
Tab zatwierdza wybraną podpowiedź. Narzędzia językowe obsługują między innymi
Python, C/C++, JavaScript/TypeScript, Bash i Lua. Plik musi mieć rozpoznany typ;
zależności i ustawienia danego projektu wpływają na dostępne podpowiedzi.

| Skrót | Działanie |
| --- | --- |
| F2 | Zmień nazwę symbolu |
| F12 | Przejdź do definicji |
| Shift+F12 | Znajdź użycia symbolu; dostępne też z menu myszy |

Lista Functions / Symbols pod drzewem pokazuje strukturę bieżącego pliku.
Menu myszy w kodzie udostępnia też dokumentację, akcje naprawcze i formatowanie.

## Projekt, repozytorium i terminal

| Skrót | Działanie |
| --- | --- |
| Ctrl+Shift+E / Alt+E | Pokaż/ukryj drzewo projektu |
| Ctrl+Shift+G / Alt+R | Zmiany Git w drzewie |
| Alt+G | LazyGit: staging, commit, historia, gałęzie |
| Alt+D | Diffview: różnice repozytorium |
| Ctrl+` / Alt+T / F4 | Pokaż/ukryj terminal dolny |
| Esc, Esc w terminalu | Wyjdź z wpisywania do terminalu |

Git działa w katalogu zawierającym repozytorium. Commity i operacje Git uruchamiasz samodzielnie.
Wiersz GIT STATUS pod zakładkami ma po prawej klikalny przycisk [⟳]; status odświeżysz
też przez R, F5 albo prawy klik > Refresh Git status. Menu Git > Refresh status robi to samo.
Kliknięcie `git master` lub innej nazwy brancha na dolnym pasku otwiera listę gałęzi.
Wybierz gałąź i zatwierdź Enterem, aby ją przełączyć. Opcja jest też w menu Git > Switch branch...
Po przełączeniu odświeżają się pliki, zakładka Git i pasek statusu.
Obok brancha jest jeden przycisk `[↑2 ↓1]`: liczba commitów do wysłania i pobrania.
Liczniki porównują HEAD ze śledzoną gałęzią; odświeżają się po operacjach Git,
zapisie, powrocie do aplikacji i co 15 sekund. Fetch w tle odświeża zdalne referencje
co minutę (można wyłączyć przez `vim.g.ide_git_autofetch = false`). Kliknięcie pobiera
zmiany, wykonuje pull zgodnie z konfiguracją Git i wysyła commity przez push.
Błąd lub konflikt przerywa synchronizację przed następnym krokiem. Brak upstream
jest oznaczony kreskami; najpierw trzeba ustawić gałąź zdalną. Podczas synchronizacji
przycisk pokazuje wielokropki i nie uruchamia drugiej operacji.
Kliknięcie zmienionego pliku w zakładce Git otwiera kartę `nazwa (diff)`:
po lewej jest wersja z HEAD tylko do odczytu, po prawej aktualna wersja do edycji.
Wspólny pasek kart znajduje się nad obiema kolumnami.
Dodane linie są zielone, usunięte czerwone, a zmienione pomarańczowe.
Ctrl+S zapisuje edytowaną wersję. Zwykła karta pliku przywraca jedną kolumnę;
obie karty zachowują te same niezapisane zmiany.
Środkowy klik zamyka kartę również na wspólnym pasku nad diffem. Zamknięcie
karty porównania zachowuje niezapisane zmiany w zwykłej karcie pliku.
Wybranie karty albo ponowne otwarcie pliku/diffa przenosi kartę na początek listy.
Kółko myszy nad paskiem kart przewija je w poziomie, bez zmiany bieżącego pliku.
Pod kartami diffa jest toolbar z przyciskami Previous / Next do przechodzenia
między zmianami. Minimapa po prawej pokazuje aktualny kod: dodatki na zielono,
usunięcia na czerwono, zmiany na pomarańczowo.
Poziome suwaki pojawiają się pod kodem, gdy linie są szersze od widoku;
można je klikać i przeciągać. W diffie oba suwaki przewijają kod razem.

Zakładka Git rozdziela Staged Changes (przygotowane do commita) i Changes.
Po wejściu w zakładkę obie grupy są rozwinięte. Kliknięcie pliku ustawia początek
zaznaczenia; Shift+klik zaznacza zakres plików, łącznie z oboma końcami.
Ctrl+klik dodaje pojedynczy plik do zaznaczenia albo go z niego usuwa.
Prawy klik na zaznaczonym pliku
zachowuje ten zakres. Stage Changes i Unstage Changes działają na zaznaczonych
plikach z odpowiedniej grupy. Menu pliku w Changes udostępnia Stage Changes
i Discard Changes, a menu pliku w Staged Changes — tylko Unstage Changes.
Stage zapisuje niezapisane zmiany przed dodaniem do indeksu.
Discard wymaga potwierdzenia, przywraca wersję z indeksu i zapisuje kopię w
`~/.local/state/nvim/git-discard/`; nie usuwa zmian przygotowanych do commita.
Na górze panelu wpisz wiadomość commita i naciśnij Enter albo kliknij
Commit staged changes. Commit obejmuje wyłącznie przygotowane zmiany.

Jeśli środkowy klik w foot przez SSH wkleja zamiast zamykać kartę, na komputerze
z foot dodaj `primary-paste=none` w sekcji `[mouse-bindings]` pliku
`~/.config/foot/foot.ini`, a następnie otwórz nową sesję foot.
Neovim obsługuje zamknięcie już po naciśnięciu środkowego przycisku.
Jeśli foot przechwytuje Shift+klik do zaznaczania tekstu terminala, w tej samej
sekcji `[mouse-bindings]` ustaw `selection-override-modifiers=Control+Shift`.
Otwórz nowe okno foot: sam Shift będzie przekazywany z kliknięciem do VTM,
a Ctrl+Shift pozostanie dostępny do zaznaczania tekstu terminala.
Niektóre terminale/KVM nie rozróżniają Ctrl+Shift; wtedy użyj skrótów Alt lub menu myszy.

## Debugger

| Skrót | Działanie |
| --- | --- |
| F5 | Uruchom / kontynuuj |
| Shift+F5 | Zatrzymaj |
| F9 | Dodaj/usuń breakpoint |
| F10 | Step over |
| F11 | Step into |
| Shift+F11 | Step out |
| Alt+B | Pokaż/ukryj panele debuggera |

Python używa debugpy. C/C++ używa CodeLLDB; skompiluj program z `-g`, po F5 wskaż plik wykonywalny.
JavaScript używa js-debug-adapter. TypeScript wymaga środowiska projektu (np. tsx/ts-node)
lub skompilowanego JavaScriptu z mapami źródeł. Własne konfiguracje uruchamiania można
trzymać w `.vscode/launch.json`. Środowisko Python projektu wybierzesz poleceniem :VenvSelect.
Debugowanie nie kompiluje automatycznie projektu.

## Konfiguracja

- lua/config/keymaps.lua — skróty klawiszowe
- lua/config/options.lua — ustawienia edytora i schowka
- lua/config/autocmds.lua — układ przy uruchomieniu i tryb wpisywania
- lua/config/ide.lua — wspólne akcje i menu myszy
- lua/config/layout.lua — zapamiętywanie proporcji i skalowanie paneli
- lua/config/projects.lua — historia katalogów i karty osobno dla każdego projektu
- lua/config/project_source.lua — zakładka Projects w pierwszym panelu
- lua/config/sidebar.lua — dolne sekcje Files/Git/Tabs, graf commitów i lista terminali
- lua/config/tab_source.lua — dokumenty i diffy w zakładce Tabs
- lua/config/git_sync.lua — liczniki upstream i klikalna synchronizacja pull/push
- lua/config/git.lua — status Git, gałęzie, stage/unstage/discard i pole commita
- lua/config/git_source.lua — grupy Staged Changes / Changes w panelu Git
- lua/config/diff.lua — porównanie HEAD z edytowalną wersją w jednej karcie
- lua/config/editor_tabs.lua — przewijany pasek kart nad edytorem oraz toolbar diffa
- lua/config/tabs.lua — kolejność kart według ostatniego wyboru
- lua/config/hscroll.lua — poziome suwaki i synchronizacja diffa
- lua/plugins/ide.lua — motyw, panele, Git, debugger i narzędzia językowe
- lua/plugins/minimap.lua — minimapa (m.in. szerokość 12 kolumn i skala braille)
- lua/config/minimap.lua — przeciąganie suwaka minimapy
- lazy-lock.json — wersje pluginów

:Lazy zarządza pluginami, :Mason narzędziami językowymi, :LazyExtras dodatkami LazyVim.
Konfiguracja jest dla użytkownika root, czyli bieżącej sesji VTM.
Proporcje paneli są zapisane w `~/.local/state/nvim/desktop-ide-layout.json`.
Historia projektów i ich otwarte karty są zapisane w `~/.local/state/nvim/desktop-ide-projects.json`.
Po zmianach konfiguracji zapisz dokumenty i uruchom Neovim ponownie.

W sesji kmscon uruchamianej przez `~/term` Home/End z modyfikatorami obsługuje
lokalna poprawka libtsm w `~/.local/opt/libtsm-keyboard`. Jej wczytanie wymaga
ponownego uruchomienia kmscon, nie tylko Neovim.

VTM jawnie przekazuje Ctrl+Shift+↑/↓ do aplikacji przez `~/.config/vtm/keybindings.xml`,
zamiast używać tych klawiszy do przewijania widoku terminalu. Zmiana configu VTM
jest wczytywana przy następnym uruchomieniu sesji.
