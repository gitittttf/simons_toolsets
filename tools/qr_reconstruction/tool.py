from core.base_tool import BaseTool
from .ui.main_window import MainWindow
import sys
import os

class QRReconstructionTool(BaseTool):
    @property
    def name(self) -> str:
        return "QR-Code Reconstructor"

    @property
    def description(self) -> str:
        return "Rekonstruiert beschädigte QR-Codes durch intelligentes Bruteforcing."

    @property
    def version(self) -> str:
        return "1.0.0"

    def run(self):
        # Temporär den Pfad anpassen, damit interne Imports funktionieren
        # (Dies ist ein Workaround, besser wäre es alle Imports relativ zu machen)
        # Aber da wir im selben Prozess sind, importieren wir einfach MainWindow
        # Die relativen Imports in MainWindow sollten funktionieren, da sie teil des Packages sind.
        
        app = MainWindow()
        app.mainloop()
