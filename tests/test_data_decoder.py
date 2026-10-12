import pytest
import qrcode
import qrcode.util

from tools.qr_reconstruction.core import codewords as cw
from tools.qr_reconstruction.core.data_decoder import DataDecodeError, decode_data
from tools.qr_reconstruction.core.spec import block_layout
from tests.helpers import EC_LEVELS


def data_codewords(text, level='M'):
    qr = qrcode.QRCode(error_correction=EC_LEVELS[level], border=0)
    qr.add_data(text, optimize=3)
    qr.make(fit=True)
    sequence = qrcode.util.create_data(qr.version, EC_LEVELS[level], qr.data_list)
    blocks = cw.deinterleave(sequence, qr.version, level)
    data = bytes(b for block, (dl, _) in zip(blocks, block_layout(qr.version, level)) for b in block[:dl])
    return data, qr.version


class Bits:
    def __init__(self):
        self.bits = ''

    def add(self, value, n):
        self.bits += format(value, f'0{n}b')
        return self

    def to_bytes(self, total):
        bits = self.bits + '0' * (-len(self.bits) % 8)
        data = bytes(int(bits[i:i + 8], 2) for i in range(0, len(bits), 8))
        pad = bytes((0xEC, 0x11)[i % 2] for i in range(total - len(data)))
        return data + pad


@pytest.mark.parametrize('text', [
    '0123456789012', 'HELLO WORLD 42', 'https://www.github.com/', 'Grüße aus München ✓',
    'ABC1234567890123abcdefXYZ', 'x' * 300, '1',
])
@pytest.mark.parametrize('level', ['L', 'H'])
def test_roundtrip_with_reference_encoder(text, level):
    data, version = data_codewords(text, level)
    decoded = decode_data(data, version)
    assert decoded.text == text
    assert decoded.padding_ok


def test_kanji():
    # "点" = Shift-JIS 0x935F → 0x935F - 0x8140 = 0x121F → 0x12 * 0xC0 + 0x1F = 0xD9F
    data = Bits().add(0b1000, 4).add(1, 8).add(0xD9F, 13).add(0, 4).to_bytes(19)
    assert decode_data(data, 1).text == '点'


def test_eci_utf8():
    raw = 'Ä€'.encode('utf-8')
    bits = Bits().add(0b0111, 4).add(26, 8).add(0b0100, 4).add(len(raw), 8)
    for b in raw:
        bits.add(b, 8)
    decoded = decode_data(bits.add(0, 4).to_bytes(19), 1)
    assert decoded.text == 'Ä€'
    assert 'eci:26' in decoded.modes


def test_wrong_padding_is_flagged():
    data = bytearray(data_codewords('HELLO', 'L')[0])
    data[-1] ^= 0xFF
    assert not decode_data(bytes(data), 1).padding_ok


def test_invalid_mode_raises():
    with pytest.raises(DataDecodeError):
        decode_data(bytes([0b11110000]) + bytes(18), 1)


def test_truncated_segment_raises():
    with pytest.raises(DataDecodeError):
        decode_data(Bits().add(0b0100, 4).add(200, 8).to_bytes(19), 1)
