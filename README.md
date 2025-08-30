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

Domyślne dane (baza i załączniki) trafiają do katalogu `~/.config/cheapchat`:

```
~/.config/cheapchat/
├── memory.sqlite
└── static/
    ├── docs/
    └── images/
```
