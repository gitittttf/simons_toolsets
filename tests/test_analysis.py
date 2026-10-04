import random

import numpy as np
import pytest

from tools.qr_reconstruction.core.analysis import (
    BLOCK_AMBIGUOUS, BLOCK_OK, VERDICT_AMBIGUOUS, VERDICT_COMPLETE, VERDICT_CORRECTABLE,
    VERDICT_INCONSISTENT, VERDICT_UNIQUE, analyze_solvability,
)
from tools.qr_reconstruction.core.codewords import data_module_order
from tools.qr_reconstruction.core.qr_matrix import QRMatrix
from tools.qr_reconstruction.core.reconstructor import Reconstructor
from tools.qr_reconstruction.core.spec import format_info_positions
from tools.qr_reconstruction.core.validator import QRValidator
from tests.helpers import damage, make_known_matrix

URL = 'https://www.github.com/'


def data_cells(matrix):
    return [(r, c) for r in range(matrix.size) for c in range(matrix.size)
            if not matrix._is_fixed_pattern(r, c)]


@pytest.fixture
def original():
    return make_known_matrix(URL, ec='M', mask=5)


def test_complete(original):
    report = analyze_solvability(original)
    assert report.verdict == VERDICT_COMPLETE
    assert report.unknown_cells == 0
    assert (report.format.ec_level, report.format.mask) == ('M', 5)


def test_unique(original):
    damaged = damage(original, random.Random(0).sample(data_cells(original), 70))
    report = analyze_solvability(damaged)
    assert report.verdict == VERDICT_UNIQUE
    assert all(b.status == BLOCK_OK for b in report.blocks)
    assert report.unknown_cells == 70


def test_ambiguous(original):
    damaged = damage(original, random.Random(0).sample(data_cells(original), len(data_cells(original)) // 2))
    report = analyze_solvability(damaged)
    assert report.verdict == VERDICT_AMBIGUOUS
    assert report.free_bits > 0
    assert any(b.status == BLOCK_AMBIGUOUS for b in report.blocks)


def test_wrongly_painted_pixel_is_correctable(original):
    painted = original.clone()
    painted.grid[12, 12] ^= 1
    assert analyze_solvability(painted).verdict == VERDICT_CORRECTABLE


def test_inconsistent(original):
    painted = original.clone()
    for r, c in random.Random(1).sample(data_cells(original), 120):
        painted.grid[r, c] ^= 1
    report = analyze_solvability(painted)
    assert report.verdict == VERDICT_INCONSISTENT
    assert report.viable_formats == 0


def test_unknown_format_prefers_stronger_ec_level(original):
    """RS-Codes gleicher Länge sind verschachtelt: ein gültiger M-Block ist auch ein gültiger L-Block"""
    cells = [p for copy in format_info_positions(original.size) for p in copy]
    damaged = damage(original, cells + random.Random(1).sample(data_cells(original), 30))
    report = analyze_solvability(damaged)
    assert report.verdict == VERDICT_UNIQUE
    assert (report.format.ec_level, report.format.mask) == ('M', 5)
    assert report.format.known_bits == 0


def test_verdict_matches_reconstructor():
    """Was die Analyse eindeutig lösbar nennt, löst der Reconstructor auch eindeutig"""
    validator = QRValidator()
    rng = random.Random(3)
    for level in 'LMQH':
        original = make_known_matrix(URL, version=3, ec=level)
        for fraction in (0.1, 0.25, 0.4):
            cells = data_cells(original)
            damaged = damage(original, rng.sample(cells, int(len(cells) * fraction)))
            report = analyze_solvability(damaged)
            results = Reconstructor(damaged, validator).run(max_time=30, max_candidates=256)
            if report.verdict == VERDICT_UNIQUE:
                assert results[0].decoded_data == URL and results[0].ambiguous_bits == 0
            elif report.verdict == VERDICT_AMBIGUOUS:
                assert results and results[0].ambiguous_bits == report.free_bits


def test_overlay_maps(original):
    rows, cols = data_module_order(original.version)
    cell = (int(rows[20]), int(cols[20]))                  # Bit 4 von Codewort 2
    report = analyze_solvability(damage(original, [cell]))
    assert report.module_block.shape == (original.size, original.size)
    assert report.module_block[cell] == 0                  # Version 2-M: ein Block
    assert report.module_block[0, 0] == -1                 # Finder-Pattern: kein Datenmodul
    affected = np.argwhere(report.module_affected).tolist()
    assert len(affected) == 8                              # genau das eine Codewort mit dem Pixel
    assert sorted(affected) == sorted([int(rows[i]), int(cols[i])] for i in range(16, 24))
    assert len(report.format_cells) == 30


def test_empty_matrix_is_ambiguous_and_fast():
    report = analyze_solvability(QRMatrix(25))
    assert report.verdict == VERDICT_AMBIGUOUS
    assert report.format.known_bits == 0
