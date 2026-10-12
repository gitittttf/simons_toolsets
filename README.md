# simons_toolsets
Eine Kollektion an Tools die ich erstellte, weil Ich auf eine Idee kam oder sowas brauchte.

## Tools

| Tool | Beschreibung |
|---|---|
| [QR-Code Rekonstruktion](tools/qr_reconstruction/README.md) | Rekonstruiert beschädigte QR-Codes per Reed-Solomon-Fehlerkorrektur |

## Starten

Alle Befehle aus dem Projektordner (dem Ordner mit `launcher.py`):

```bash
pip install -r requirements-dev.txt   # Abhängigkeiten aller Tools + pytest
python launcher.py                    # Hub mit allen Tools
```

## Entwicklung

```bash
python -m pytest        # Tests
python -m mypy tools    # Typprüfung (Konfiguration in mypy.ini)
```

Neue Tools liegen als Paket unter `tools/<name>/` und stellen in `tools/<name>/tool.py` eine Klasse bereit,
die von `core.base_tool.BaseTool` erbt – der Hub findet sie dann automatisch.
