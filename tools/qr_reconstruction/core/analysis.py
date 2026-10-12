"""
Lösbarkeitsanalyse für den Editor

Beantwortet schon während des Abmalens: Ist der Code mit den bekannten Pixeln eindeutig rekonstruierbar,
mehrdeutig oder widersprüchlich - und wo liegen die Problemstellen?

Nutzt dieselben Bausteine wie der Reconstructor, aber ohne Lösungen aufzuzählen oder zu dekodieren
(nur die lineare RS-Analyse je Block), daher schnell genug für jede Änderung im Editor.
"""

import time
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np

from .gil import GilYielder
from .codewords import data_module_order, deinterleave, interleave_order, read_codewords
from .qr_matrix import QRMatrix
from .reconstructor import FormatCandidate, rank_formats
from .rs_decoder import solve_block
from .spec import block_layout, format_info_positions, num_total_codewords

# Gesamturteil
VERDICT_COMPLETE = 'complete'          # keine unbekannten Pixel
VERDICT_UNIQUE = 'unique'              # eindeutig lösbar
VERDICT_CORRECTABLE = 'correctable'    # eindeutig, aber nur mit Korrektur falsch abgemalter Pixel
VERDICT_AMBIGUOUS = 'ambiguous'        # mehrere Lösungen möglich
VERDICT_INCONSISTENT = 'inconsistent'  # keine Lösung mit den bekannten Pixeln

# Status je Block
BLOCK_OK = 'ok'
BLOCK_CORRECTED = 'corrected'
BLOCK_AMBIGUOUS = 'ambiguous'
BLOCK_UNSOLVABLE = 'unsolvable'


@dataclass
class BlockStatus:
    index: int
    nsym: int                  # EC-Codewörter
    unknown_codewords: int     # Codewörter mit mindestens einem unbekannten Bit
    unknown_bits: int
    free_bits: Optional[int]   # None = Block widersprüchlich
    corrected_errors: int = 0

    @property
    def status(self) -> str:
        if self.free_bits is None:
            return BLOCK_UNSOLVABLE
        if self.free_bits > 0:
            return BLOCK_AMBIGUOUS
        if self.corrected_errors:
            return BLOCK_CORRECTED
        return BLOCK_OK


@dataclass
class SolvabilityReport:
    verdict: str
    message: str
    unknown_cells: int
    format: Optional[FormatCandidate] = None
    viable_formats: int = 0          # Formate, mit denen alle Blöcke konsistent sind
    blocks: List[BlockStatus] = field(default_factory=list)
    # Für das Overlay: je Modul der Block-Index (-1 = kein Datenmodul) und ob sein Codewort unbekannte Bits hat
    module_block: Optional[np.ndarray] = None
    module_affected: Optional[np.ndarray] = None
    # Für den Inspektor: je Modul Index in der übertragenen Codewort-Folge (-1 = kein Datenmodul) und Bit (7 = MSB),
    # je Codewort (Block, Position im Block, ist EC-Codewort)
    module_codeword: Optional[np.ndarray] = None
    module_bit: Optional[np.ndarray] = None
    codeword_location: List[tuple] = field(default_factory=list)
    format_cells: List[tuple] = field(default_factory=list)

    @property
    def free_bits(self) -> int:
        return sum(b.free_bits or 0 for b in self.blocks)


def _analyze_format(matrix: QRMatrix, fmt: FormatCandidate) -> List[BlockStatus]:
    grid = (matrix.grid == 1).astype(np.uint8)
    reading = read_codewords(grid, matrix.locked, matrix.version, fmt.mask)
    value_blocks = deinterleave(reading.values, matrix.version, fmt.ec_level)
    mask_blocks = deinterleave(reading.known_masks, matrix.version, fmt.ec_level)
    statuses = []
    yield_gil = GilYielder()  # läuft im Editor in einem Hintergrund-Thread
    for i, (values, masks, (_, nsym)) in enumerate(
            zip(value_blocks, mask_blocks, block_layout(matrix.version, fmt.ec_level))):
        yield_gil()
        solution = solve_block(values, masks, nsym)
        statuses.append(BlockStatus(
            index=i,
            nsym=nsym,
            unknown_codewords=sum(1 for m in masks if m != 0xFF),
            unknown_bits=sum(8 - bin(m).count('1') for m in masks),
            free_bits=None if solution is None else solution.free_bits,
            corrected_errors=0 if solution is None else solution.corrected_errors,
        ))
    return statuses


