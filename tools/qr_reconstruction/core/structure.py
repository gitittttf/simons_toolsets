"""
Struktur-Annahmen über den Datenstrom

Die Datencodewörter eines QR-Codes sind nicht beliebig: Auf Modus-Indikator und Zeichenzähler folgen der
Inhalt, ein Terminator (bis zu 4 Null-Bits), Null-Bits bis zur Bytegrenze und dann abwechselnd die
Füllbytes 0xEC/0x11 bis zur Kapazität. Bei kurzen Inhalten in großen Codes ist ein Großteil der Daten
also Füllung - und damit bekannt, sobald Modus und Länge feststehen.

Eine Hypothese (Modus, Länge, optional bekannter Textanfang) liefert daher zusätzliche bekannte Bits.
Der Reconstructor probiert die plausiblen Hypothesen durch und löst das RS-Gleichungssystem jeweils neu.
"""

from dataclasses import dataclass
from typing import Iterator, List, Optional, Tuple

from .spec import (
    ALPHANUMERIC_CHARSET, MODE_ALPHANUMERIC, MODE_BYTE, MODE_NUMERIC, char_count_bits, num_data_codewords,
)
from .data_decoder import PAD_BYTES

MODE_NAMES = {MODE_BYTE: 'Byte', MODE_ALPHANUMERIC: 'Alphanumerisch', MODE_NUMERIC: 'Numerisch'}


@dataclass
class Hypothesis:
    mode: int
    length: int                 # Zeichen (Byte-Modus: Bytes)
    prefix: bytes = b''         # bekannter Textanfang (nur Byte-Modus)

    def describe(self) -> str:
        text = f"{MODE_NAMES[self.mode]}-Modus, {self.length} Zeichen + Standard-Füllung"
        if self.prefix:
            text += f", beginnt mit {self.prefix.decode('utf-8', errors='replace')!r}"
        return text


def content_bits(mode: int, length: int) -> int:
    if mode == MODE_BYTE:
        return 8 * length
    if mode == MODE_ALPHANUMERIC:
        return 11 * (length // 2) + 6 * (length % 2)
    if mode == MODE_NUMERIC:
        return 10 * (length // 3) + (7 if length % 3 == 2 else 4 if length % 3 == 1 else 0)
    raise ValueError(f"Modus {mode} wird nicht unterstützt")


class _BitWriter:
    """Setzt bekannte Bits im Datenstrom (MSB zuerst, wie im QR-Code)"""

    def __init__(self, total_bytes: int):
        self.values = [0] * total_bytes
        self.masks = [0] * total_bytes
        self.pos = 0

    def write(self, value: int, bits: int):
        for i in range(bits - 1, -1, -1):
            self.set_bit(self.pos, (value >> i) & 1)
            self.pos += 1

    def skip(self, bits: int):
        self.pos += bits

    def set_bit(self, pos: int, bit: int):
        byte, offset = divmod(pos, 8)
        shift = 7 - offset
        self.masks[byte] |= 1 << shift
        if bit:
            self.values[byte] |= 1 << shift


def constraints(hypothesis: Hypothesis, version: int, ec_level: str) -> Optional[Tuple[List[int], List[int]]]:
    """
    Bekannte Bits des Datenstroms (Werte, Masken je Datencodewort) unter der Hypothese,
    oder None, wenn der Inhalt nicht in den Code passt.
    """
    capacity = num_data_codewords(version, ec_level)
    count_bits = char_count_bits(hypothesis.mode, version)
    used = 4 + count_bits + content_bits(hypothesis.mode, hypothesis.length)
    if used > capacity * 8 or hypothesis.length >= (1 << count_bits):
        return None

    writer = _BitWriter(capacity)
    writer.write(hypothesis.mode, 4)
    writer.write(hypothesis.length, count_bits)
    content_start = writer.pos
    for byte in hypothesis.prefix[:hypothesis.length]:
        writer.write(byte, 8)
    writer.pos = content_start + content_bits(hypothesis.mode, hypothesis.length)

    # Terminator (bis zu 4 Null-Bits), dann Null-Bits bis zur Bytegrenze
    writer.write(0, min(4, capacity * 8 - writer.pos))
    writer.write(0, (-writer.pos) % 8)
    # Füllbytes bis zur Kapazität
    pad_index = 0
    while writer.pos < capacity * 8:
        writer.write(PAD_BYTES[pad_index % 2], 8)
        pad_index += 1
    return writer.values, writer.masks


def prefix_constraints(prefix: bytes, version: int, ec_level: str) -> Optional[Tuple[List[int], List[int]]]:
    """Nur der Textanfang (Byte-Modus), Länge offen - für den Fall, dass keine Längen-Hypothese passt"""
    capacity = num_data_codewords(version, ec_level)
    count_bits = char_count_bits(MODE_BYTE, version)
    if 4 + count_bits + 8 * len(prefix) > capacity * 8:
        return None
    writer = _BitWriter(capacity)
    writer.write(MODE_BYTE, 4)
    writer.skip(count_bits)
    for byte in prefix:
        writer.write(byte, 8)
    return writer.values, writer.masks


def hypotheses(version: int, ec_level: str, prefix: bytes = b'') -> Iterator[Hypothesis]:
    """
    Plausible Hypothesen, die häufigsten zuerst: Byte-Modus (URLs, Text) vor Alphanumerisch und Numerisch.
    Mit bekanntem Textanfang nur Byte-Modus ab dessen Länge.
    """
    capacity_bits = num_data_codewords(version, ec_level) * 8
    modes = [MODE_BYTE] if prefix else [MODE_BYTE, MODE_ALPHANUMERIC, MODE_NUMERIC]
    if prefix and not prefix.isascii():
        modes = [MODE_BYTE]
    if prefix and all(chr(b) in ALPHANUMERIC_CHARSET for b in prefix):
        modes = [MODE_BYTE, MODE_ALPHANUMERIC]
    for mode in modes:
        count_bits = char_count_bits(mode, version)
        length = len(prefix) if mode == MODE_BYTE else 0
        while 4 + count_bits + content_bits(mode, length) <= capacity_bits and length < (1 << count_bits):
            if length > 0:
                yield Hypothesis(mode, length, prefix if mode == MODE_BYTE else b'')
            length += 1
