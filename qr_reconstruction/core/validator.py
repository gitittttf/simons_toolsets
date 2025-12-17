"""
QR-Code Validator mit verbessertem Content-Scoring

Validiert QR-Codes basierend auf:
- Struktur (Finder-Patterns, Timing-Patterns)
- Muster-Qualität
- Modul-Dichte
- Dekodierbarkeit (pyzbar)
- Inhalt (URL-Patterns, Wörterbuch-Matches) [NEU]
"""

import numpy as np
from typing import Optional, Tuple
from dataclasses import dataclass
from PIL import Image
import os
from .qr_matrix import QRMatrix, CellState
from .content_scorer import ContentScorer, ContentScore, get_content_scorer


@dataclass
class ValidationResult:
    """Ergebnis einer QR-Code-Validierung"""
    is_valid: bool
    confidence: float  # 0-100
    decoded_data: Optional[str]
    matrix: np.ndarray
    error_correction_level: Optional[str] = None
    
    # Detaillierte Scores (alle 0-100)
    structure_score: float = 0.0
    pattern_score: float = 0.0
    decode_score: float = 0.0
    density_score: float = 0.0
    content_score: float = 0.0  # NEU: Content-basierter Score
    
    # Content-Score Details
    is_url: bool = False
    url_type: Optional[str] = None
    german_words: int = 0
    english_words: int = 0
    
    # Debug-Info
    debug_info: str = ""
    
    def __repr__(self):
        return (f"ValidationResult(valid={self.is_valid}, "
                f"confidence={self.confidence:.1f}%, "
                f"data='{self.decoded_data[:30] if self.decoded_data else 'None'}...')")


