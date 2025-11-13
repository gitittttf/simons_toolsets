"""
QR-Code-Rekonstruktion - Vereinfachte Version
Manuelle Eingabe, ohne Bildverarbeitung, einfach zu verstehen
"""

import numpy as np
from itertools import product
from typing import List, Tuple, Optional
import json
from PIL import Image
import os
from datetime import datetime


class QRCode:
    """Repräsentiert einen QR-Code als Grid"""
    
    def __init__(self, size: int = 21):
        self.size = size
        self.grid = np.zeros((size, size), dtype=int)
        self.locked = np.zeros((size, size), dtype=bool)
        
    def set_cell(self, row: int, col: int, value: int, locked: bool = False):
        """Setzt eine einzelne Zelle"""
        self.grid[row, col] = value
        if locked:
            self.locked[row, col] = True
    
    def get_unknown_cells(self) -> List[Tuple[int, int]]:
        """Gibt alle unbekannten (nicht gesperrten) Zellen zurück"""
        unknown = []
        for i in range(self.size):
            for j in range(self.size):
                if not self.locked[i, j]:
                    unknown.append((i, j))
        return unknown
    
    def print_grid(self, show_locked: bool = False):
        """Gibt das Grid in der Konsole aus"""
        print("\n" + "=" * (self.size * 2 + 2))
        for i in range(self.size):
            row_str = ""
            for j in range(self.size):
                if show_locked and self.locked[i, j]:
                    # Gesperrte Zellen mit Rahmen anzeigen
                    row_str += "[█]" if self.grid[i, j] == 1 else "[░]"
                else:
                    row_str += "█ " if self.grid[i, j] == 1 else "░ "
            print(row_str)
        print("=" * (self.size * 2 + 2) + "\n")
    
    def show_image(self, scale: int = 20, show_locked: bool = False, save: bool = True, custom_name: Optional[str] = None):
        """Zeigt das Grid als Bild und öffnet es
        
        Args:
            scale: Größe eines Moduls in Pixeln
            show_locked: Zeige gesperrte Zellen in Blau
            save: Soll das Bild gespeichert werden?
            custom_name: Optional eigener Dateiname (ohne Pfad)
        """
        # Erstelle output Ordner falls nicht vorhanden
        output_dir = 'output'
        if save and not os.path.exists(output_dir):
            os.makedirs(output_dir)
            print(f"Output-Ordner erstellt: {output_dir}/")
        
        # Erstelle Bild als numpy array (einfacher und schneller)
        img_size = self.size * scale
        img_array = np.zeros((img_size, img_size, 3), dtype=np.uint8)
        img_array.fill(255)  # Weiß als Hintergrund
        
        for i in range(self.size):
            for j in range(self.size):
                # Bestimme Farbe
                if show_locked and self.locked[i, j]:
                    # Gesperrte Zellen in Blau
                    color = [0, 0, 0] if self.grid[i, j] == 1 else [200, 220, 255]
                else:
                    # Normal schwarz/weiß
                    color = [0, 0, 0] if self.grid[i, j] == 1 else [255, 255, 255]
                
                # Fülle Pixel-Block
                y_start = i * scale
                y_end = (i + 1) * scale
                x_start = j * scale
                x_end = (j + 1) * scale
                img_array[y_start:y_end, x_start:x_end] = color
        
        # Konvertiere zu PIL Image
        img = Image.fromarray(img_array, 'RGB')
        
        # Speichere wenn gewünscht
        if save:
            if custom_name:
                filename = os.path.join(output_dir, custom_name)
            else:
                # Generiere eindeutigen Namen mit Timestamp
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
                filename = os.path.join(output_dir, f'qr_{timestamp}.png')
            
            img.save(filename)
            print(f"✓ Bild gespeichert: {filename}")
        else:
            print("Bild wird nur angezeigt (nicht gespeichert)")
        
        # Öffne mit Standard-Bildviewer
        img.show()
        
        return img
    
    def save_to_file(self, filename: str):
        """Speichert den QR-Code als JSON"""
        data = {
            'size': self.size,
            'grid': self.grid.tolist(),
            'locked': self.locked.tolist()
        }
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"Gespeichert in: {filename}")
    
    @classmethod
    def load_from_file(cls, filename: str):
        """Lädt einen QR-Code aus JSON"""
        with open(filename, 'r') as f:
            data = json.load(f)
        
        qr = cls(size=data['size'])
        qr.grid = np.array(data['grid'])
        qr.locked = np.array(data['locked'])
        return qr


