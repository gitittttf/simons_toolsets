"""
Spec-basierte QR-Rekonstruktion

Pipeline:
  1. Format-Info: die 32 möglichen (EC-Level, Maske) nach Übereinstimmung mit den bekannten
     Format-Bits ranken
  2. Codewörter lesen und entmaskieren, in RS-Blöcke aufteilen
  3. Jeden Block per Reed-Solomon rekonstruieren (rs_decoder.solve_block) - Blöcke sind unabhängig,
     die Kosten addieren sich also statt sich zu multiplizieren
  4. Datenbitstrom dekodieren; Terminator/Padding und Inhalt dienen zum Ranken mehrdeutiger Lösungen
  5. Vollständige Matrix neu rendern und von pyzbar gegenprüfen lassen

Im Gegensatz zum Pixel-Bruteforce (2^unbekannte Pixel) ist die Laufzeit hier praktisch unabhängig
von der Anzahl unbekannter Pixel, solange die Fehlerkorrektur sie abdeckt.
"""

import logging
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

from .codewords import deinterleave, interleave, read_codewords, render_matrix
from .data_decoder import DataDecodeError, decode_data
from .gil import GilYielder
from .structure import Hypothesis, constraints, hypotheses, prefix_constraints
from .qr_matrix import QRMatrix
from .rs_decoder import BlockSolution, solve_block
from .spec import MODE_BYTE as MODE_BYTE_FOR_PREFIX, VALID_FORMATS, block_layout, format_info_positions
from .validator import QRValidator, ValidationResult

logger = logging.getLogger(__name__)

# Mehr Kombinationen werden bei mehrdeutigen Lösungen nicht durchprobiert
DEFAULT_MAX_CANDIDATES = 1 << 16
# Unter einer Struktur-Annahme dürfen höchstens so viele Bits offen bleiben (werden durchprobiert)
STRUCTURE_MAX_FREE_BITS = 12
# Formate mit bis zu so vielen zusätzlichen Abweichungen gegenüber dem besten werden zuerst geprüft
FORMAT_SLACK = 2


@dataclass
class FormatCandidate:
    ec_level: str
    mask: int
    mismatches: int   # bekannte Format-Bits (beide Kopien), die nicht passen
    known_bits: int   # Anzahl bekannter Format-Bits (beide Kopien)

    @property
    def score(self) -> float:
        """0..1: wie gut die bekannten Format-Bits passen (0.5 wenn keine bekannt)"""
        if self.known_bits == 0:
            return 0.5
        return max(0.0, 1.0 - self.mismatches / self.known_bits * 4)


def rank_formats(matrix: QRMatrix) -> List[FormatCandidate]:
    """Alle 32 Format-Kombinationen, sortiert nach Abweichung von den bekannten Format-Bits"""
    positions = [p for copy in format_info_positions(matrix.size) for p in enumerate(copy)]
    known = [(i, r, c) for i, (r, c) in positions if matrix.locked[r, c]]
    candidates = []
    for bits, (level, mask) in VALID_FORMATS.items():
        mismatches = sum(1 for i, r, c in known if int(matrix.grid[r, c] == 1) != (bits >> i) & 1)
        candidates.append(FormatCandidate(level, mask, mismatches, len(known)))
    candidates.sort(key=lambda f: f.mismatches)
    return candidates


@dataclass
class _Candidate:
    """Eine vollständige Lösung (vor dem Rendern)"""
    text: str
    padding_ok: bool
    fmt: FormatCandidate
    codewords: List[int]
    unknown_codewords: int
    corrected_errors: int
    ambiguous_bits: int
    content: float    # Inhalts-Score 0..1 (URL/Wörterbuch/Lesbarkeit)
    complete: bool    # False, wenn nicht alle mehrdeutigen Lösungen durchprobiert wurden
    assumption: str = ''  # Struktur-Annahme, unter der die Lösung eindeutig ist (leer = keine nötig)


# Obergrenze der Confidence, wenn der Lösungsraum nicht vollständig durchsucht wurde
INCOMPLETE_CONFIDENCE_CAP = 50.0


