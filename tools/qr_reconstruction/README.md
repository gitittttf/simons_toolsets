# QR-Code Rekonstruktion

Rekonstruiert beschädigte oder unvollständige QR-Codes. Man malt den Code im Editor ab, markiert
beschädigte Stellen als *unbekannt*, und das Tool berechnet die fehlenden Pixel aus der
Reed-Solomon-Fehlerkorrektur, die jeder QR-Code ohnehin enthält.

## Installation

```bash
pip install -r tools/qr_reconstruction/requirements.txt
```

Eine native Bibliothek wie zbar wird **nicht** benötigt: Das Tool dekodiert QR-Raster mit einem eigenen
Decoder (`core/decoder.py`). Früher wurde dafür pyzbar/zbar verwendet – zbar 0.10 in den Windows-Wheels
bricht aber bei bestimmten Symbolen (Structured-Append-Kopf, entsteht bei mehrdeutigen Rekonstruktionen)
den ganzen Prozess per Assertion ab.

pyzbar dient nur noch in den Tests als unabhängige Referenz (`pip install -r requirements-dev.txt`,
unter Linux zusätzlich `sudo apt install libzbar0`, Diagnose: `python tools/qr_reconstruction/check_pyzbar.py`).

## Starten

Aus dem Projektordner:

```bash
python -m tools.qr_reconstruction   # nur dieses Tool
python launcher.py                  # oder über den Hub
```

Nicht `main_window.py` direkt starten – die relativen Imports funktionieren nur als Modul.

## Bedienung

1. **Bild importieren** (Foto oder Screenshot) – oder eine **Version wählen** (Größe des Codes,
   z. B. 25×25 = Version 2) und den Code abmalen, oder das GitHub-Preset laden.
2. **Abmalen:** Linksklick bzw. Ziehen malt Schwarz/Weiß – gemalte Pixel gelten als *bekannt*.
   Tipp: nur die schwarzen Pixel malen, dann „Unbekannte → Weiß“.
3. **Schaden markieren:** Rechtsklick bzw. Ziehen markiert Pixel als *unbekannt* (grau mit „?“);
   ein zweiter Rechtsklick holt die vorherige Farbe zurück.
4. **Lösbarkeit prüfen:** Die Sidebar zeigt live, ob der Code eindeutig lösbar ist. Der Schalter
   *Overlay* färbt betroffene Codewörter nach ihrem RS-Block ein:
   grün = eindeutig, gelb = korrigiert, orange = mehrdeutig, rot = widersprüchlich, lila = Format-Info.
5. **Bekannter Textanfang** (optional, z. B. `https://`): hilft bei starkem Schaden enorm, siehe unten.
6. **Wiederherstellen** starten. Findet die Reed-Solomon-Rekonstruktion nichts, bietet das Tool
   als Fallback einen Pixel-Bruteforce an.
7. **Ergebnis:** Text kopieren, URL öffnen oder den reparierten Code als PNG/SVG speichern
   (mit Ruhezone – direkt scanbar und druckbar).

Zoom per Mausrad, verschieben mit Strg+Linksklick oder Mittelklick, **Strg+Z / Strg+Y** für
Rückgängig/Wiederholen. Die Statuszeile unter dem Raster zeigt zum Modul unter der Maus Codewort,
RS-Block, Bitposition, ob es Daten oder Fehlerkorrektur ist, und den Bytewert (**Codewort-Inspektor**).

### Bild-Import

1. „📷 Bild importieren“ und ein Foto/einen Screenshot wählen (PNG, JPG, BMP, WebP, TIFF).
2. Die Ecken des Codes werden automatisch gesucht. Findet OpenCV nichts – typisch, wenn ein
   Finder-Pattern beschädigt ist –, zieht man die vier Punkte von Hand auf die Ecken. Ungefähr reicht:
   Die Ecken werden anhand der Finder- und Timing-Muster nachjustiert.
3. Das Bild wird entzerrt, die Version automatisch erkannt und jedes Modul abgetastet. Als unbekannt
   markiert werden unsichere Module, **farbige** Module (z. B. ein roter Stift – QR-Codes sind
   schwarz/weiß) und große einfarbige Flächen.
4. Im Editor liegt das entzerrte Foto hinter dem Raster (Schalter „Foto hinter dem Raster anzeigen“).
   **Schwarze/graue Flecken, Knicke und Reflexe per Rechtsklick als unbekannt markieren** – ein komplett
   überdecktes Modul sieht im Bild genauso aus wie ein echtes, das kann der Import nicht sicher erkennen.
   Die Lösbarkeitsanzeige zeigt sofort, ob es reicht.

Der Import braucht OpenCV (`opencv-python`, in den Requirements enthalten); ohne OpenCV läuft das Tool
weiter, nur der Import ist dann nicht verfügbar.

## Kommandozeile

Ohne Oberfläche, z. B. für viele Bilder auf einmal:

```bash
python -m tools.qr_reconstruction foto.jpg
python -m tools.qr_reconstruction foto.jpg --prefix https:// --save repariert.png
python -m tools.qr_reconstruction *.png --save fix_{name}.svg --json
python -m tools.qr_reconstruction kaputt.png --corners 52,45,343,52,352,345,44,350
```