class QRStructure:
    """Kennt die feste Struktur von QR-Codes"""
    
    @staticmethod
    def add_position_markers(qr: QRCode):
        """Fügt die drei Positionsmarker hinzu (die drei Quadrate)"""
        positions = [
            (0, 0),                    # Oben links
            (0, qr.size - 7),          # Oben rechts
            (qr.size - 7, 0)           # Unten links
        ]
        
        for start_row, start_col in positions:
            # Äußerer schwarzer Rahmen
            for i in range(7):
                qr.set_cell(start_row + i, start_col, 1, locked=True)
                qr.set_cell(start_row + i, start_col + 6, 1, locked=True)
                qr.set_cell(start_row, start_col + i, 1, locked=True)
                qr.set_cell(start_row + 6, start_col + i, 1, locked=True)
            
            # Weißer Rahmen (innen)
            for i in range(1, 6):
                for j in range(1, 6):
                    if i == 1 or i == 5 or j == 1 or j == 5:
                        qr.set_cell(start_row + i, start_col + j, 0, locked=True)
            
            # Schwarzes Zentrum (3x3)
            for i in range(2, 5):
                for j in range(2, 5):
                    qr.set_cell(start_row + i, start_col + j, 1, locked=True)
    
    @staticmethod
    def add_timing_patterns(qr: QRCode):
        """Fügt die Timing-Muster hinzu (alternierend schwarz-weiß)"""
        for i in range(8, qr.size - 8):
            value = (i + 1) % 2  # Alternierend 0 und 1
            qr.set_cell(6, i, value, locked=True)  # Horizontal
            qr.set_cell(i, 6, value, locked=True)  # Vertikal
    
    @staticmethod
    def validate_structure(qr: QRCode) -> bool:
        """Prüft ob die QR-Struktur korrekt ist"""
        # Prüfe Timing-Pattern
        for i in range(8, qr.size - 8):
            expected = (i + 1) % 2
            if qr.grid[6, i] != expected or qr.grid[i, 6] != expected:
                return False
        return True


class BruteForceReconstructor:
    """Rekonstruiert fehlende Teile durch Ausprobieren"""
    
    def __init__(self, qr: QRCode, max_iterations: int = 10000):
        self.qr = qr
        self.max_iterations = max_iterations
        self.unknown_cells = qr.get_unknown_cells()
        
    def reconstruct(self, validator_func=None):
        """
        Hauptfunktion: Probiert alle Kombinationen durch
        
        validator_func: Optional eine Funktion die (grid) -> (bool, score, data) zurückgibt
                       Wenn None, werden nur strukturelle Checks gemacht
        """
        print(f"Starte Rekonstruktion...")
        print(f"Unbekannte Zellen: {len(self.unknown_cells)}")
        print(f"Mögliche Kombinationen: {2**len(self.unknown_cells):,}")
        print(f"Max. Iterationen: {self.max_iterations:,}\n")
        
        if len(self.unknown_cells) > 20:
            print("⚠️  WARNUNG: Sehr viele unbekannte Zellen!")
            print("   Das könnte sehr lange dauern. Empfehlung:")
            print("   - Mehr Zellen als 'locked' markieren")
            print("   - max_iterations reduzieren\n")
        
        results = []
        tested = 0
        
        # Generiere Kandidaten
        total = min(2**len(self.unknown_cells), self.max_iterations)
        
        for combination in self._generate_candidates(total):
            tested += 1
            
            # Erstelle Kandidaten-Grid
            candidate_grid = self.qr.grid.copy()
            for (row, col), value in zip(self.unknown_cells, combination):
                candidate_grid[row, col] = value
            
            # Validiere Kandidat
            if validator_func:
                is_valid, score, data = validator_func(candidate_grid)
                if is_valid:
                    results.append({
                        'grid': candidate_grid,
                        'score': score,
                        'data': data,
                        'iteration': tested
                    })
                    print(f"✓ Gültiger Kandidat #{tested}: {data} (Score: {score:.2%})")
            else:
                # Nur strukturelle Validierung
                temp_qr = QRCode(self.qr.size)
                temp_qr.grid = candidate_grid
                if QRStructure.validate_structure(temp_qr):
                    results.append({
                        'grid': candidate_grid,
                        'score': 1.0,
                        'data': 'Struktur gültig',
                        'iteration': tested
                    })
                    print(f"✓ Strukturell gültiger Kandidat #{tested}")
            
            # Fortschrittsanzeige
            if tested % 1000 == 0:
                print(f"   Fortschritt: {tested:,} / {total:,} ({tested/total*100:.1f}%)")
        
        print(f"\n{'='*50}")
        print(f"Rekonstruktion abgeschlossen!")
        print(f"Getestete Kandidaten: {tested:,}")
        print(f"Gültige Ergebnisse: {len(results)}")
        print(f"{'='*50}\n")
        
        # Sortiere nach Score
        results.sort(key=lambda x: x['score'], reverse=True)
        return results
    
    def _generate_candidates(self, max_count: int):
        """Generiert Kombinationen (0/1) für unbekannte Zellen"""
        if len(self.unknown_cells) <= 20:
            # Kleine Anzahl: Vollständige Enumeration
            for i, combination in enumerate(product([0, 1], repeat=len(self.unknown_cells))):
                if i >= max_count:
                    break
                yield combination
        else:
            # Große Anzahl: Zufälliges Sampling
            for _ in range(max_count):
                yield tuple(np.random.randint(0, 2) for _ in range(len(self.unknown_cells)))