class Reconstructor:
    """
    Rekonstruiert eine teilweise bekannte QR-Matrix (matrix.locked = bekannt).

    Liefert ValidationResults im selben Format wie die BruteforceEngine (method="rs").
    """

    def __init__(self, matrix: QRMatrix, validator: Optional[QRValidator] = None, known_prefix: str = ''):
        """
        Args:
            known_prefix: bekannter Textanfang (z.B. "https://"), hilft bei mehrdeutigem Schaden
        """
        self.matrix = matrix
        self.validator = validator or QRValidator()
        self.known_prefix = known_prefix.encode('utf-8')
        self.progress_callback: Optional[Callable] = None
        self.result_callback: Optional[Callable] = None
        self._should_stop = False
        self.stats: Dict[str, Any] = {'tested': 0, 'valid': 0, 'start_time': None, 'end_time': None, 'mode': 'rs'}

    def stop(self):
        self._should_stop = True

    @property
    def stop_requested(self) -> bool:
        return self._should_stop

    def set_progress_callback(self, callback):
        self.progress_callback = callback

    def set_result_callback(self, callback):
        self.result_callback = callback

    def get_stats(self) -> Dict:
        stats = self.stats.copy()
        if stats['start_time']:
            stats['elapsed'] = (stats['end_time'] or time.time()) - stats['start_time']
        return stats

    def run(self, max_time: float = 60, max_candidates: int = DEFAULT_MAX_CANDIDATES,
            allow_errors: bool = True, max_results: int = 50) -> List[ValidationResult]:
        """
        Args:
            max_time: Zeitlimit in Sekunden
            max_candidates: maximale Anzahl Kombinationen bei mehrdeutigen Lösungen
            allow_errors: falsch abgemalte (bekannte) Codewörter per Fehlerkorrektur zulassen
            max_results: so viele beste Lösungen werden gerendert und zurückgegeben

        Returns:
            Lösungen, ein Eintrag pro Inhalt, nach Confidence sortiert
        """
        self._should_stop = False
        start = time.time()
        deadline = start + max_time
        self.stats = {'tested': 0, 'valid': 0, 'start_time': start, 'end_time': None, 'mode': 'rs'}

        formats = rank_formats(self.matrix)
        best_mismatch = formats[0].mismatches
        # Erst die plausibelsten Formate; die übrigen nur, wenn diese nichts ergeben
        first_pass = [f for f in formats if f.mismatches <= best_mismatch + FORMAT_SLACK]
        second_pass = [f for f in formats if f.mismatches > best_mismatch + FORMAT_SLACK]

        candidates: Dict[str, _Candidate] = {}
        for pass_formats in (first_pass, second_pass):
            for fmt in pass_formats:
                if self._should_stop or time.time() > deadline:
                    break
                for cand in self._solve_format(fmt, max_candidates, allow_errors, deadline):
                    existing = candidates.get(cand.text)
                    if existing is None or self._rank_key(cand) > self._rank_key(existing):
                        candidates[cand.text] = cand
                self.stats['tested'] += 1
                self._report_progress(len(formats), len(candidates))
            if candidates:
                break

        best = sorted(candidates.values(), key=self._rank_key, reverse=True)[:max_results]
        results = []
        for cand in best:
            result = self._build_result(cand, total_candidates=len(candidates))
            results.append(result)
            self.stats['valid'] += 1
            if self.result_callback:
                self.result_callback(result)

        self.stats['end_time'] = time.time()
        logger.info("RS-Rekonstruktion: %d Formate geprüft, %d Lösungen in %.2fs",
                    self.stats['tested'], len(candidates), self.stats['end_time'] - start)
        results.sort(key=lambda r: r.confidence, reverse=True)
        return results

    def _report_progress(self, total, valid):
        if self.progress_callback:
            self.progress_callback(self.stats['tested'], valid, total)

    @staticmethod
    def _rank_key(cand: _Candidate) -> Tuple:
        return (cand.padding_ok, -cand.fmt.mismatches, -cand.corrected_errors, -cand.ambiguous_bits,
                cand.content)

    def _solve_format(self, fmt: FormatCandidate, max_candidates: int, allow_errors: bool,
                      deadline: float) -> List[_Candidate]:
        version = self.matrix.version
        grid = (self.matrix.grid == 1).astype(np.uint8)
        reading = read_codewords(grid, self.matrix.locked, version, fmt.mask)
        value_blocks = deinterleave(reading.values, version, fmt.ec_level)
        mask_blocks = deinterleave(reading.known_masks, version, fmt.ec_level)

        solutions: List[BlockSolution] = []
        for values, masks, (_, nsym) in zip(value_blocks, mask_blocks, block_layout(version, fmt.ec_level)):
            solution = solve_block(values, masks, nsym, allow_errors=allow_errors)
            if solution is None:
                return []  # mit diesem Format kann der Block nicht gültig sein
            solutions.append(solution)

        free_bits = sum(s.free_bits for s in solutions)
        unknown = sum(s.unknown_codewords for s in solutions)
        errors = sum(s.corrected_errors for s in solutions)
        if free_bits > 0:
            # Mehrdeutig: erst mit Wissen über den Aufbau der Daten (Modus, Länge, Füllbytes) versuchen
            structured = self._solve_with_structure(fmt, value_blocks, mask_blocks, unknown, deadline)
            if structured:
                return structured
        combos = min(1 << free_bits, max_candidates)
        complete = combos == (1 << free_bits)
        if not complete:
            logger.warning("Format %s/%d: 2^%d mögliche Lösungen, prüfe nur %d",
                           fmt.ec_level, fmt.mask, free_bits, combos)

        # Gesamtauswahl → Auswahl je Block (Bits der Reihe nach auf die Blöcke verteilt)
        results = []
        yield_gil = GilYielder()
        for selection in range(combos):
            if selection % 1024 == 0 and (self._should_stop or time.time() > deadline):
                break
            yield_gil()
            blocks = []
            rest = selection
            for s in solutions:
                blocks.append(s.codeword(rest & ((1 << s.free_bits) - 1)))
                rest >>= s.free_bits
            data = bytes(b for block, s in zip(blocks, solutions) for b in block[:s.data_len])
            try:
                decoded = decode_data(data, version)
            except DataDecodeError:
                continue
            results.append(_Candidate(
                text=decoded.text,
                padding_ok=decoded.padding_ok,
                fmt=fmt,
                codewords=interleave(blocks, version, fmt.ec_level),
                unknown_codewords=unknown,
                corrected_errors=errors,
                ambiguous_bits=free_bits,
                content=self.validator.content_scorer.score_content(decoded.text).total_score,
                complete=complete,
            ))
        return results

    def _solve_with_structure(self, fmt: FormatCandidate, value_blocks: List[List[int]],
                              mask_blocks: List[List[int]], unknown: int, deadline: float) -> List[_Candidate]:
        """
        Probiert Struktur-Hypothesen (core/structure.py): Jede legt Modus-Indikator, Zeichenzähler,
        Terminator und Füllbytes fest. Nur Hypothesen, die zu den bekannten Bits passen und die Lösung
        eindeutig machen, ergeben Kandidaten.
        """
        version, level = self.matrix.version, fmt.ec_level
        layout = block_layout(version, level)
        # Datenstrom-Byte → (Block, Position im Block)
        data_positions = [(b, i) for b, (data_len, _) in enumerate(layout) for i in range(data_len)]

        def attempt(fixed) -> Optional[List[BlockSolution]]:
            fixed_values, fixed_masks = fixed
            values = [list(v) for v in value_blocks]
            masks = [list(m) for m in mask_blocks]
            for (b, i), fv, fm in zip(data_positions, fixed_values, fixed_masks):
                if not fm:
                    continue
                overlap = masks[b][i] & fm
                if (values[b][i] ^ fv) & overlap:
                    return None  # widerspricht bekannten Pixeln
                masks[b][i] |= fm
                values[b][i] = (values[b][i] & ~fm & 0xFF) | fv
            solutions = []
            free = 0
            for vals, msks, (_, nsym) in zip(values, masks, layout):
                solution = solve_block(vals, msks, nsym, allow_errors=False)
                if solution is None:
                    return None
                free += solution.free_bits
                if free > STRUCTURE_MAX_FREE_BITS:
                    return None
                solutions.append(solution)
            return solutions

        candidates: List[Tuple[Hypothesis, List[BlockSolution]]] = []
        yield_gil = GilYielder()
        for hypothesis in hypotheses(version, level, self.known_prefix):
            if self._should_stop or time.time() > deadline:
                break
            yield_gil()
            fixed = constraints(hypothesis, version, level)
            solutions = attempt(fixed) if fixed else None
            if solutions is not None:
                candidates.append((hypothesis, solutions))
        if not candidates and self.known_prefix:
            fixed = prefix_constraints(self.known_prefix, version, level)
            solutions = attempt(fixed) if fixed else None
            if solutions is not None:
                candidates.append((Hypothesis(MODE_BYTE_FOR_PREFIX, len(self.known_prefix), self.known_prefix),
                                   solutions))

        results = []
        for hypothesis, solutions in candidates:
            free = sum(s.free_bits for s in solutions)
            for selection in range(1 << free):
                if selection % 256 == 0 and (self._should_stop or time.time() > deadline):
                    break
                blocks, rest = [], selection
                for s in solutions:
                    blocks.append(s.codeword(rest & ((1 << s.free_bits) - 1)))
                    rest >>= s.free_bits
                data = bytes(byte for block, (data_len, _) in zip(blocks, layout) for byte in block[:data_len])
                try:
                    decoded = decode_data(data, version)
                except DataDecodeError:
                    continue
                results.append(_Candidate(
                    text=decoded.text,
                    padding_ok=decoded.padding_ok,
                    fmt=fmt,
                    codewords=interleave(blocks, version, level),
                    unknown_codewords=unknown,
                    corrected_errors=0,
                    ambiguous_bits=free,
                    content=self.validator.content_scorer.score_content(decoded.text).total_score,
                    complete=True,
                    assumption=hypothesis.describe(),
                ))
        if results:
            logger.info("Format %s/%d: %d Lösung(en) über Struktur-Annahmen", level, fmt.mask, len(results))
        return results

    def _build_result(self, cand: _Candidate, total_candidates: int) -> ValidationResult:
        """
        Rendert die Lösung, lässt sie von pyzbar gegenprüfen und berechnet die Confidence:
          40  RS-konsistent (Voraussetzung für jede Lösung)
        + 20  Format-Bits passen (anteilig)
        + 15  Terminator/Padding korrekt
        + 25  Eindeutigkeit: eindeutig → voll (×0.8, wenn nur unter einer Struktur-Annahme),
              sonst halber Inhalts-Score
        -  5  je korrigiertem (falsch abgemaltem) Codewort
        Wurde ein mehrdeutiger Lösungsraum nur teilweise durchsucht, höchstens INCOMPLETE_CONFIDENCE_CAP.
        """
        grid = render_matrix(self.matrix.version, cand.fmt.ec_level, cand.fmt.mask, cand.codewords)
        rendered = QRMatrix(self.matrix.size)
        rendered.grid = grid.astype(int)
        rendered.locked[:] = True
        check = self.validator.validate(rendered)
        pyzbar_text = check.decoded_data
        content = self.validator.content_scorer.score_content(cand.text)

        unique = total_candidates == 1 and cand.ambiguous_bits == 0
        certainty = 1.0 if unique else 0.5 * content.total_score
        if cand.assumption:
            certainty *= 0.8
        confidence = (40 + 20 * cand.fmt.score + 15 * cand.padding_ok + 25 * certainty
                      - 5 * cand.corrected_errors)
        if not cand.complete:
            confidence = min(confidence, INCOMPLETE_CONFIDENCE_CAP)
        confidence = max(0.0, min(100.0, confidence))

        debug = (f"RS | Format {cand.fmt.ec_level}/Maske {cand.fmt.mask} "
                 f"({cand.fmt.mismatches}/{cand.fmt.known_bits} Format-Bits abweichend) | "
                 f"{cand.unknown_codewords} Codewörter rekonstruiert | "
                 f"{cand.corrected_errors} Fehler korrigiert | "
                 f"2^{cand.ambiguous_bits} Lösungen{'' if cand.complete else ' (nicht alle geprüft)'} | "
                 f"Padding {'ok' if cand.padding_ok else 'abweichend'} | pyzbar: {pyzbar_text!r}")
        if cand.assumption:
            debug += f" | Annahme: {cand.assumption}"

        check.is_valid = True
        check.confidence = confidence
        check.decoded_data = cand.text
        check.matrix = grid.astype(int)
        check.error_correction_level = cand.fmt.ec_level
        check.content_score = content.total_score * 100
        check.is_url = content.is_url
        check.url_type = content.url_type
        check.german_words = len(content.german_matches)
        check.english_words = len(content.english_matches)
        check.method = "rs"
        check.mask_pattern = cand.fmt.mask
        check.unknown_codewords = cand.unknown_codewords
        check.corrected_errors = cand.corrected_errors
        check.ambiguous_bits = cand.ambiguous_bits
        check.padding_ok = cand.padding_ok
        check.assumption = cand.assumption
        # Ein Standard-Decoder akzeptiert das rekonstruierte Symbol. Den Text vergleichen wir bewusst
        # nicht: zbar rät die Zeichenkodierung von Byte-Segmenten und liest UTF-8 teils als Shift-JIS.
        check.decoder_confirmed = pyzbar_text is not None
        check.debug_info = debug
        return check
