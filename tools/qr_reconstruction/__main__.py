"""
Einstiegspunkt: Oberfläche oder Kommandozeile

    python -m tools.qr_reconstruction                      # Oberfläche
    python -m tools.qr_reconstruction bild.png [...]       # ohne Oberfläche rekonstruieren

Beispiele:
    python -m tools.qr_reconstruction foto.jpg
    python -m tools.qr_reconstruction foto.jpg --prefix https:// --save repariert.png
    python -m tools.qr_reconstruction *.png --json
    python -m tools.qr_reconstruction kaputt.png --corners 52,45,343,52,352,345,44,350

Exit-Code: 0 = alle Bilder rekonstruiert, 1 = mindestens eins ohne Lösung, 2 = Fehler
"""

import argparse
import json
import logging
import sys
from typing import List, Optional


def _parse_corners(text: str):
    import numpy as np
    values = [float(v) for v in text.replace(';', ',').split(',')]
    if len(values) != 8:
        raise argparse.ArgumentTypeError("--corners erwartet 8 Zahlen: x1,y1,x2,y2,x3,y3,x4,y4")
    return np.array(values, dtype=np.float32).reshape(4, 2)


def _reconstruct_image(path: str, args) -> dict:
    from .core import image_import
    from .core.export import save_matrix
    from .core.reconstructor import Reconstructor

    image = image_import.load_image(path)
    corners = args.corners if args.corners is not None else image_import.detect_corners(image)
    if corners is None:
        return {'file': path, 'error': "Kein QR-Code gefunden - Ecken mit --corners angeben"}
    imported = image_import.sample_grid(image, corners)
    results = Reconstructor(imported.to_matrix(), known_prefix=args.prefix).run(max_time=args.time)
    entry = {
        'file': path,
        'version': imported.to_matrix().version,
        'pattern_score': round(imported.pattern_score, 3),
        'unknown_modules': int(imported.unsure.sum()),
        'results': [{
            'text': r.decoded_data,
            'confidence': round(r.confidence, 1),
            'error_correction_level': r.error_correction_level,
            'mask': r.mask_pattern,
            'reconstructed_codewords': r.unknown_codewords,
            'corrected_errors': r.corrected_errors,
            'ambiguous_bits': r.ambiguous_bits,
            'assumption': r.assumption,
        } for r in results[:args.top]],
    }
    if results and args.save:
        target = args.save if len(args.images) == 1 else args.save.replace('{name}', _stem(path))
        save_matrix(results[0].matrix, target)
        entry['saved'] = target
    return entry


def _stem(path: str) -> str:
    from pathlib import Path
    return Path(path).stem


def _print_entry(entry: dict):
    print(f"\n{entry['file']}")
    if 'error' in entry:
        print(f"  ✗ {entry['error']}")
        return
    print(f"  Version {entry['version']}, feste Muster {entry['pattern_score']:.0%}, "
          f"{entry['unknown_modules']} Module unbekannt")
    if not entry['results']:
        print("  ✗ Keine Lösung gefunden")
    for i, r in enumerate(entry['results'], start=1):
        details = f"EC {r['error_correction_level']}, Maske {r['mask']}, {r['reconstructed_codewords']} Codewörter rekonstruiert"
        if r['corrected_errors']:
            details += f", {r['corrected_errors']} korrigiert"
        if r['ambiguous_bits']:
            details += f", mehrdeutig (2^{r['ambiguous_bits']})"
        print(f"  {i}. [{r['confidence']:5.1f}%] {r['text']!r}")
        print(f"     {details}" + (f"\n     Annahme: {r['assumption']}" if r['assumption'] else ""))
    if 'saved' in entry:
        print(f"  → gespeichert: {entry['saved']}")


def run_cli(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tools.qr_reconstruction",
        description="Rekonstruiert beschädigte QR-Codes aus Bildern (ohne Oberfläche).")
    parser.add_argument('images', nargs='+', help="Bilddateien (PNG, JPG, ...)")
    parser.add_argument('--prefix', default='', help="bekannter Textanfang, z.B. https://")
    parser.add_argument('--corners', type=_parse_corners,
                        help="Ecken des Codes x1,y1,...,x4,y4 (wenn die automatische Erkennung scheitert)")
    parser.add_argument('--save', help="rekonstruierten Code speichern (.png/.svg); bei mehreren Bildern "
                                       "{name} als Platzhalter verwenden")
    parser.add_argument('--top', type=int, default=3, help="so viele Lösungen anzeigen (Standard 3)")
    parser.add_argument('--time', type=float, default=60, help="Zeitlimit je Bild in Sekunden")
    parser.add_argument('--json', action='store_true', help="Ergebnis als JSON ausgeben")
    parser.add_argument('-v', '--verbose', action='store_true', help="Fortschritt protokollieren")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO if args.verbose else logging.ERROR,
                        format="%(levelname)s %(name)s: %(message)s")
    from .core.image_import import ImageImportError

    entries, exit_code = [], 0
    for path in args.images:
        try:
            entry = _reconstruct_image(path, args)
        except ImageImportError as e:
            entry = {'file': path, 'error': str(e)}
        if 'error' in entry:
            exit_code = 2
        elif not entry['results']:
            exit_code = max(exit_code, 1)
        entries.append(entry)
        if not args.json:
            _print_entry(entry)
    if args.json:
        print(json.dumps(entries, ensure_ascii=False, indent=2))
    return exit_code


def main(argv: Optional[List[str]] = None):
    """Ohne Argumente: Oberfläche. Mit Bildpfaden: Kommandozeile."""
    argv = sys.argv[1:] if argv is None else argv
    if argv:
        sys.exit(run_cli(argv))

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger(__name__).info("QR-Code Rekonstruktion startet")
    from .ui.main_window import MainWindow
    app = MainWindow()
    app.mainloop()


if __name__ == "__main__":
    main()
