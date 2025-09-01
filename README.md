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

## Dane użytkownika

Domyślna lokalizacja danych (baza i załączniki) to podkatalog `data/` w repozytorium. Możesz ją zmienić, ustawiając zmienną środowiskową `CHEAPCHAT_DATA_DIR`.

```
data/
├── memory.sqlite
└── static/
    ├── docs/
    └── images/
```
