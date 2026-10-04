"""
Reed-Solomon-Rekonstruktion eines einzelnen QR-Blocks

QR nutzt RS über GF(256) (Polynom 0x11d, Generator 2, erste Nullstelle α^0).
Ein Block c_0..c_{n-1} ist gültig, wenn alle Syndrome S_j = Σ c_i·α^(j·(n-1-i)), j < nsym, null sind.

Weil diese Syndrome linear sind - auch auf Bit-Ebene über GF(2) -, wird jedes unbekannte Bit eine
Variable und die Syndrome werden zu 8·nsym binären Gleichungen. Gauß-Elimination liefert exakt
alle Lösungen (ein affiner Raum der Dimension "free_bits"), ohne Bruteforce. Teilweise bekannte
Codewörter tragen dabei jedes bekannte Bit bei, statt nur als Erasure zu zählen.

Sind dagegen *bekannte* Bits falsch (falsch abgemalt), hat das Gleichungssystem keine Lösung;
dann übernimmt klassische Fehler+Erasure-Korrektur (reedsolo): 2·Fehler + Erasures ≤ nsym.
"""

from dataclasses import dataclass, field
from functools import lru_cache
from typing import List, Optional, Tuple

import numpy as np

try:
    from reedsolo import RSCodec, ReedSolomonError
    REEDSOLO_AVAILABLE = True
except ImportError:  # Fehlerkorrektur bleibt dann aus, Erasures funktionieren trotzdem
    REEDSOLO_AVAILABLE = False

# GF(256)-Tabellen
_EXP = [0] * 510
_LOG = [0] * 256
_x = 1
for _i in range(255):
    _EXP[_i] = _x
    _LOG[_x] = _i
    _x <<= 1
    if _x & 0x100:
        _x ^= 0x11D
for _i in range(255, 510):
    _EXP[_i] = _EXP[_i - 255]


def gf_mul(a: int, b: int) -> int:
    if a == 0 or b == 0:
        return 0
    return _EXP[_LOG[a] + _LOG[b]]


_EXP_NP = np.array(_EXP, dtype=np.int64)
_LOG_NP = np.array(_LOG, dtype=np.int64)


@lru_cache(maxsize=None)
def _syndrome_exponents(n: int, nsym: int) -> np.ndarray:
    """Exponent von α für Codewort i in Syndrom j: j·(n-1-i) mod 255"""
    j = np.arange(nsym)[:, None]
    i = np.arange(n)[None, :]
    return (j * (n - 1 - i)) % 255


def syndromes(codeword: List[int], nsym: int) -> List[int]:
    """S_j = Σ c_i·α^(j·(n-1-i)) für j = 0..nsym-1 (vektorisiert: XOR-Summe der Produkte über log/exp)"""
    c = np.asarray(codeword, dtype=np.int64)
    terms = _EXP_NP[(_LOG_NP[c][None, :] + _syndrome_exponents(len(c), nsym)) % 255]
    terms[:, c == 0] = 0
    return np.bitwise_xor.reduce(terms, axis=1).tolist()


@lru_cache(maxsize=None)
def _codec(nsym: int):
    """reedsolo baut bei jeder Instanz seine Tabellen neu - daher je nsym nur einmal"""
    return RSCodec(nsym)


def _pack(values: List[int]) -> int:
    """GF(256)-Werte je 8 Bit nebeneinander in einen Bitvektor"""
    packed = 0
    for j, v in enumerate(values):
        packed |= v << (8 * j)
    return packed


@dataclass
class BlockSolution:
    """
    Lösungsraum eines Blocks: base XOR beliebige Kombination der null_basis-Vektoren.
    Jeder Vektor ist eine Bitmaske über `variables` (Position im Block, Bitnummer).
    """
    base: List[int]
    data_len: int
    variables: List[Tuple[int, int]] = field(default_factory=list)
    null_basis: List[int] = field(default_factory=list)
    corrected_errors: int = 0   # bekannte Codewörter, die als falsch korrigiert wurden
    unknown_codewords: int = 0  # Codewörter mit mindestens einem unbekannten Bit

    @property
    def free_bits(self) -> int:
        return len(self.null_basis)

    def codeword(self, selection: int = 0) -> List[int]:
        """Konkreter Block für eine Auswahl (Bit i = null_basis[i] verwenden)"""
        if not selection:
            return list(self.base)
        flips = 0
        i = 0
        while selection:
            if selection & 1:
                flips ^= self.null_basis[i]
            selection >>= 1
            i += 1
        result = list(self.base)
        u = 0
        while flips:
            if flips & 1:
                pos, bit = self.variables[u]
                result[pos] ^= 1 << bit
            flips >>= 1
            u += 1
        return result


