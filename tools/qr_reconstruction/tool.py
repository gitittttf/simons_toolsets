from core.base_tool import BaseTool
from .ui.main_window import MainWindow
import sys
import os

class QRReconstructionTool(BaseTool):
    @property
    def name(self) -> str:
        return "QR-Code Reconst."

    @property
    def description(self) -> str:
        return "Rekonstruiert unvollständige QR-Codes durch Bruteforcing"

    @property
    def version(self) -> str:
        return "0.1.0"

    def run(self):
        """Startet die das Tool als Standalone"""
        from .ui.main_window import MainWindow
        app = MainWindow(is_standalone=True)
        app.mainloop()

    def launch_gui(self, parent):
        """Startet die GUI vom Hub aus"""
        from .ui.main_window import MainWindowToplevel
        # Wir nutzten jetzt ein echtes Toplevel-Fenster, das am Hub-Root hängt
        self.window = MainWindowToplevel()
        return self.window

    def cleanup(self):
        """Stoppt Hintergrund-Prozesse"""
        if hasattr(self, 'window') and self.window:
            if hasattr(self.window, 'bruteforce_engine') and self.window.bruteforce_engine:
                self.window.bruteforce_engine.stop()
            try:
                self.window.destroy()
            except Exception as e:
                # Ignore errors if window is already destroyed
                print(f"Cleanup note: {e}")
                pass
