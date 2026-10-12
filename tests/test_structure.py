import random

import pytest

from tools.qr_reconstruction.core import codewords as cw
from tools.qr_reconstruction.core.data_decoder import decode_data
from tools.qr_reconstruction.core.reconstructor import Reconstructor
from tools.qr_reconstruction.core.spec import (
    MODE_ALPHANUMERIC, MODE_BYTE, MODE_NUMERIC, block_layout,
)
from tools.qr_reconstruction.core.structure import Hypothesis, constraints, hypotheses, prefix_constraints
from tests.helpers import damage, make_known_matrix

import qrcode
import qrcode.util

URL = 'https://www.github.com/'


def data_bytes(text, version, level, mode=None):
    qr = qrcode.QRCode(version=version, error_correction={'L': 1, 'M': 0, 'Q': 3, 'H': 2}[level])
    qr.add_data(qrcode.util.QRData(text.encode(), mode=mode) if mode else text, optimize=0)
    qr.make(fit=False)
    seq = qrcode.util.create_data(version, qr.error_correction, qr.data_list)
    blocks = cw.deinterleave(seq, version, level)
    return bytes(b for block, (dl, _) in zip(blocks, block_layout(version, level)) for b in block[:dl])


def data_cells(matrix):
    return [(r, c) for r in range(matrix.size) for c in range(matrix.size) if not matrix._is_fixed_pattern(r, c)]


@pytest.mark.parametrize('text,mode,qr_mode', [
    (URL, MODE_BYTE, qrcode.util.MODE_8BIT_BYTE),
    ('HELLO WORLD', MODE_ALPHANUMERIC, qrcode.util.MODE_ALPHA_NUM),
    ('0123456789', MODE_NUMERIC, qrcode.util.MODE_NUMBER),
])
@pytest.mark.parametrize('version,level', [(2, 'M'), (5, 'L'), (10, 'H')])
def test_constraints_match_real_codes(text, mode, qr_mode, version, level):
    """Die festgelegten Bits einer richtigen Hypothese stimmen mit echten Codes überein"""
    real = data_bytes(text, version, level, qr_mode)
    values, masks = constraints(Hypothesis(mode, len(text)), version, level)
    assert len(values) == len(real)
    assert all((v ^ r) & m == 0 for v, r, m in zip(values, real, masks))
    assert sum(bin(m).count('1') for m in masks) > 0


def test_prefix_is_fixed():
    real = data_bytes(URL, 2, 'M', qrcode.util.MODE_8BIT_BYTE)
    for fixed in (constraints(Hypothesis(MODE_BYTE, len(URL), b'https://'), 2, 'M'),
                  prefix_constraints(b'https://', 2, 'M')):
        values, masks = fixed
        assert all((v ^ r) & m == 0 for v, r, m in zip(values, real, masks))
        assert masks[2] == 0xFF  # ab Bit 12 steht der Textanfang, Byte 2 ist komplett festgelegt


def test_too_long_hypothesis_rejected():
    assert constraints(Hypothesis(MODE_BYTE, 200), 1, 'H') is None


def test_hypotheses_respect_prefix_and_capacity():
    hs = list(hypotheses(2, 'M', b'https://'))
    assert {h.mode for h in hs} == {MODE_BYTE}
    assert min(h.length for h in hs) == len('https://')
    assert all(constraints(h, 2, 'M') is not None for h in hs)
    assert {h.mode for h in hypotheses(2, 'M')} == {MODE_BYTE, MODE_ALPHANUMERIC, MODE_NUMERIC}


def test_known_prefix_resolves_heavy_damage():
    """50 % Schaden in v2-M: ohne Hinweis 2^48 Möglichkeiten, mit 'https://' eindeutig"""
    original = make_known_matrix(URL, version=2, ec='M')
    damaged = damage(original, random.Random(1).sample(data_cells(original), len(data_cells(original)) // 2))
    without = Reconstructor(damaged).run(max_time=30, max_candidates=1024)
    assert without[0].decoded_data != URL or without[0].ambiguous_bits > 0
    results = Reconstructor(damaged, known_prefix='https://').run(max_time=30)
    assert [r.decoded_data for r in results] == [URL]
    assert results[0].assumption and results[0].confidence >= 90


def test_padding_resolves_damage_without_hint():
    """Kurzer Inhalt in großem Code: die Füllbytes allein machen die Lösung eindeutig"""
    original = make_known_matrix(URL, version=4, ec='L')
    damaged = damage(original, random.Random(3).sample(data_cells(original), int(len(data_cells(original)) * 0.45)))
    results = Reconstructor(damaged).run(max_time=30)
    assert results[0].decoded_data == URL
    assert 'Füllung' in results[0].assumption


def test_unique_cases_need_no_assumption():
    original = make_known_matrix(URL, version=2, ec='M')
    damaged = damage(original, random.Random(0).sample(data_cells(original), 60))
    result = Reconstructor(damaged, known_prefix='https://').run(max_time=30)[0]
    assert result.decoded_data == URL and result.assumption == ''


def test_wrong_prefix_does_not_produce_wrong_unique_result():
    original = make_known_matrix(URL, version=2, ec='M')
    damaged = damage(original, random.Random(1).sample(data_cells(original), len(data_cells(original)) // 2))
    results = Reconstructor(damaged, known_prefix='ftp://').run(max_time=30, max_candidates=512)
    assert not (results and results[0].assumption and results[0].decoded_data.startswith('ftp://')
                and results[0].ambiguous_bits == 0 and len(results) == 1) or results[0].decoded_data == URL


def test_decoded_hypothesis_roundtrip():
    """Daten, die exakt die Constraints einer Hypothese erfüllen, dekodieren mit korrektem Padding"""
    real = data_bytes(URL, 3, 'Q', qrcode.util.MODE_8BIT_BYTE)
    decoded = decode_data(real, 3)
    assert decoded.text == URL and decoded.padding_ok