def _solve_linear(values: List[int], known_masks: List[int], nsym: int) -> Optional[BlockSolution]:
    n = len(values)
    variables = [(pos, bit) for pos in range(n) for bit in range(8)
                 if not (known_masks[pos] >> bit) & 1]
    # Unbekannte Bits als 0 → Syndrom des bekannten Anteils = rechte Seite
    base = [v & m for v, m in zip(values, known_masks)]
    rhs = _pack(syndromes(base, nsym))

    # XOR-Basis über die Spalten (Beitrag jedes Variablen-Bits zu den Syndromen),
    # jeweils mit Buchführung, welche Variablen zur Basis-Spalte kombiniert wurden
    pivots = {}  # höchstes Bit → (Spalte, Variablen-Kombination)
    null_basis = []
    for u, (pos, bit) in enumerate(variables):
        exponent = n - 1 - pos
        column = _pack([gf_mul(1 << bit, _EXP[(j * exponent) % 255]) for j in range(nsym)])
        combo = 1 << u
        while column:
            top = column.bit_length() - 1
            if top not in pivots:
                pivots[top] = (column, combo)
                break
            pivot_col, pivot_combo = pivots[top]
            column ^= pivot_col
            combo ^= pivot_combo
        else:
            null_basis.append(combo)  # abhängige Spalte → freier Freiheitsgrad

    # Partikuläre Lösung: rechte Seite durch die Basis ausdrücken
    solution = 0
    while rhs:
        top = rhs.bit_length() - 1
        if top not in pivots:
            return None  # inkonsistent: bekannte Bits widersprechen dem RS-Code
        pivot_col, pivot_combo = pivots[top]
        rhs ^= pivot_col
        solution ^= pivot_combo

    u = 0
    while solution:
        if solution & 1:
            pos, bit = variables[u]
            base[pos] |= 1 << bit
        solution >>= 1
        u += 1

    return BlockSolution(base=base, data_len=n - nsym, variables=variables, null_basis=null_basis)


def _correct_with_errors(values: List[int], known_masks: List[int], nsym: int) -> Optional[BlockSolution]:
    """Fehler+Erasure-Korrektur für den Fall, dass bekannte Codewörter falsch sind"""
    if not REEDSOLO_AVAILABLE:
        return None
    erase_pos = [i for i, m in enumerate(known_masks) if m != 0xFF]
    if len(erase_pos) + 2 > nsym:  # Platz für mindestens einen Fehler nötig
        return None
    try:
        _, corrected, _ = _codec(nsym).decode(bytearray(values), erase_pos=erase_pos or None)
    except ReedSolomonError:
        return None
    corrected = list(corrected)
    if any(syndromes(corrected, nsym)):
        return None
    errors = sum(1 for i, m in enumerate(known_masks) if m == 0xFF and corrected[i] != values[i])
    # Bekannte Bits in teilweise bekannten Codewörtern zählen ebenfalls als Fehler, wenn sie abweichen
    errors += sum(1 for i, m in enumerate(known_masks)
                  if 0 < m < 0xFF and (corrected[i] ^ values[i]) & m)
    return BlockSolution(base=corrected, data_len=len(values) - nsym, corrected_errors=errors)


def solve_block(values: List[int], known_masks: List[int], nsym: int,
                allow_errors: bool = True) -> Optional[BlockSolution]:
    """
    Rekonstruiert einen RS-Block.

    Args:
        values: Codewörter des Blocks (Daten + EC), unbekannte Bits beliebig
        known_masks: je Codewort Bitmaske der bekannten Bits
        nsym: Anzahl EC-Codewörter
        allow_errors: falsch bekannte Codewörter per Fehlerkorrektur zulassen

    Returns:
        Lösungsraum oder None, wenn der Block mit diesen Daten nicht gültig sein kann
    """
    unknown = sum(1 for m in known_masks if m != 0xFF)
    solution = _solve_linear(values, known_masks, nsym)
    if solution is None and allow_errors:
        solution = _correct_with_errors(values, known_masks, nsym)
    if solution is not None:
        solution.unknown_codewords = unknown
    return solution
