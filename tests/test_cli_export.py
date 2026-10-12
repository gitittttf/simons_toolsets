import json

import numpy as np
import pytest
import pyzbar.pyzbar as pyzbar
from PIL import Image

from tools.qr_reconstruction.core.export import matrix_to_image, matrix_to_svg, save_matrix
from tests.helpers import make_qr_grid

URL = 'https://www.github.com/'


def test_exported_png_is_scannable(tmp_path):
    grid = make_qr_grid(URL)
    path = tmp_path / "code.png"
    save_matrix(grid, str(path))
    assert pyzbar.decode(Image.open(path))[0].data.decode() == URL


def test_png_has_quiet_zone():
    image = np.array(matrix_to_image(make_qr_grid(URL), scale=10))
    assert (image[:40] == 255).all() and (image[:, :40] == 255).all()
    assert image.shape == ((25 + 8) * 10,) * 2


def test_svg_contains_one_square_per_black_module(tmp_path):
    grid = make_qr_grid(URL)
    svg = matrix_to_svg(grid)
    assert svg.startswith('<svg') and svg.count('h1v1h-1z') == int(grid.sum())
    path = tmp_path / "code.svg"
    save_matrix(grid, str(path))
    assert path.read_text(encoding='utf-8') == svg


cv2 = pytest.importorskip("cv2")
from tools.qr_reconstruction.__main__ import run_cli  # noqa: E402
from tests.image_helpers import blob, code_image  # noqa: E402


def write(path, image):
    cv2.imwrite(str(path), image)
    return str(path)


def test_cli_reconstructs_and_saves(tmp_path, capsys):
    image, _ = code_image(URL)
    source = write(tmp_path / "kaputt.png", blob(image, 260, 280, 60, color=(20, 20, 200)))
    target = tmp_path / "repariert.png"
    assert run_cli([source, '--save', str(target), '--json']) == 0
    entry = json.loads(capsys.readouterr().out)[0]
    assert entry['results'][0]['text'] == URL
    assert pyzbar.decode(Image.open(target))[0].data.decode() == URL


def test_cli_manual_corners_and_errors(tmp_path, capsys):
    image, _ = code_image(URL)
    damaged = write(tmp_path / "finder.png", blob(image, 95, 95, 45))
    # ohne Ecken: kein Code gefunden → Exit-Code 2
    assert run_cli([damaged]) == 2
    assert run_cli([damaged, '--corners', '52,45,343,52,352,345,44,350']) == 0
    assert URL in capsys.readouterr().out
    assert run_cli([str(tmp_path / "fehlt.png")]) == 2
    with pytest.raises(SystemExit):
        run_cli([damaged, '--corners', '1,2,3'])


def test_cli_batch_with_name_placeholder(tmp_path):
    image, _ = code_image(URL)
    sources = [write(tmp_path / f"code{i}.png", image) for i in range(2)]
    assert run_cli(sources + ['--save', str(tmp_path / "fix_{name}.svg")]) == 0
    assert (tmp_path / "fix_code0.svg").exists() and (tmp_path / "fix_code1.svg").exists()