class QRValidator:
    """
    Validiert QR-Codes und berechnet Confidence-Scores
    
    Verwendet den neuen ContentScorer für intelligente Inhaltsbewertung
    """
    
    # Gewichte für Gesamt-Confidence (müssen sich zu 1.0 addieren)
    WEIGHTS = {
        'structure': 0.15,      # QR-Struktur korrekt
        'pattern': 0.10,        # Muster-Check
        'density': 0.05,        # Modul-Dichte
        'decode': 0.20,         # Dekodierung erfolgreich
        'content': 0.50         # Content-Score (Wörterbuch/URL)
    }
    
    def __init__(self, debug_mode: bool = False):
        """
        Initialisiert den Validator
        
        Args:
            debug_mode: Wenn True, werden Debug-Bilder gespeichert
        """
        self.debug_mode = debug_mode
        self.pyzbar_available = False
        self.debug_counter = 0
        
        # Content-Scorer initialisieren
        self.content_scorer = get_content_scorer()
        
        # Erstelle Debug-Ordner
        if debug_mode:
            os.makedirs('debug_qr_images', exist_ok=True)
        
        try:
            import pyzbar.pyzbar as pyzbar
            self.pyzbar = pyzbar
            self.pyzbar_available = True
            print("✓ pyzbar erfolgreich geladen")
        except ImportError:
            print("⚠️ pyzbar nicht installiert - Dekodierung eingeschränkt")
            print("   Installation: pip install pyzbar")
            print("   Windows: Zusätzlich zbar DLL benötigt!")
    
    def validate(self, matrix: QRMatrix) -> ValidationResult:
        """Validiert eine QR-Matrix und berechnet Confidence"""
        binary = matrix.to_binary_grid()
        debug_info = []
        
        # 1. Struktur-Check
        structure_score = self._check_structure(matrix)
        debug_info.append(f"Structure: {structure_score*100:.1f}%")
        
        # 2. Pattern-Check
        pattern_score = self._check_patterns(binary)
        debug_info.append(f"Pattern: {pattern_score*100:.1f}%")
        
        # 3. Dichte-Check
        density_score = self._check_density(binary)
        debug_info.append(f"Density: {density_score*100:.1f}%")
        
        # 4. Dekodierung
        decoded_data, decode_score, decode_debug = self._try_decode(binary)
        debug_info.append(decode_debug)
        
        # 5. Content-Scoring (NEU)
        content_result = self.content_scorer.score_content(decoded_data)
        content_score = content_result.total_score
        debug_info.append(f"Content: {content_score*100:.1f}%")
        
        # Gesamt-Confidence berechnen
        confidence = (
            structure_score * self.WEIGHTS['structure'] +
            pattern_score * self.WEIGHTS['pattern'] +
            density_score * self.WEIGHTS['density'] +
            decode_score * self.WEIGHTS['decode'] +
            content_score * self.WEIGHTS['content']
        ) * 100
        
        # Wenn dekodiert UND guter Content-Score → Boost
        if decoded_data and content_score > 0.5:
            confidence = min(100.0, confidence * 1.1)
        
        # Wenn URL erkannt → zusätzlicher Boost
        if content_result.is_url:
            confidence = min(100.0, confidence + 5.0)
        
        is_valid = confidence > 40  # Threshold für "gültig"
        
        return ValidationResult(
            is_valid=is_valid,
            confidence=confidence,
            decoded_data=decoded_data,
            matrix=binary,
            structure_score=structure_score * 100,
            pattern_score=pattern_score * 100,
            decode_score=decode_score * 100,
            density_score=density_score * 100,
            content_score=content_score * 100,
            is_url=content_result.is_url,
            url_type=content_result.url_type,
            german_words=len(content_result.german_matches),
            english_words=len(content_result.english_matches),
            debug_info=" | ".join(debug_info)
        )
    
    def _check_structure(self, matrix: QRMatrix) -> float:
        """Prüft strukturelle Integrität"""
        score = 0.0
        checks = 0
        
        # 1. Prüfe Finder Patterns
        finder_positions = [
            (0, 0),
            (0, matrix.size - 7),
            (matrix.size - 7, 0)
        ]
        
        for r, c in finder_positions:
            if self._validate_finder_pattern(matrix.grid, r, c):
                score += 1.0
            checks += 1
        
        # 2. Prüfe Timing Patterns
        if self._validate_timing_patterns(matrix.grid, matrix.size):
            score += 1.0
        checks += 1
        
        return score / checks if checks > 0 else 0.0
    
    def _validate_finder_pattern(self, grid: np.ndarray, row: int, col: int) -> bool:
        """Validiert ein einzelnes Finder-Pattern"""
        try:
            # Äußerer Rahmen muss schwarz sein
            for i in range(7):
                if grid[row + i, col] != CellState.BLACK or \
                   grid[row + i, col + 6] != CellState.BLACK or \
                   grid[row, col + i] != CellState.BLACK or \
                   grid[row + 6, col + i] != CellState.BLACK:
                    return False
            
            # Weißer innerer Rahmen
            for i in range(1, 6):
                for j in range(1, 6):
                    if i == 1 or i == 5 or j == 1 or j == 5:
                        if grid[row + i, col + j] != CellState.WHITE:
                            return False
            
            # Schwarzes Zentrum
            for i in range(2, 5):
                for j in range(2, 5):
                    if grid[row + i, col + j] != CellState.BLACK:
                        return False
            
            return True
        except IndexError:
            return False
    
    def _validate_timing_patterns(self, grid: np.ndarray, size: int) -> bool:
        """Validiert Timing-Patterns"""
        try:
            for i in range(8, size - 8):
                expected = CellState.BLACK if (i % 2 == 0) else CellState.WHITE
                if grid[6, i] != expected or grid[i, 6] != expected:
                    return False
            return True
        except IndexError:
            return False
    
    def _check_patterns(self, grid: np.ndarray) -> float:
        """Prüft typische QR-Code-Muster"""
        score = 1.0
        
        # Penalize lange Sequenzen gleicher Farbe
        max_run_penalty = 0
        for i in range(grid.shape[0]):
            run_length = 1
            for j in range(1, grid.shape[1]):
                if grid[i, j] == grid[i, j-1]:
                    run_length += 1
                else:
                    run_length = 1
                
                if run_length > 5:
                    max_run_penalty = max(max_run_penalty, run_length - 5)
        
        score -= min(max_run_penalty * 0.05, 0.3)
        
        # Penalize zu viele 2x2 Blöcke
        block_penalty = 0
        for i in range(grid.shape[0] - 1):
            for j in range(grid.shape[1] - 1):
                block = grid[i:i+2, j:j+2]
                if np.all(block == block[0, 0]):
                    block_penalty += 1
        
        score -= min(block_penalty * 0.01, 0.2)
        
        return max(score, 0.0)
    
    def _check_density(self, grid: np.ndarray) -> float:
        """Prüft Modul-Dichte"""
        total = grid.size
        black = np.sum(grid == 1)
        ratio = black / total
        
        # Ideal: 50%, acceptable: 40-60%
        if 0.40 <= ratio <= 0.60:
            deviation = abs(ratio - 0.50)
            score = 1.0 - (deviation * 10)
        else:
            if ratio < 0.40:
                score = ratio / 0.40
            else:
                score = (1.0 - ratio) / 0.40
        
        return max(score, 0.0)
    
    def _try_decode(self, grid: np.ndarray) -> Tuple[Optional[str], float, str]:
        """
        Versucht den QR-Code zu dekodieren (mit mehreren Strategien)
        
        Returns:
            (decoded_data, score, debug_info)
        """
        if not self.pyzbar_available:
            return None, 0.0, "pyzbar nicht verfügbar"
        
        debug_info = []
        
        try:
            # Strategie 1: Standard-Dekodierung
            result = self._decode_attempt(grid, invert=False, scale=20)
            if result:
                debug_info.append(f"✓ Dekodiert: {result[:30]}...")
                return result, 1.0, " | ".join(debug_info)
            
            # Strategie 2: Invertiert
            result = self._decode_attempt(grid, invert=True, scale=20)
            if result:
                debug_info.append(f"✓ Invertiert: {result[:30]}...")
                return result, 1.0, " | ".join(debug_info)
            
            # Strategie 3: Größere Skalierung
            result = self._decode_attempt(grid, invert=False, scale=30)
            if result:
                debug_info.append(f"✓ Groß: {result[:30]}...")
                return result, 1.0, " | ".join(debug_info)
            
            # Strategie 4: Invertiert + groß
            result = self._decode_attempt(grid, invert=True, scale=30)
            if result:
                debug_info.append(f"✓ Inv+Groß: {result[:30]}...")
                return result, 1.0, " | ".join(debug_info)
            
            debug_info.append("✗ Dekodierung fehlgeschlagen")
            return None, 0.0, " | ".join(debug_info)
        
        except Exception as e:
            debug_info.append(f"✗ Fehler: {str(e)}")
            return None, 0.0, " | ".join(debug_info)
    
    def _decode_attempt(self, grid: np.ndarray, invert: bool, scale: int) -> Optional[str]:
        """Ein Dekodierungs-Versuch mit spezifischen Parametern"""
        try:
            # Konvertiere zu Bild
            if invert:
                img_array = np.uint8(grid * 255)
            else:
                img_array = np.uint8((1 - grid) * 255)
            
            img = Image.fromarray(img_array, mode='L')
            
            # Skaliere hoch
            img = img.resize(
                (grid.shape[1] * scale, grid.shape[0] * scale),
                Image.Resampling.NEAREST
            )
            
            # Debug: Speichere Bild
            if self.debug_mode:
                debug_filename = f'debug_qr_images/qr_decode_{self.debug_counter}_{("inv" if invert else "std")}_s{scale}.png'
                img.save(debug_filename)
            
            # Dekodiere
            decoded = self.pyzbar.decode(img)
            
            if decoded and len(decoded) > 0:
                data = decoded[0].data.decode('utf-8', errors='ignore')
                return data
            
            return None
        
        except Exception as e:
            if self.debug_mode:
                print(f"  ✗ Dekodierungs-Fehler: {e}")
            return None
        finally:
            self.debug_counter += 1
    
    def quick_validate(self, matrix: QRMatrix) -> bool:
        """Schnelle Validierung (nur Struktur)"""
        structure_score = self._check_structure(matrix)
        return structure_score > 0.8