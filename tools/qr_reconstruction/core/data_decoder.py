"""
Dekodiert den Bitstrom der Datencodewörter in Text (Spezifikation 7.4)

Unterstützt: Numeric, Alphanumeric, Byte (UTF-8 / Latin-1 / ECI), Kanji, FNC1-Indikatoren.
Structured Append wird übersprungen (nur der Inhalt dieses Symbols wird geliefert).
"""

from dataclasses import dataclass, field
from typing import List, Optional

from .spec import (
    ALPHANUMERIC_CHARSET, MODE_ALPHANUMERIC, MODE_BYTE, MODE_ECI, MODE_FNC1_FIRST,
    MODE_FNC1_SECOND, MODE_KANJI, MODE_NUMERIC, MODE_STRUCTURED_APPEND, MODE_TERMINATOR,
    char_count_bits,
)

PAD_BYTES = (0xEC, 0x11)

# ECI-Zuweisungsnummer → Python-Codec (Auswahl der gebräuchlichsten)
ECI_CODECS = {
    1: 'latin-1', 3: 'latin-1', 4: 'iso8859-2', 5: 'iso8859-3', 6: 'iso8859-4', 7: 'iso8859-5',
    8: 'iso8859-6', 9: 'iso8859-7', 10: 'iso8859-8', 11: 'iso8859-9', 13: 'iso8859-11',
    15: 'iso8859-13', 16: 'iso8859-14', 17: 'iso8859-15', 18: 'iso8859-16', 20: 'shift_jis',
    21: 'cp1250', 22: 'cp1251', 23: 'cp1252', 24: 'cp1256', 25: 'utf-16-be', 26: 'utf-8',
    27: 'ascii', 28: 'big5', 29: 'gb18030', 30: 'euc-kr',
}


class DataDecodeError(ValueError):
    pass


@dataclass
class DecodedData:
    text: str
    modes: List[str] = field(default_factory=list)
    # Plausibilität: korrekter Terminator und Padding nach Spezifikation
    # (falsch rekonstruierte Daten verletzen das fast immer)
    padding_ok: bool = True


class _BitReader:
    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0

    @property
    def remaining(self) -> int:
        return len(self.data) * 8 - self.pos

    def read(self, n: int) -> int:
        if n > self.remaining:
            raise DataDecodeError("Bitstrom endet unerwartet")
        value = 0
        for _ in range(n):
            byte = self.data[self.pos >> 3]
            value = (value << 1) | ((byte >> (7 - (self.pos & 7))) & 1)
            self.pos += 1
        return value


def _decode_bytes(raw: bytes, codec: Optional[str]) -> str:
    if codec:
        return raw.decode(codec, errors='replace')
    # Ohne ECI ist laut Standard ISO-8859-1 gemeint, in der Praxis meist UTF-8
    try:
        return raw.decode('utf-8')
    except UnicodeDecodeError:
        return raw.decode('latin-1')


def decode_data(data: bytes, version: int) -> DecodedData:
    """
    Dekodiert die (de-interleavten, aneinandergehängten) Datencodewörter.

    Raises:
        DataDecodeError bei strukturell ungültigem Bitstrom
    """
    reader = _BitReader(data)
    parts: List[str] = []
    modes: List[str] = []
    codec: Optional[str] = None
    padding_ok = True

    while reader.remaining >= 4:
        mode = reader.read(4)
        if mode == MODE_TERMINATOR:
            break

        if mode == MODE_NUMERIC:
            count = reader.read(char_count_bits(mode, version))
            digits = []
            while count >= 3:
                value = reader.read(10)
                if value > 999:
                    raise DataDecodeError("Ungültige Numeric-Gruppe")
                digits.append(f"{value:03d}")
                count -= 3
            if count == 2:
                value = reader.read(7)
                if value > 99:
                    raise DataDecodeError("Ungültige Numeric-Gruppe")
                digits.append(f"{value:02d}")
            elif count == 1:
                value = reader.read(4)
                if value > 9:
                    raise DataDecodeError("Ungültige Numeric-Gruppe")
                digits.append(str(value))
            parts.append(''.join(digits))
            modes.append('numeric')

        elif mode == MODE_ALPHANUMERIC:
            count = reader.read(char_count_bits(mode, version))
            chars = []
            while count >= 2:
                value = reader.read(11)
                if value >= 45 * 45:
                    raise DataDecodeError("Ungültiges Alphanumeric-Paar")
                chars.append(ALPHANUMERIC_CHARSET[value // 45] + ALPHANUMERIC_CHARSET[value % 45])
                count -= 2
            if count == 1:
                value = reader.read(6)
                if value >= 45:
                    raise DataDecodeError("Ungültiges Alphanumeric-Zeichen")
                chars.append(ALPHANUMERIC_CHARSET[value])
            parts.append(''.join(chars))
            modes.append('alphanumeric')

        elif mode == MODE_BYTE:
            count = reader.read(char_count_bits(mode, version))
            raw = bytes(reader.read(8) for _ in range(count))
            parts.append(_decode_bytes(raw, codec))
            modes.append('byte')

        elif mode == MODE_KANJI:
            count = reader.read(char_count_bits(mode, version))
            kanji = bytearray()
            for _ in range(count):
                value = reader.read(13)
                code = ((value // 0xC0) << 8) | (value % 0xC0)
                code += 0x8140 if code < 0x1F00 else 0xC140
                kanji += code.to_bytes(2, 'big')
            parts.append(bytes(kanji).decode('shift_jis', errors='replace'))
            modes.append('kanji')

        elif mode == MODE_ECI:
            first = reader.read(8)
            if first & 0x80 == 0:
                assignment = first
            elif first & 0xC0 == 0x80:
                assignment = ((first & 0x3F) << 8) | reader.read(8)
            elif first & 0xE0 == 0xC0:
                assignment = ((first & 0x1F) << 16) | reader.read(16)
            else:
                raise DataDecodeError("Ungültige ECI-Kennung")
            codec = ECI_CODECS.get(assignment)
            if codec is None:
                raise DataDecodeError(f"Unbekannte ECI-Zuweisung {assignment}")
            modes.append(f'eci:{assignment}')

        elif mode == MODE_STRUCTURED_APPEND:
            reader.read(16)  # Position, Anzahl, Parität
            modes.append('structured_append')

        elif mode == MODE_FNC1_FIRST:
            modes.append('fnc1')

        elif mode == MODE_FNC1_SECOND:
            reader.read(8)  # Application Indicator
            modes.append('fnc1')

        else:
            raise DataDecodeError(f"Ungültiger Modus-Indikator {mode:04b}")

    else:
        # Kein expliziter Terminator: nur erlaubt, wenn weniger als 4 Bits übrig sind (alle 0)
        if reader.remaining and reader.read(reader.remaining) != 0:
            padding_ok = False

    if not modes:
        raise DataDecodeError("Keine Datensegmente")

    # Rest des aktuellen Bytes muss 0 sein, danach abwechselnd 0xEC / 0x11
    if reader.pos % 8:
        if reader.read(8 - reader.pos % 8) != 0:
            padding_ok = False
    pad_index = 0
    while reader.remaining >= 8:
        if reader.read(8) != PAD_BYTES[pad_index % 2]:
            padding_ok = False
        pad_index += 1

    return DecodedData(text=''.join(parts), modes=modes, padding_ok=padding_ok)
