"""
QR-Code Validator mit Confidence-Scoring
Validiert QR-Codes und berechnet Confidence-Score basierend auf verschiedenen Kriterien
"""

import numpy as np
from typing import Optional, Tuple
from dataclasses import dataclass
from PIL import Image
import qrcode
from .qr_matrix import QRMatrix, CellState


@dataclass
class ValidationResult:
    """Ergebnis einer QR-Code-Validierung"""
    is_valid: bool
    confidence: float  # 0-100
    decoded_data: Optional[str]
    matrix: np.ndarray
    error_correction_level: Optional[str] = None
    
    # Detaillierte Scores
    structure_score: float = 0.0
    pattern_score: float = 0.0
    decode_score: float = 0.0
    density_score: float = 0.0
    
    def __repr__(self):
        return (f"ValidationResult(valid={self.is_valid}, "
                f"confidence={self.confidence:.1f}%, "
                f"data='{self.decoded_data[:30] if self.decoded_data else 'None'}...')")


class QRValidator:
    """
    Validiert QR-Codes und berechnet Confidence-Scores
    
    Scoring-Kriterien:
    - Strukturelle Integrität (Finder, Timing, Alignment patterns)
    - Dekodierbarkeit (kann ein QR-Reader es lesen?)
    - Dichte-Verteilung (typisch 40-60% schwarze Module)
    - Pattern-Konsistenz
    """
    
    def __init__(self):
        """Initialisiert den Validator"""
        self.pyzbar_available = False
        try:
            import pyzbar.pyzbar as pyzbar
            self.pyzbar = pyzbar
            self.pyzbar_available = True
        except ImportError:
            print("⚠️ pyzbar nicht installiert - Dekodierung eingeschränkt")
    
    def validate(self, matrix: QRMatrix) -> ValidationResult:
        """
        Validiert eine QR-Matrix und berechnet Confidence
        
        Args:
            matrix: QRMatrix zum Validieren
            
        Returns:
            ValidationResult mit allen Details
        """
        binary = matrix.to_binary_grid()
        
        # Berechne Teil-Scores
        structure_score = self._check_structure(matrix)
        pattern_score = self._check_patterns(binary)
        density_score = self._check_density(binary)
        
        # Versuche zu dekodieren
        decoded_data, decode_score = self._try_decode(binary)
        
        # Gesamt-Confidence (gewichtet)
        weights = {
            'structure': 0.25,
            'pattern': 0.20,
            'density': 0.15,
            'decode': 0.40
        }
        
        confidence = (
            structure_score * weights['structure'] +
            pattern_score * weights['pattern'] +
            density_score * weights['density'] +
            decode_score * weights['decode']
        ) * 100
        
        is_valid = confidence > 50  # Threshold für "gültig"
        
        return ValidationResult(
            is_valid=is_valid,
            confidence=confidence,
            decoded_data=decoded_data,
            matrix=binary,
            structure_score=structure_score * 100,
            pattern_score=pattern_score * 100,
            decode_score=decode_score * 100,
            density_score=density_score * 100
        )
    
    def _check_structure(self, matrix: QRMatrix) -> float:
        """
        Prüft strukturelle Integrität (Finder, Timing Patterns)
        
        Returns:
            Score 0.0-1.0
        """
        score = 0.0
        checks = 0
        
        # 1. Prüfe Finder Patterns (3 Stück)
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
        """
        Prüft typische QR-Code-Muster
        
        QR-Codes vermeiden bestimmte Muster:
        - Zu viele gleiche Module in Folge
        - Zu viele 2x2 Blöcke gleicher Farbe
        
        Returns:
            Score 0.0-1.0
        """
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
        """
        Prüft Modul-Dichte (typisch 40-60% schwarz)
        
        Returns:
            Score 0.0-1.0
        """
        total = grid.size
        black = np.sum(grid == 1)
        ratio = black / total
        
        # Ideal: 50%, acceptable: 40-60%
        if 0.40 <= ratio <= 0.60:
            # Höherer Score je näher an 50%
            deviation = abs(ratio - 0.50)
            score = 1.0 - (deviation * 10)  # Max deviation: 0.1 => -100%
        else:
            # Außerhalb akzeptablem Bereich
            if ratio < 0.40:
                score = ratio / 0.40
            else:  # ratio > 0.60
                score = (1.0 - ratio) / 0.40
        
        return max(score, 0.0)
    
    def _try_decode(self, grid: np.ndarray) -> Tuple[Optional[str], float]:
        """
        Versucht den QR-Code zu dekodieren
        
        Returns:
            (decoded_data, score)
        """
        if not self.pyzbar_available:
            # Fallback: Simuliere Dekodierung basierend auf Struktur
            print("⚠️ pyzbar nicht verfügbar - Dekodierung übersprungen")
            return "[Simuliert: QR-Code]", 0.5
        
        try:
            # Erstelle PIL Image aus Grid (RICHTIGE Orientierung)
            # pyzbar erwartet: schwarz=0, weiß=255
            img_array = np.uint8((1 - grid) * 255)  # Invertiere: 1 -> 0 (schwarz), 0 -> 255 (weiß)
            img = Image.fromarray(img_array, mode='L')
            
            # Scale up für bessere Erkennung (größer = besser)
            scale = 20
            img = img.resize(
                (grid.shape[1] * scale, grid.shape[0] * scale), 
                Image.Resampling.NEAREST
            )
            
            # Debug: Speichere Bild zum Testen (optional)
            # img.save('debug_qr_decode.png')
            
            # Dekodiere mit pyzbar
            decoded = self.pyzbar.decode(img)
            
            if decoded and len(decoded) > 0:
                try:
                    data = decoded[0].data.decode('utf-8', errors='ignore')
                    print(f"✓ QR dekodiert: {data[:50]}...")
                    return data, 1.0  # Erfolgreich dekodiert = voller Score
                except Exception as decode_err:
                    print(f"⚠️ Dekodierungs-Fehler: {decode_err}")
                    return None, 0.0
            else:
                # Kein QR-Code erkannt
                return None, 0.0
        
        except Exception as e:
            print(f"❌ Dekodierungs-Exception: {e}")
            import traceback
            traceback.print_exc()
            return None, 0.0
    
    def quick_validate(self, matrix: QRMatrix) -> bool:
        """
        Schnelle Validierung (nur Struktur, kein Dekodieren)
        
        Returns:
            True wenn strukturell gültig
        """
        structure_score = self._check_structure(matrix)
        return structure_score > 0.8