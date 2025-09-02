# Cheapchat

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Na systemach z PEP-668 (np. Debian/Ubuntu) instaluj w wirtualnym środowisku lub użyj `pip install --break-system-packages`.

## Uruchomienie

```bash
python app.py
```

## Generowanie linków `data:` do plików

Skrypt `generate_data_links.py` tworzy w pamięci przykładowe pliki PDF i ODT oraz wypisuje gotowe do użycia adresy `data:`.

```bash
python generate_data_links.py
```

Pierwsza linia zawiera URL z plikiem PDF, druga – z dokumentem ODT. Linki można bezpośrednio umieszczać w odpowiedziach lub w tagach HTML, aby przeglądarka pobrała plik z pamięci podręcznej.

Endpoint API `/api/data-links` zwraca podobne linki w formacie JSON:

```
curl http://localhost:8000/api/data-links
```

Odpowiedź zawiera pola `pdf`, `odt` oraz `html` z gotowymi łączami.

## Dane użytkownika

Domyślne dane (baza i załączniki) trafiają do katalogu `~/.config/cheapchat`:

```
~/.config/cheapchat/
├── memory.sqlite
└── static/
    ├── docs/
    └── images/
```
