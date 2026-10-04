import logging

from core.base_tool import BaseTool

logger = logging.getLogger(__name__)


class QRReconstructionTool(BaseTool):
    @property
    def name(self) -> str:
        return "QR-Code Reconst."

    @property
    def description(self) -> str:
        return "Rekonstruiert beschädigte QR-Codes per Reed-Solomon-Fehlerkorrektur"

    @property
    def version(self) -> str:
        return "0.2.0"

    def run(self):
        """Startet das Tool als Standalone"""
        from .ui.main_window import MainWindow
        app = MainWindow(is_standalone=True)
        app.mainloop()

    def launch_gui(self, parent):
        """Startet die GUI vom Hub aus (eigenes Toplevel-Fenster am Hub-Root)"""
        from .ui.main_window import MainWindowToplevel
        self.window = MainWindowToplevel()
        return self.window

    def cleanup(self):
        """Stoppt laufende Rekonstruktionen und schließt das Fenster"""
        if getattr(self, 'window', None):
            if getattr(self.window, 'active_job', None):
                self.window.active_job.stop()
            try:
                self.window.destroy()
            except Exception as e:  # Fenster kann bereits zerstört sein
                logger.debug("Cleanup: %s", e)