`--corners` setzt die vier Ecken (x,y im Uhrzeigersinn), wenn die automatische Erkennung scheitert.
Exit-Code: 0 = alles rekonstruiert, 1 = mindestens ein Bild ohne Lösung, 2 = Fehler.

## Wie es funktioniert

1. **Format-Info:** Fehlerkorrektur-Level und Maske sind in 15 Bits (zweifach) kodiert; es gibt
   nur 32 gültige Werte. Diese werden nach Übereinstimmung mit den bekannten Bits gerankt.
2. **Codewörter:** Die Datenmodule werden in der Zickzack-Reihenfolge der Spezifikation gelesen,
   entmaskiert und auf die Reed-Solomon-Blöcke verteilt.
3. **Reed-Solomon:** Jedes unbekannte Bit wird eine Variable; die RS-Prüfgleichungen sind auf
   Bit-Ebene linear. Gauß-Elimination liefert exakt alle Lösungen – ohne Durchprobieren. Teilweise
   bekannte Codewörter tragen dabei jedes bekannte Bit bei. Falsch abgemalte Pixel werden per
   klassischer Fehlerkorrektur (`reedsolo`) behoben.
4. **Daten:** Der Bitstrom wird dekodiert (Numeric, Alphanumeric, Byte, Kanji, ECI). Bei mehreren
   möglichen Lösungen entscheiden Terminator/Padding und der Inhalt (URL, Wörterbuch).
5. **Struktur-Solver:** Bleibt die Lösung mehrdeutig, werden Annahmen über den Aufbau der Daten
   durchprobiert: Modus (Byte/Alphanumerisch/Numerisch) und Länge legen Zeichenzähler, Terminator und
   die Füllbytes `0xEC 0x11 …` bis zum Ende fest – bei kurzen Inhalten in großen Codes ist das ein
   Großteil der Daten. Ein bekannter Textanfang legt weitere Bits fest. Jede Annahme liefert zusätzliche
   bekannte Bits für das Gleichungssystem. Beispiel: 50 % Schaden in einem Version-2-M-Code sind ohne
   Hinweis mehrdeutig (2^48 Lösungen), mit Textanfang `https://` eindeutig.
6. **Gegenprobe:** Die rekonstruierte Matrix wird neu gerendert und unabhängig neu dekodiert.

| Modul | Aufgabe |
|---|---|
| `core/spec.py` | Tabellen der Spezifikation (Blöcke, Masken, Format-/Version-Info) |
| `core/codewords.py` | Module ↔ Codewörter, Interleaving |
| `core/rs_decoder.py` | Rekonstruktion eines RS-Blocks |
| `core/data_decoder.py` | Bitstrom → Text |
| `core/reconstructor.py` | Gesamte Pipeline |
| `core/analysis.py` | Lösbarkeitsanalyse für den Editor |
| `core/image_import.py` | Bild → Matrix (Ecken, Entzerren, Version, Abtasten) |
| `core/structure.py` | Struktur-Annahmen (Modus, Länge, Füllbytes, Textanfang) |
| `core/export.py` | Matrix → PNG/SVG mit Ruhezone |
| `core/bruteforce.py` | Pixel-Bruteforce (Fallback) |
| `core/decoder.py` | Eigener Decoder für vollständige Raster (liest alles, was zbar liest, und mehr) |
| `core/validator.py`, `core/content_scorer.py` | Bewertung (Struktur, Dekodierbarkeit, Inhalts-Score) |

## Grenzen

- **Kapazität:** Pro Block lassen sich so viele unbekannte Codewörter rekonstruieren, wie der Block
  EC-Codewörter hat – je nach Level etwa 20 % (L), 37 % (M), 55 % (Q) bzw. 65 % (H) der Codewörter.
  (Die oft genannten 7/15/25/30 % gelten für *unbekannte Fehler*; bekannte Lücken kosten nur halb so
  viel.) Mit teilweise bekannten Codewörtern geht oft noch mehr. Darüber wird es **mehrdeutig**; das Tool prüft dann bis zu 65.536
  Kandidaten und deckelt die Confidence bei 50 %.
- **Falsch abgemalte Pixel** kosten doppelt so viel Kapazität wie unbekannte. Im Zweifel ein Pixel
  lieber als unbekannt markieren als zu raten.
- **Feste Muster** (Finder, Timing, Alignment, Version-Info) werden aus der Version erzeugt und
  sind nicht editierbar; die gewählte Version muss also stimmen.
- **Zeichenkodierung:** Byte-Segmente ohne ECI werden als UTF-8 (sonst Latin-1) gelesen.
- **Bild-Import:** Geknickte/gewölbte Codes (nicht flach) werden nur über die vier Ecken entzerrt und
  können am Rand verrutschen; Flecken müssen von Hand markiert werden (siehe oben).

## Tests

```bash
python -m pytest          # Unit-Tests (Referenz: die qrcode-Bibliothek)
python quick_test.py      # Szenario: 20 % Schaden per RS, 8 Pixel per Bruteforce
```
