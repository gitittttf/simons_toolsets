import random

import pytest
import qrcode.util
from reedsolo import RSCodec

from tools.qr_reconstruction.core import codewords as cw
from tools.qr_reconstruction.core import rs_decoder as rs

NSYM = 10  # Version 2-L: ein Block mit 34 Daten- + 10 EC-Codewörtern


@pytest.fixture
def block():
    sequence = qrcode.util.create_data(2, qrcode.constants.ERROR_CORRECT_L,
                                       [qrcode.util.QRData(b'https://www.github.com/abc')])
    return cw.deinterleave(sequence, 2, 'L')[0]


def scramble(block, masks, rng):
    """Unbekannte Bits zufällig setzen, bekannte Bits behalten"""
    return [(b & m) | (rng.randrange(256) & ~m & 0xFF) for b, m in zip(block, masks)]


def test_gf_arithmetic_matches_reedsolo():
    rng = random.Random(0)
    data = bytes(rng.randrange(256) for _ in range(20))
    encoded = list(RSCodec(NSYM).encode(data))
    assert rs.syndromes(encoded, NSYM) == [0] * NSYM


def test_valid_block_has_zero_syndromes(block):
    assert rs.syndromes(block, NSYM) == [0] * NSYM


@pytest.mark.parametrize('erasures', [1, 5, NSYM])
def test_erasures_up_to_nsym_are_unique(block, erasures):
    rng = random.Random(erasures)
    masks = [0xFF] * len(block)
    for p in rng.sample(range(len(block)), erasures):
        masks[p] = 0
    solution = rs.solve_block(scramble(block, masks, rng), masks, NSYM)
    assert solution.free_bits == 0
    assert solution.codeword() == block
    assert solution.unknown_codewords == erasures


def test_one_codeword_beyond_capacity_leaves_eight_free_bits(block):
    rng = random.Random(1)
    masks = [0xFF] * len(block)
    for p in rng.sample(range(len(block)), NSYM + 1):
        masks[p] = 0
    solution = rs.solve_block(scramble(block, masks, rng), masks, NSYM)
    assert solution.free_bits == 8
    assert block in [solution.codeword(s) for s in range(256)]


def test_partial_codewords_beyond_erasure_capacity(block):
    """16 Codewörter mit je 4 unbekannten Bits: als Erasures unlösbar (16 > 10), bitweise eindeutig"""
    rng = random.Random(2)
    masks = [0xFF] * len(block)
    for p in rng.sample(range(len(block)), 16):
        masks[p] = 0b10100101
    solution = rs.solve_block(scramble(block, masks, rng), masks, NSYM)
    assert solution.free_bits == 0
    assert solution.codeword() == block


def test_wrong_known_codewords_are_corrected(block):
    rng = random.Random(3)
    masks = [0xFF] * len(block)
    values = list(block)
    for p in rng.sample(range(len(block)), 4):
        masks[p] = 0
        values[p] = 0
    for p in rng.sample([i for i in range(len(block)) if masks[i] == 0xFF], 3):  # 2*3 + 4 = 10
        values[p] ^= 0x5A
    solution = rs.solve_block(values, masks, NSYM)
    assert solution.codeword() == block
    assert solution.corrected_errors == 3
    assert rs.solve_block(values, masks, NSYM, allow_errors=False) is None


def test_uncorrectable_block_returns_none(block):
    assert rs.solve_block([b ^ 0xFF for b in block], [0xFF] * len(block), NSYM) is None