def _module_maps(matrix: QRMatrix, ec_level: str):
    """Block-Index je Datenmodul und ob das zugehörige Codewort unbekannte Bits enthält"""
    version = matrix.version
    rows, cols = data_module_order(version)
    count = num_total_codewords(version) * 8
    rows, cols = rows[:count], cols[:count]
    order = interleave_order(version, ec_level)

    codeword_block = np.array([b for b, _ in order], dtype=int)
    module_codeword = np.arange(count) // 8
    module_block = np.full((matrix.size, matrix.size), -1, dtype=int)
    module_block[rows, cols] = codeword_block[module_codeword]

    unknown_module = ~matrix.locked[rows, cols]
    codeword_unknown = np.zeros(len(order), dtype=bool)
    np.logical_or.at(codeword_unknown, module_codeword, unknown_module)
    module_affected = np.zeros((matrix.size, matrix.size), dtype=bool)
    module_affected[rows, cols] = codeword_unknown[module_codeword]

    codeword_map = np.full((matrix.size, matrix.size), -1, dtype=int)
    codeword_map[rows, cols] = module_codeword
    bit_map = np.full((matrix.size, matrix.size), -1, dtype=int)
    bit_map[rows, cols] = 7 - np.arange(count) % 8
    layout = block_layout(version, ec_level)
    locations = [(b, pos, pos >= layout[b][0]) for b, pos in order]
    return module_block, module_affected, codeword_map, bit_map, locations


def analyze_solvability(matrix: QRMatrix, max_time: float = 0.5) -> SolvabilityReport:
    """
    Analysiert, ob und wie eindeutig die Matrix rekonstruierbar ist.

    Geprüft werden die Formate mit den wenigsten Abweichungen zu den bekannten Format-Bits
    (bei unbekannter Format-Info also alle 32), höchstens bis `max_time`.
    """
    deadline = time.time() + max_time
    unknown_cells = int((~matrix.locked).sum())
    format_cells = [p for copy in format_info_positions(matrix.size) for p in copy]

    formats = rank_formats(matrix)
    best_mismatch = formats[0].mismatches
    candidates = [f for f in formats if f.mismatches == best_mismatch]

    viable: List[Tuple[FormatCandidate, List[BlockStatus]]] = []
    first: Optional[Tuple[FormatCandidate, List[BlockStatus]]] = None
    for fmt in candidates:
        if viable and time.time() > deadline:
            break
        statuses = _analyze_format(matrix, fmt)
        if first is None:
            first = (fmt, statuses)
        if all(s.free_bits is not None for s in statuses):
            viable.append((fmt, statuses))

    if viable:
        # Bestes Format: wenigste Freiheitsgrade, dann wenigste Korrekturen, dann die meisten EC-Codewörter.
        # Letzteres, weil RS-Codes gleicher Länge verschachtelt sind: Ein gültiger Block mit 16 EC-Codewörtern
        # ist auch mit 10 gültig - das Format mit mehr bestandenen Prüfungen ist das plausiblere.
        fmt, statuses = min(viable, key=lambda v: (sum(s.free_bits or 0 for s in v[1]),
                                                   sum(s.corrected_errors for s in v[1]),
                                                   -sum(s.nsym for s in v[1])))
    else:
        assert first is not None  # es gibt immer mindestens einen Format-Kandidaten
        fmt, statuses = first

    module_block, module_affected, module_codeword, module_bit, locations = _module_maps(matrix, fmt.ec_level)
    report = SolvabilityReport(
        verdict='', message='', unknown_cells=unknown_cells, format=fmt, viable_formats=len(viable),
        blocks=statuses, module_block=module_block, module_affected=module_affected,
        module_codeword=module_codeword, module_bit=module_bit, codeword_location=locations,
        format_cells=format_cells,
    )

    free_bits = report.free_bits
    errors = sum(s.corrected_errors for s in statuses)
    if not viable:
        report.verdict = VERDICT_INCONSISTENT
        bad = sum(1 for s in statuses if s.status == BLOCK_UNSOLVABLE)
        report.message = (f"Keine gültige Lösung: {bad} von {len(statuses)} Blöcken passen nicht zu den "
                          f"bekannten Pixeln. Zu viel Schaden oder falsch abgemalte Pixel.")
    elif unknown_cells == 0 and errors == 0:
        report.verdict = VERDICT_COMPLETE
        report.message = "Alle Pixel bekannt - der Code ist vollständig und gültig."
    elif free_bits > 0:
        report.verdict = VERDICT_AMBIGUOUS
        report.message = (f"Mehrdeutig: 2^{free_bits} mögliche Lösungen. Mehr Pixel als bekannt markieren, "
                          f"vor allem in den orange markierten Codewörtern.")
    elif errors > 0:
        report.verdict = VERDICT_CORRECTABLE
        report.message = (f"Lösbar, aber {errors} Codewort(e) widersprechen den bekannten Pixeln und werden "
                          f"korrigiert - evtl. falsch abgemalt.")
    else:
        report.verdict = VERDICT_UNIQUE
        report.message = "Eindeutig lösbar."

    if report.verdict != VERDICT_INCONSISTENT and report.viable_formats > 1:
        report.message += f" ({report.viable_formats} Formate möglich, die Rekonstruktion prüft alle.)"
    return report