def simple_validator(grid: np.ndarray) -> Tuple[bool, float, str]:
    """
    Einfache Validierungsfunktion für Demo-Zwecke
    
    In einer echten Implementierung würde hier:
    - QR-Code Dekodierung stattfinden (mit pyzbar oder qrcode library)
    - URL/Text-Validierung
    - Plausibilitäts-Checks
    
    Returns: (is_valid, score, decoded_data)
    """
    # Für diese Demo: Prüfe nur ob es "interessant" aussieht
    # (z.B. nicht komplett schwarz oder weiß)
    
    total_cells = grid.size
    black_cells = np.sum(grid == 1)
    white_cells = np.sum(grid == 0)
    
    # QR-Codes haben typischerweise 40-60% schwarze Zellen
    black_ratio = black_cells / total_cells
    
    if 0.35 < black_ratio < 0.65:
        score = 1.0 - abs(black_ratio - 0.5) * 2  # Höherer Score wenn näher an 50%
        return True, score, f"Plausibel (Schwarz: {black_ratio:.1%})"
    
    return False, 0.0, ""


# ============================================================================
# BEISPIELE FÜR DIE VERWENDUNG
# ============================================================================

def example_1_manual_input():
    """Beispiel 1: Komplett manuelle Eingabe"""
    print("\n" + "="*60)
    print("BEISPIEL 1: Manuelle Eingabe")
    print("="*60)
    
    # Erstelle leeren QR-Code
    qr = QRCode(size=21)
    
    # Füge feste Struktur hinzu
    QRStructure.add_position_markers(qr)
    QRStructure.add_timing_patterns(qr)
    
    # Simuliere bekannte Bereiche (z.B. obere linke Hälfte ist bekannt)
    print("\nSimuliere teilweise bekannten QR-Code...")
    for i in range(qr.size):
        for j in range(qr.size // 2):  # Linke Hälfte
            if not qr.locked[i, j]:
                # Setze Zufallswerte für Demo
                qr.set_cell(i, j, np.random.randint(0, 2), locked=True)
    
    print("\nBekannter Bereich:")
    save_choice = input("Bild speichern? (j/n): ").lower() == 'j'
    qr.show_image(scale=20, show_locked=True, save=save_choice, custom_name='qr_input_bekannt.png')
    
    # Speichere für später
    qr.save_to_file('qr_partial.json')
    
    # Starte Rekonstruktion (nur kurz für Demo)
    reconstructor = BruteForceReconstructor(qr, max_iterations=1000)
    results = reconstructor.reconstruct(validator_func=simple_validator)
    
    # Zeige beste Ergebnisse
    if results:
        print("\nTop 3 Rekonstruktionen:")
        for i, result in enumerate(results[:3], 1):
            print(f"\n{i}. Platz (Score: {result['score']:.2%})")
            print(f"   {result['data']}")
            temp_qr = QRCode(qr.size)
            temp_qr.grid = result['grid']
            
            save_choice = input(f"Ergebnis #{i} speichern? (j/n): ").lower() == 'j'
            temp_qr.show_image(scale=20, save=save_choice, custom_name=f'qr_result_top{i}.png')


def example_2_interactive():
    """Beispiel 2: Interaktive Eingabe"""
    print("\n" + "="*60)
    print("BEISPIEL 2: Interaktive Eingabe")
    print("="*60)
    
    qr = QRCode(size=21)
    QRStructure.add_position_markers(qr)
    QRStructure.add_timing_patterns(qr)
    
    print("\nInteraktiver Editor:")
    print("Befehle:")
    print("  set <row> <col> <value>  - Setze Zelle (value: 0=weiß, 1=schwarz)")
    print("  lock <row> <col>         - Sperre Zelle")
    print("  show                     - Zeige Grid als Bild")
    print("  save <filename>          - Speichere als JSON")
    print("  run                      - Starte Rekonstruktion")
    print("  quit                     - Beenden")
    print("\nTipp: Koordinaten starten bei 0")
    print("Beispiel: 'set 10 10 1' setzt Zelle (10,10) auf schwarz\n")
    
    save_choice = input("Erstes Bild speichern? (j/n): ").lower() == 'j'
    qr.show_image(scale=20, show_locked=True, save=save_choice, custom_name='qr_editor_start.png')
    
    while True:
        try:
            cmd = input("\nBefehl: ").strip().split()
            
            if not cmd:
                continue
            
            if cmd[0] == 'quit':
                break
            
            elif cmd[0] == 'set' and len(cmd) == 4:
                row, col, value = int(cmd[1]), int(cmd[2]), int(cmd[3])
                qr.set_cell(row, col, value, locked=True)
                print("✓ Zelle gesetzt")
                save_choice = input("Aktuelles Bild speichern? (j/n): ").lower() == 'j'
                qr.show_image(scale=20, show_locked=True, save=save_choice)
            
            elif cmd[0] == 'lock' and len(cmd) == 3:
                row, col = int(cmd[1]), int(cmd[2])
                qr.locked[row, col] = True
                print("✓ Zelle gesperrt")
            
            elif cmd[0] == 'show':
                save_choice = input("Bild speichern? (j/n): ").lower() == 'j'
                qr.show_image(scale=20, show_locked=True, save=save_choice)
            
            elif cmd[0] == 'save' and len(cmd) == 2:
                qr.save_to_file(cmd[1])
            
            elif cmd[0] == 'run':
                max_iter = int(input("Max. Iterationen (z.B. 1000): "))
                reconstructor = BruteForceReconstructor(qr, max_iterations=max_iter)
                results = reconstructor.reconstruct(validator_func=simple_validator)
                
                if results:
                    print(f"\nBestes Ergebnis:")
                    best = results[0]
                    temp_qr = QRCode(qr.size)
                    temp_qr.grid = best['grid']
                    
                    save_choice = input("Bestes Ergebnis speichern? (j/n): ").lower() == 'j'
                    if save_choice:
                        temp_qr.show_image(scale=20, save=True, custom_name='qr_reconstructed_best.png')
                        temp_qr.save_to_file('qr_reconstructed.json')
                    else:
                        temp_qr.show_image(scale=20, save=False)
            
            else:
                print("❌ Unbekannter Befehl")
        
        except (ValueError, IndexError) as e:
            print(f"❌ Fehler: {e}")
        except KeyboardInterrupt:
            print("\nAbgebrochen")
            break


def example_3_from_file():
    """Beispiel 3: Lade aus gespeicherter Datei"""
    print("\n" + "="*60)
    print("BEISPIEL 3: Aus Datei laden")
    print("="*60)
    
    try:
        qr = QRCode.load_from_file('qr_partial.json')
        print("QR-Code geladen!")
        
        print(f"Größe: {qr.size}x{qr.size}")
        print(f"Gesperrte Zellen: {np.sum(qr.locked)}")
        print(f"Unbekannte Zellen: {len(qr.get_unknown_cells())}")
        
        save_choice = input("\nBild speichern? (j/n): ").lower() == 'j'
        qr.show_image(scale=20, show_locked=True, save=save_choice, custom_name='qr_loaded.png')
        
    except FileNotFoundError:
        print("Datei nicht gefunden. Führe zuerst Beispiel 1 aus.")


def main():
    """Hauptprogramm"""
    print("""
    ╔════════════════════════════════════════════════════════╗
    ║     QR-Code Rekonstruktion - Vereinfachte Version      ║
    ║                                                        ║
    ║  Keine Bildverarbeitung - Manuelle Eingabe - Einfach  ║
    ╚════════════════════════════════════════════════════════╝
    """)
    
    print("Wählen Sie ein Beispiel:")
    print("1 - Automatische Demo (simuliert teilweisen QR-Code)")
    print("2 - Interaktiver Editor (selbst Zellen setzen)")
    print("3 - Aus Datei laden (qr_partial.json)")
    print("0 - Beenden")
    
    choice = input("\nIhre Wahl: ").strip()
    
    if choice == '1':
        example_1_manual_input()
    elif choice == '2':
        example_2_interactive()
    elif choice == '3':
        example_3_from_file()
    elif choice == '0':
        print("Auf Wiedersehen!")
    else:
        print("Ungültige Wahl")


if __name__ == "__main__":
    main()