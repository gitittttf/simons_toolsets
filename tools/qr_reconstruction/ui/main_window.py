"""
Main Window - Mit offiziellen QR-Code Größen

Features:
- Nur offizielle QR-Versionen (1-40, Größen 21-177)
- Dropdown für Versionsauswahl
- Korrekte Pattern-Generierung
"""

import customtkinter as ctk
from tkinter import filedialog, messagebox
import logging
import queue
import threading
import sys
from typing import Optional
from .grid_editor import GridEditor
from .corner_dialog import CornerDialog
from .results_view import ResultsView
from ..core.qr_matrix import QRMatrix, QR_VERSIONS
from ..core.bruteforce import BruteforceEngine
from ..core.reconstructor import Reconstructor
from ..core import image_import
from ..core.codewords import read_codewords
from ..core.spec import format_info_positions, version_info_positions
from ..core.analysis import (
    VERDICT_AMBIGUOUS, VERDICT_COMPLETE, VERDICT_CORRECTABLE, VERDICT_INCONSISTENT, VERDICT_UNIQUE,
    BLOCK_AMBIGUOUS, BLOCK_CORRECTED, BLOCK_OK, BLOCK_UNSOLVABLE, analyze_solvability,
)
from ..core.validator import QRValidator


from .theme import Colors, Fonts, Dimensions
logger = logging.getLogger(__name__)

# Anzeige des Analyse-Ergebnisses: Text und Farbe je Urteil
VERDICT_DISPLAY = {
    VERDICT_COMPLETE: ("✓ Vollständig", Colors.SUCCESS),
    VERDICT_UNIQUE: ("✓ Eindeutig lösbar", Colors.SUCCESS),
    VERDICT_CORRECTABLE: ("⚠ Lösbar mit Korrektur", Colors.WARNING),
    VERDICT_AMBIGUOUS: ("⚠ Mehrdeutig", Colors.WARNING),
    VERDICT_INCONSISTENT: ("✗ Nicht lösbar", Colors.ERROR),
}
BLOCK_STATUS_NAMES = {
    BLOCK_OK: "ok", BLOCK_CORRECTED: "korrigiert", BLOCK_AMBIGUOUS: "mehrdeutig", BLOCK_UNSOLVABLE: "widersprüchlich",
}
# Wartezeit nach der letzten Änderung, bevor die Lösbarkeit neu analysiert wird
ANALYSIS_DEBOUNCE_MS = 250


def setup_theme():
    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("blue")

# =============================================================================
# HAUPTFENSTER
# =============================================================================
class MainWindowMixin:
    """Gemeinsame Implementierung für Standalone (CTk) und Hub-Tool (CTkToplevel)"""

    def _init_shared(self, is_standalone=True):
        self.is_standalone = is_standalone
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        setup_theme()
        for sequence, action in (("<Control-z>", "undo"), ("<Control-y>", "redo"), ("<Control-Z>", "redo")):
            self.bind(sequence, lambda event, a=action: self._editor_history(a))

        self.title("✨ QR-Code Rekonstruktion ✨")
        self.geometry("1550x980")
        self.minsize(1200, 800)
        self.configure(fg_color=Colors.BG_PRIMARY)

        # State
        self.matrix: Optional[QRMatrix] = None
        self.validator = QRValidator()
        # Laufender Job: Reconstructor oder (als Fallback) BruteforceEngine
        self.active_job = None
        self.bruteforce_thread: Optional[threading.Thread] = None
        self.is_running = False

        # UI Components
        self.grid_editor: Optional[GridEditor] = None
        self.editor_controls = None
        self.results_view: Optional[ResultsView] = None
        
        # Foto aus dem Bild-Import (entzerrt, Graubild) als Editor-Hintergrund
        self.photo = None
        self.photo_on = True
        
        # Lösbarkeitsanalyse (läuft entprellt im Hintergrund)
        self.overlay_on = False
        self._analysis_after = None
        self._analysis_generation = 0
        self._analysis_queue: queue.Queue = queue.Queue()
        self._analysis_polling = False
        self._last_report = None
        self._inspect_cache = (None, None)

        self._build_start_screen()

    def _on_close(self):
        """Clean exit handler"""
        if self.is_running and self.active_job:
            self.active_job.stop()
        
        # If standalone, we destroy ourselves (and exit app)
        if self.is_standalone:
            self.destroy()
            sys.exit(0)
        else:
            # If Hub-managed, the Hub has hooked WM_DELETE_WINDOW too (in launcher.py).
            # However, since we overwrote the protocol here, we need to trigger the hide behavior.
            # Actually, launcher.py overwrites it AFTER launch_gui returns. 
            # So this method might be overwritten by launcher. But to be safe:
            self.withdraw() # Default to hide

    def _build_start_screen(self):
        """Start-Screen mit Versionsauswahl"""
        for widget in self.winfo_children():
            widget.destroy()
        
        container = ctk.CTkFrame(self, fg_color=Colors.BG_PRIMARY, corner_radius=Dimensions.CORNER_RADIUS_NONE)
        container.pack(fill="both", expand=True)
        
        # Zentrierte Karte mit Glass-Effekt
        center = ctk.CTkFrame(container, fg_color=Colors.BG_SECONDARY, border_width=Dimensions.BORDER_WIDTH_THIN, border_color=Colors.BORDER, corner_radius=Dimensions.CORNER_RADIUS_L)
        center.place(relx=0.5, rely=0.45, anchor="center")
        
        # Title mit Icon
        ctk.CTkLabel(center, text="✨ QR-Code Rekonstruktion", font=Fonts.TITLE, text_color=Colors.TEXT_PRIMARY).pack(pady=(30, 5), padx=50)
        ctk.CTkLabel(center, text="Beschädigte QR-Codes intelligent wiederherstellen", font=Fonts.BODY, text_color=Colors.TEXT_SECONDARY).pack(pady=(0, 30))
        
        # Divider
        ctk.CTkFrame(center, height=1, fg_color=Colors.BORDER).pack(fill="x", padx=40, pady=10)
        
        # Version Selection
        version_section = ctk.CTkFrame(center, fg_color="transparent")
        version_section.pack(pady=20)
        
        ctk.CTkLabel(version_section, text="📦 Wähle eine QR-Code Version:", font=Fonts.SUBHEADING, text_color=Colors.TEXT_PRIMARY).pack(pady=(0, 20))
        
        # Quick Select Grid
        quick_frame = ctk.CTkFrame(version_section, fg_color="transparent")
        quick_frame.pack(pady=10)
        
        common_versions = [
            (1, "V1", "21x21"),
            (2, "V2", "25x25"),
            (3, "V3", "29x29"),
            (4, "V4", "33x33"),
            (5, "V5", "37x37"),
            (6, "V6", "41x41"),
        ]
        
        for i, (version, label, size_str) in enumerate(common_versions):
            size = QR_VERSIONS[version][0]
            btn = ctk.CTkButton(
                quick_frame,
                text=f"{label}\n{size_str}",
                command=lambda s=size: self._create_matrix(s),
                width=100,
                height=60,
                font=Fonts.BUTTON,
                fg_color=Colors.BG_CARD,
                text_color=Colors.ACCENT,
                hover_color=Colors.BG_CARD_HOVER,
                corner_radius=Dimensions.CORNER_RADIUS_M,
                border_width=Dimensions.BORDER_WIDTH_DEFAULT,
                border_color=Colors.BORDER
            )
            btn.grid(row=0, column=i, padx=8, pady=8)
        
        # OR Divider
        ctk.CTkLabel(version_section, text="- oder -", font=Fonts.SMALL, text_color=Colors.TEXT_MUTED).pack(pady=10)
        
        # Version Dropdown
        input_row = ctk.CTkFrame(version_section, fg_color="transparent")
        input_row.pack(pady=10)
        
        ctk.CTkLabel(input_row, text="Manuelle Auswahl:", font=Fonts.BODY, text_color=Colors.TEXT_PRIMARY).pack(side="left", padx=(0, 10))
        
        version_options = []
        for v in range(1, 41):
            size = QR_VERSIONS[v][0]
            version_options.append(f"Version {v} ({size}x{size})")
        
        self.version_var = ctk.StringVar(value=version_options[0])
        self.version_dropdown = ctk.CTkComboBox(
            input_row,
            values=version_options,
            variable=self.version_var,
            width=200,
            height=36,
            font=Fonts.BODY,
            fg_color="#ffffff",
            border_color=Colors.ACCENT,
            button_color=Colors.ACCENT,
            dropdown_fg_color="#ffffff",
            dropdown_text_color="#000000",
            corner_radius=Dimensions.CORNER_RADIUS_M,
            border_width=Dimensions.BORDER_WIDTH_DEFAULT
        )
        self.version_dropdown.pack(side="left", padx=10)
        
        ctk.CTkButton(
            input_row,
            text="🚀 Starten",
            command=self._start_from_dropdown,
            width=120,
            height=36,
            font=Fonts.BUTTON,
            fg_color=Colors.ACCENT,
            text_color="#ffffff",
            hover_color=Colors.ACCENT_HOVER,
            corner_radius=Dimensions.CORNER_RADIUS_M
        ).pack(side="left", padx=(10, 0))

        # Preset Button
        ctk.CTkButton(
            input_row,
            text="GitHub Preset",
            command=self._load_github_preset,
            width=120,
            height=36,
            font=Fonts.BUTTON,
            fg_color=Colors.BG_CARD,
            text_color=Colors.TEXT_PRIMARY,
            hover_color=Colors.BG_CARD_HOVER,
            corner_radius=Dimensions.CORNER_RADIUS_M,
            border_width=Dimensions.BORDER_WIDTH_DEFAULT,
            border_color=Colors.ACCENT
        ).pack(side="left", padx=10)
        
        # Bild-Import
        ctk.CTkLabel(version_section, text="- oder -", font=Fonts.SMALL, text_color=Colors.TEXT_MUTED).pack(pady=10)
        ctk.CTkButton(
            version_section,
            text="📷 Bild importieren (Foto / Screenshot)",
            command=self._import_image,
            width=320,
            height=44,
            font=Fonts.BUTTON_LARGE,
            fg_color=Colors.ACCENT,
            text_color="#ffffff",
            hover_color=Colors.ACCENT_HOVER,
            corner_radius=Dimensions.CORNER_RADIUS_M
        ).pack(pady=(0, 10))
        
        # Info
        ctk.CTkLabel(
            center,
            text="Unterstützt Version 1 (21x21) bis Version 40 (177x177)",
            font=Fonts.SMALL,
            text_color=Colors.TEXT_MUTED
        ).pack(pady=(10, 30))
    
    def _start_from_dropdown(self):
        """Startet mit ausgewählter Version"""
        selected = self.version_var.get()
        # Parse "Version 1 (21x21)" -> version 1
        version = int(selected.split("Version ")[1].split(" ")[0])
        size = QR_VERSIONS[version][0]
        self._create_matrix(size)
    
    def _load_github_preset(self):
        """Lädt das GitHub Preset und startet den Editor"""
        try:
            import qrcode
            
            # Generate GitHub QR
            qr = qrcode.QRCode(version=1, box_size=1, border=0)
            qr.add_data("https://www.github.com/")
            qr.make(fit=True)
            
            data = qr.get_matrix()
            size = len(data)
            
            # Create Matrix
            self._create_matrix(size)
            
            # Populate
            from ..core.qr_matrix import CellState
            for r in range(size):
                for c in range(size):
                    val = CellState.BLACK if data[r][c] else CellState.WHITE
                    self.matrix.grid[r, c] = val
                    self.matrix.locked[r, c] = True # Preset is effectively fully known
            
            # Refresh Editor if it exists (it's freshly built in _create_matrix -> _build_editor_view, but we need to redraw content)
            # The _build_editor_view was called in _create_matrix.
            # Now we just need to make sure grid_editor renders the new data.
            # Since we just modified self.matrix, and grid_editor uses it by reference, we just call render
            if self.grid_editor:
                self.grid_editor.render()
                if self.editor_controls:
                    self.editor_controls.update_stats()
                    
        except ImportError:
            messagebox.showerror("Fehler", "qrcode Library fehlt.", parent=self)

    def _create_matrix(self, size: int):
        """Erstellt Matrix"""
        self.matrix = QRMatrix(size=size)
        self.photo = None
        self._build_editor_view()

    # ------------------------------------------------------------------ Bild-Import
    def _import_image(self):
        path = filedialog.askopenfilename(
            parent=self, title="QR-Code-Bild öffnen",
            filetypes=[("Bilder", "*.png *.jpg *.jpeg *.bmp *.webp *.tif *.tiff"), ("Alle Dateien", "*.*")])
        if not path:
            return
        try:
            image = image_import.load_image(path)
            corners = image_import.detect_corners(image)
        except image_import.ImageImportError as e:
            messagebox.showerror("Bild-Import", str(e), parent=self)
            return
        CornerDialog(self, image, corners, on_accept=lambda c: self._run_import(image, c))

    def _run_import(self, image, corners):
        """Abtasten im Hintergrund (bei großen Versionen einige Sekunden), dann in den Editor"""
        busy = ctk.CTkToplevel(self)
        busy.title("Bild-Import")
        busy.configure(fg_color=Colors.BG_PRIMARY)
        busy.resizable(False, False)
        ctk.CTkLabel(busy, text="Bild wird analysiert …", font=Fonts.BODY,
                     text_color=Colors.TEXT_PRIMARY).pack(padx=40, pady=(20, 8))
        bar = ctk.CTkProgressBar(busy, mode="indeterminate", width=260, progress_color=Colors.ACCENT)
        bar.pack(padx=40, pady=(0, 20))
        bar.start()
        busy.transient(self)

        results: queue.Queue = queue.Queue()

        def work():
            try:
                results.put(image_import.sample_grid(image, corners))
            except Exception as e:  # dem Nutzer melden statt den Thread still sterben zu lassen
                logger.exception("Bild-Import fehlgeschlagen")
                results.put(e)

        threading.Thread(target=work, daemon=True).start()

        def poll():
            try:
                outcome = results.get_nowait()
            except queue.Empty:
                self.after(50, poll)
                return
            busy.destroy()
            if isinstance(outcome, Exception):
                messagebox.showerror("Bild-Import", f"Das Bild konnte nicht ausgewertet werden:\n{outcome}",
                                     parent=self)
                return
            self._apply_import(outcome)

        self.after(50, poll)

    def _apply_import(self, result):
        if result.pattern_score < 0.85 and not messagebox.askyesno(
                "Bild-Import",
                f"Die festen Muster (Finder, Timing) passen nur zu {result.pattern_score:.0%} - "
                "vermutlich sitzen die Ecken nicht richtig.\n\nTrotzdem übernehmen?", parent=self):
            return
        self.matrix = result.to_matrix()
        self.photo = result.warped
        self.photo_on = True
        self._build_editor_view()
        unsure = int(result.unsure.sum())
        messagebox.showinfo(
            "Bild-Import",
            f"Version {self.matrix.version} ({result.size}×{result.size}) erkannt, "
            f"feste Muster passen zu {result.pattern_score:.0%}.\n"
            f"{unsure} unsichere Module wurden als unbekannt markiert.\n\n"
            "Flecken, Knicke oder Reflexe erkennt das Tool nicht sicher: Markiere beschädigte "
            "Stellen per Rechtsklick als unbekannt. Das Foto liegt dafür hinter dem Raster "
            "(Schalter „Foto anzeigen“).", parent=self)
    
    def _build_editor_view(self):
        """Editor View mit neuem Sidebar-Layout"""
        for widget in self.winfo_children():
            widget.destroy()
        
        main = ctk.CTkFrame(self, fg_color="#333333", corner_radius=Dimensions.CORNER_RADIUS_NONE)
        main.pack(fill="both", expand=True)
        
        # 1. Canvas Area (Left/Center) - Takes available space
        canvas_container = ctk.CTkFrame(main, fg_color="#333333", corner_radius=Dimensions.CORNER_RADIUS_NONE)
        canvas_container.pack(fill="both", expand=True, side="left")
        
        # Statuszeile für den Codewort-Inspektor
        self.inspector_label = ctk.CTkLabel(
            canvas_container, text="  Maus über ein Modul bewegen, um Codewort und Block zu sehen",
            font=Fonts.SMALL, text_color="#cbd5e1", fg_color="#262626", anchor="w", height=26)
        self.inspector_label.pack(side="bottom", fill="x")
        
        self.grid_editor = GridEditor(canvas_container, self.matrix)
        self.grid_editor.pack(fill="both", expand=True)
        self.grid_editor.on_hover = self._on_inspect
        if self.photo is not None:
            self.grid_editor.set_photo(self.photo, show=self.photo_on)
        
        def on_change(r, c):
            self._update_stats_sidebar()
        self.grid_editor.on_cell_changed = on_change
        
        # 2. Sidebar (Right) - Fixed width
        # Scrollbar, damit bei kleinen Fenstern nichts abgeschnitten wird
        sidebar = ctk.CTkScrollableFrame(main, fg_color=Colors.BG_CARD, width=310, corner_radius=Dimensions.CORNER_RADIUS_NONE)
        sidebar.pack(fill="y", side="right")
        
        # Sidebar Content
        ctk.CTkLabel(sidebar, text="QR Rekonstruktion", font=Fonts.HEADING, text_color=Colors.TEXT_PRIMARY).pack(pady=(20, 5), padx=20, anchor="w")
        ctk.CTkLabel(sidebar, text=f"Version {self.matrix.version} ({self.matrix.size}×{self.matrix.size})", font=Fonts.BODY, text_color=Colors.TEXT_MUTED).pack(pady=(0, 20), padx=20, anchor="w")
        
        # Stats Panel
        self.stats_labels = {}
        self._build_stats_panel(sidebar)
        
        # Divider
        ctk.CTkFrame(sidebar, height=1, fg_color=Colors.BORDER).pack(fill="x", padx=20, pady=20)
        
        # Controls
        self._build_sidebar_controls(sidebar)
        
        # Divider
        ctk.CTkFrame(sidebar, height=1, fg_color=Colors.BORDER).pack(fill="x", padx=20, pady=20)
        
        # Action (Start)
        self._build_sidebar_action(sidebar)
        
        # Back Button at bottom
        ctk.CTkButton(
            sidebar, text="⬅ Zurück",
            command=self._build_start_screen,
            fg_color="transparent", text_color=Colors.TEXT_MUTED,
            hover_color=Colors.BG_CARD_HOVER,
            font=Fonts.SMALL
        ).pack(side="bottom", pady=20)
        
        # Mock the Controls object for compatibility if something else uses it
        self.editor_controls = type('obj', (object,), {'update_stats': self._update_stats_sidebar})
        self._update_stats_sidebar()

    def _build_stats_panel(self, parent):
        stats_frame = ctk.CTkFrame(parent, fg_color="transparent")
        stats_frame.pack(fill="x", padx=20)
        
        items = ["Unbekannte Pixel", "Format", "Lösbarkeit"]
        for item in items:
            row = ctk.CTkFrame(stats_frame, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=item, font=Fonts.SMALL, text_color=Colors.TEXT_MUTED).pack(side="left")
            lbl = ctk.CTkLabel(row, text="-", font=Fonts.BODY_BOLD, text_color=Colors.TEXT_PRIMARY)
            lbl.pack(side="right")
            self.stats_labels[item] = lbl
        
        self.analysis_message = ctk.CTkLabel(
            stats_frame, text="", font=Fonts.SMALL, text_color=Colors.TEXT_SECONDARY,
            wraplength=270, justify="left", anchor="w")
        self.analysis_message.pack(fill="x", pady=(6, 0))
        self.analysis_blocks = ctk.CTkLabel(
            stats_frame, text="", font=Fonts.SMALL, text_color=Colors.TEXT_MUTED,
            wraplength=270, justify="left", anchor="w")
        self.analysis_blocks.pack(fill="x", pady=(2, 0))
        
        # Foto-Schalter (nur nach Bild-Import)
        if self.photo is not None:
            photo_var = ctk.BooleanVar(value=self.photo_on)
            
            def toggle_photo():
                self.photo_on = photo_var.get()
                self.grid_editor.show_photo = self.photo_on
                self.grid_editor.render()
            
            ctk.CTkSwitch(
                stats_frame, text="Foto hinter dem Raster anzeigen", variable=photo_var,
                command=toggle_photo, font=Fonts.SMALL, text_color=Colors.TEXT_PRIMARY,
                progress_color=Colors.ACCENT,
            ).pack(anchor="w", pady=(10, 0))
        
        # Overlay-Schalter + Legende
        overlay_var = ctk.BooleanVar(value=self.overlay_on)
        
        def toggle_overlay():
            self.overlay_on = overlay_var.get()
            self.grid_editor.overlay_enabled = self.overlay_on
            self.grid_editor.render()
        
        ctk.CTkSwitch(
            stats_frame, text="Overlay: Blöcke & Format-Info", variable=overlay_var,
            command=toggle_overlay, font=Fonts.SMALL, text_color=Colors.TEXT_PRIMARY,
            progress_color=Colors.ACCENT,
        ).pack(anchor="w", pady=(10, 2))
        legend = ctk.CTkFrame(stats_frame, fg_color="transparent")
        legend.pack(fill="x")
        entries = [(Colors.OVERLAY_OK, "eindeutig"), (Colors.OVERLAY_CORRECTED, "korrigiert"),
                   (Colors.OVERLAY_AMBIGUOUS, "mehrdeutig"), (Colors.OVERLAY_UNSOLVABLE, "widersprüchlich"),
                   (Colors.OVERLAY_FORMAT, "Format-Info")]
        for i, (color, text) in enumerate(entries):
            item = ctk.CTkFrame(legend, fg_color="transparent")
            item.grid(row=i // 3, column=i % 3, sticky="w", padx=(0, 8))
            ctk.CTkLabel(item, text="■", font=Fonts.SMALL, text_color=color, width=10).pack(side="left")
            ctk.CTkLabel(item, text=text, font=("Segoe UI", 9), text_color=Colors.TEXT_MUTED).pack(side="left")

    def _build_sidebar_controls(self, parent):
        ctk.CTkLabel(parent, text="Werkzeuge", font=Fonts.SUBHEADING, text_color=Colors.TEXT_PRIMARY).pack(padx=20, anchor="w", pady=(0, 10))
        
        # Buttons Grid
        btn_grid = ctk.CTkFrame(parent, fg_color="transparent")
        btn_grid.pack(fill="x", padx=15)
        
        def reset():
            # Alles außer den festen Mustern wird unbekannt, Farben werden verworfen
            self.grid_editor.push_undo()
            self.matrix.reset()
            self.grid_editor.render()
            self._update_stats_sidebar()
            
        def unknown_to_white():
            # Nützlich nach dem Abmalen nur der schwarzen Pixel: Rest als bekannt-weiß übernehmen
            from ..core.qr_matrix import CellState
            self.grid_editor.push_undo()
            mask = ~self.matrix.locked
            self.matrix.grid[mask] = CellState.WHITE
            self.matrix.locked[mask] = True
            self.grid_editor.render()
            self._update_stats_sidebar()
            
        def all_unknown():
            # Farben bleiben erhalten, alle nicht festen Pixel gelten als unbekannt
            self.grid_editor.push_undo()
            self.matrix.locked[~self.matrix.fixed] = False
            self.grid_editor.render()
            self._update_stats_sidebar()
            
        btns = [("Reset (alles leeren)", reset), ("Unbekannte → Weiß", unknown_to_white),
                ("Alles als unbekannt markieren", all_unknown)]
        for txt, cmd in btns:
            ctk.CTkButton(
                btn_grid, text=txt, command=cmd,
                height=32, font=Fonts.BODY,
                fg_color=Colors.BG_PRIMARY, text_color=Colors.TEXT_PRIMARY,
                hover_color=Colors.BG_CARD_HOVER, border_width=0
            ).pack(fill="x", pady=4)
        
        # Hints
        ctk.CTkLabel(parent, text="Steuerung:", font=Fonts.SMALL, text_color=Colors.TEXT_MUTED).pack(padx=20, anchor="w", pady=(20, 5))
        hints = ["Linksklick: Schwarz/Weiß malen (= bekannt)", "Rechtsklick: unbekannt markieren / zurück",
                 "Scroll: Zoom", "Strg+Klick oder Mittelklick: Bewegen", "Strg+Z / Strg+Y: Rückgängig / Wiederholen"]
        for h in hints:
             ctk.CTkLabel(parent, text=f"• {h}", font=Fonts.SMALL, text_color=Colors.TEXT_MUTED).pack(padx=25, anchor="w")

    def _build_sidebar_action(self, parent):
        # Mode options
        ctk.CTkLabel(parent, text="Such-Modus", font=Fonts.SUBHEADING, text_color=Colors.TEXT_PRIMARY).pack(padx=20, anchor="w", pady=(0, 5))
        
        self.mode_var = ctk.StringVar(value="fast")
        self.mode_menu = ctk.CTkOptionMenu(
            parent, variable=self.mode_var,
            values=["fast", "accurate", "custom"],
            command=self._on_mode_change_sidebar,
            fg_color=Colors.BG_PRIMARY, 
            button_color=Colors.ACCENT,
            text_color=Colors.TEXT_PRIMARY,
            dropdown_fg_color=Colors.BG_CARD,
            dropdown_text_color=Colors.TEXT_PRIMARY,
            corner_radius=Dimensions.CORNER_RADIUS_M
        )
        self.mode_menu.pack(padx=20, fill="x")
        
        # Descriptions
        self.mode_desc = ctk.CTkLabel(parent, text="Reed-Solomon-Rekonstruktion (max. 30s).\nFallback-Bruteforce: max. 1.000 Versuche.", font=Fonts.SMALL, text_color=Colors.TEXT_MUTED, wraplength=280, justify="left")
        self.mode_desc.pack(padx=20, pady=(5,0), anchor="w")
        
        # Custom Inputs Container (Hidden by default)
        self.custom_inputs = ctk.CTkFrame(parent, fg_color="transparent")
        
        # Iterations Input
        row1 = ctk.CTkFrame(self.custom_inputs, fg_color="transparent")
        row1.pack(fill="x", pady=2)
        ctk.CTkLabel(row1, text="Max. Iter:", font=Fonts.SMALL, text_color=Colors.TEXT_PRIMARY, width=80, anchor="w").pack(side="left")
        self.custom_iter_entry = ctk.CTkEntry(row1, height=24, font=Fonts.SMALL)
        self.custom_iter_entry.insert(0, "100000")
        self.custom_iter_entry.pack(side="left", fill="x", expand=True)

        # Time Input
        row2 = ctk.CTkFrame(self.custom_inputs, fg_color="transparent")
        row2.pack(fill="x", pady=2)
        ctk.CTkLabel(row2, text="Max. Zeit (s):", font=Fonts.SMALL, text_color=Colors.TEXT_PRIMARY, width=80, anchor="w").pack(side="left")
        self.custom_time_entry = ctk.CTkEntry(row2, height=24, font=Fonts.SMALL)
        self.custom_time_entry.insert(0, "300")
        self.custom_time_entry.pack(side="left", fill="x", expand=True)
        
        ctk.CTkLabel(self.custom_inputs, text="* Stoppt wenn eines erreicht wird", font=("Segoe UI", 10), text_color=Colors.TEXT_MUTED).pack(anchor="w", pady=(2,0))

        
        # Bekannter Textanfang: hilft bei mehrdeutigem Schaden (Struktur-Solver)
        ctk.CTkLabel(parent, text="Bekannter Textanfang (optional)", font=Fonts.SMALL,
                     text_color=Colors.TEXT_PRIMARY).pack(padx=20, anchor="w", pady=(12, 2))
        self.prefix_entry = ctk.CTkEntry(parent, height=28, font=Fonts.BODY,
                                         placeholder_text="z.B. https://")
        self.prefix_entry.pack(padx=20, fill="x")
        if getattr(self, 'known_prefix', ''):
            self.prefix_entry.insert(0, self.known_prefix)
        ctk.CTkLabel(parent, text="Hilft, wenn der Code zu stark beschädigt ist.", font=("Segoe UI", 10),
                     text_color=Colors.TEXT_MUTED).pack(padx=20, anchor="w")

        self.btn_start = ctk.CTkButton(
            parent,
            text="✨ Wiederherstellen",
            command=self._start_bruteforce,
            height=40,
            font=Fonts.BUTTON_LARGE,
            fg_color=Colors.ACCENT,
            hover_color=Colors.ACCENT_HOVER,
            corner_radius=Dimensions.CORNER_RADIUS_M
        )
        self.btn_start.pack(padx=20, pady=20, fill="x")
        
    def _on_mode_change_sidebar(self, choice):
        if choice == "fast":
            self.mode_desc.configure(text="Reed-Solomon-Rekonstruktion (max. 30s).\nFallback-Bruteforce: max. 1.000 Versuche.")
            self.custom_inputs.pack_forget()
        elif choice == "accurate":
            self.mode_desc.configure(text="Reed-Solomon-Rekonstruktion (max. 120s).\nFallback-Bruteforce: max. 50.000 Versuche.")
            self.custom_inputs.pack_forget()
        elif choice == "custom":
            self.mode_desc.configure(text="Benutzerdefinierte Limits.\nLeerlassen = Keine Grenze.")
            self.custom_inputs.pack(padx=20, pady=10, fill="x")


    def _update_stats_sidebar(self):
        if not hasattr(self, 'stats_labels') or not self.stats_labels:
            return
        unknown = int((~self.matrix.locked).sum())
        self.stats_labels["Unbekannte Pixel"].configure(text=str(unknown))
        self._schedule_analysis()

    def _schedule_analysis(self):
        """Analyse erst nach einer kurzen Pause starten, nicht bei jedem gemalten Pixel"""
        if self._analysis_after is not None:
            self.after_cancel(self._analysis_after)
        self.stats_labels["Lösbarkeit"].configure(text="…", text_color=Colors.TEXT_MUTED)
        self._analysis_after = self.after(ANALYSIS_DEBOUNCE_MS, self._start_analysis)

    def _start_analysis(self):
        self._analysis_after = None
        self._analysis_generation += 1
        generation = self._analysis_generation
        snapshot = self.matrix.clone()  # der Thread arbeitet nie auf der Matrix, die gerade bemalt wird
        results = self._analysis_queue

        def work():
            try:
                report = analyze_solvability(snapshot)
            except Exception:
                logger.exception("Lösbarkeitsanalyse fehlgeschlagen")
                report = None
            results.put((generation, report))

        threading.Thread(target=work, daemon=True).start()
        if not self._analysis_polling:
            self._analysis_polling = True
            self.after(30, self._poll_analysis)

    def _poll_analysis(self):
        """Einzige Poll-Schleife: wartet auf das Ergebnis der neuesten Analyse, ältere werden verworfen"""
        found, current = False, None
        try:
            while True:
                generation, report = self._analysis_queue.get_nowait()
                if generation == self._analysis_generation:
                    found, current = True, report
                    break
        except queue.Empty:
            pass
        if not found and self.winfo_exists():
            self.after(30, self._poll_analysis)
            return
        self._analysis_polling = False
        self._show_analysis(current)

    def _editor_history(self, action: str):
        """Strg+Z / Strg+Y - nur im Editor"""
        editor = self.grid_editor
        if editor is None or not editor.winfo_exists() or self.is_running:
            return
        getattr(editor, action)()

    def _on_inspect(self, cell):
        """Codewort-Inspektor: erklärt das Modul unter der Maus"""
        if cell is None or not getattr(self, 'inspector_label', None) or not self.inspector_label.winfo_exists():
            return
        self.inspector_label.configure(text="  " + self._describe_module(*cell))

    def _describe_module(self, r: int, c: int) -> str:
        m = self.matrix
        assert m is not None  # der Inspektor existiert nur im Editor
        known = "bekannt" if m.locked[r, c] else "unbekannt"
        where = f"Zeile {r + 1}, Spalte {c + 1}"
        for copy, positions in enumerate(format_info_positions(m.size), start=1):
            if (r, c) in positions:
                return f"{where} · Format-Info, Bit {positions.index((r, c))} (Kopie {copy}) · {known}"
        if m.fixed[r, c]:
            if m.version >= 7 and any((r, c) in block for block in version_info_positions(m.size)):
                kind = "Version-Info"
            elif (r, c) == (4 * m.version + 9, 8):
                kind = "Dark Module"
            elif (r <= 7 and c <= 7) or (r <= 7 and c >= m.size - 8) or (r >= m.size - 8 and c <= 7):
                kind = "Finder-Pattern / Separator"
            elif r == 6 or c == 6:
                kind = "Timing-Pattern"
            else:
                kind = "Alignment-Pattern"
            return f"{where} · {kind} (fest, aus der Version)"
        report = self._last_report
        if report is None or report.module_codeword is None:
            return f"{where} · {known}"
        if report.module_codeword[r, c] < 0:
            return f"{where} · Restbit (gehört zu keinem Codewort) · {known}"
        index = int(report.module_codeword[r, c])
        block, pos, is_ec = report.codeword_location[index]
        text = (f"{where} · Codewort {index + 1} · Block {block + 1}, Byte {pos + 1} "
                f"({'Fehlerkorrektur' if is_ec else 'Daten'}) · Bit {report.module_bit[r, c]} · {known}")
        # Wert des Codeworts (entmaskiert), wenn alle 8 Bits bekannt sind
        if self._inspect_cache[0] is not report:
            reading = read_codewords((m.grid == 1).astype('uint8'), m.locked, m.version, report.format.mask)
            self._inspect_cache = (report, reading)
        reading = self._inspect_cache[1]
        if reading.known_masks[index] == 0xFF:
            # Nur hex: Zeichen sind gegenüber den Codewörtern um den Modus-Indikator (4 Bit) verschoben
            text += f" · Wert 0x{reading.values[index]:02X}"
        return text

    def _show_analysis(self, report):
        labels = getattr(self, 'stats_labels', None)
        if not labels or not labels["Lösbarkeit"].winfo_exists():
            return  # Editor wurde inzwischen verlassen
        if report is None:
            labels["Lösbarkeit"].configure(text="Fehler", text_color=Colors.ERROR)
            return
        
        self._last_report = report
        self._inspect_cache = (None, None)
        text, color = VERDICT_DISPLAY[report.verdict]
        labels["Lösbarkeit"].configure(text=text, text_color=color)
        fmt = report.format
        fmt_text = f"{fmt.ec_level} / Maske {fmt.mask}"
        if fmt.known_bits == 0:
            fmt_text += " (geraten)"
        elif fmt.mismatches:
            fmt_text += f" ({fmt.mismatches} Bit abweichend)"
        labels["Format"].configure(text=fmt_text)
        message = report.message
        if report.verdict == VERDICT_AMBIGUOUS:
            message += (" Tipp: Den bekannten Textanfang eintragen (z.B. https://) - die Rekonstruktion "
                        "nutzt zusätzlich den Aufbau der Daten (Länge, Füllbytes).")
        self.analysis_message.configure(text=message)
        
        # Blöcke: bei wenigen einzeln auflisten, sonst zusammenfassen
        if len(report.blocks) <= 4:
            lines = [f"Block {b.index + 1}: {b.unknown_codewords}/{b.nsym} Codewörter unbekannt "
                     f"– {BLOCK_STATUS_NAMES[b.status]}" for b in report.blocks]
        else:
            counts = {}
            for b in report.blocks:
                counts[b.status] = counts.get(b.status, 0) + 1
            lines = [f"{len(report.blocks)} Blöcke: " + ", ".join(
                f"{n} {BLOCK_STATUS_NAMES[status]}" for status, n in counts.items())]
        lines.append("(unbekannte Codewörter / EC-Codewörter je Block)")
        self.analysis_blocks.configure(text="\n".join(lines))
        
        if self.grid_editor is not None and self.grid_editor.winfo_exists():
            self.grid_editor.set_overlay(report, enabled=self.overlay_on)

    def _start_bruteforce(self):
        """Rekonstruktion starten: erst Reed-Solomon, Pixel-Bruteforce nur als Fallback"""
        stats = self.matrix.get_stats()
        unknown = stats['unknown_cells']
        
        if unknown == 0:
            messagebox.showinfo("Info", "Alle Pixel sind bereits bekannt!", parent=self)
            return
        
        if hasattr(self, 'btn_start'):
            self.btn_start.configure(state="disabled", text="⏳ Arbeite...")
        # Alle Eingaben des Editors lesen, bevor die Ergebnisansicht ihn ersetzt
        self.known_prefix = self.prefix_entry.get().strip() if hasattr(self, 'prefix_entry') else ''
        
        mode = self.mode_var.get()
        max_iter = None
        max_time = None
        
        if mode == "custom":
            # Defaults
            max_iter = 100000
            max_time = 300
            
            # Try to read inputs from sidebar if they exist
            try:
                if hasattr(self, 'custom_iter_entry'):
                    val_i = self.custom_iter_entry.get()
                    if val_i: max_iter = int(val_i)
                
                if hasattr(self, 'custom_time_entry'):
                    val_t = self.custom_time_entry.get()
                    if val_t: max_time = float(val_t)
            except ValueError:
                pass # Use defaults
            
        elif mode == "fast":
            max_iter = 1000
            max_time = 30
        else:
            # accurate
            max_iter = 50000
            max_time = 120
        
        self._run_settings = (mode, max_iter, max_time)
        self._build_results_view()
        self.is_running = True
        job = Reconstructor(self.matrix, self.validator, known_prefix=self.known_prefix)
        self._start_job(job, lambda: job.run(max_time=max_time), "rs_complete")

    def _start_job(self, job, run_job, complete_message):
        """Startet einen Job (Reconstructor/BruteforceEngine) in einem Hintergrund-Thread"""
        self.active_job = job

        # Worker-Thread kommuniziert nur über seine eigene Queue mit der UI.
        # Lokale Variable statt self.msg_queue, damit ein alter Lauf nie in die Queue eines neuen schreibt.
        msg_queue = queue.Queue()
        self.msg_queue = msg_queue

        job.set_progress_callback(lambda tested, valid, total: msg_queue.put(("progress", (tested, valid, total))))
        job.set_result_callback(lambda result: msg_queue.put(("result", result)))

        def run():
            msg_queue.put((complete_message, run_job()))

        self.bruteforce_thread = threading.Thread(target=run, daemon=True)
        self.bruteforce_thread.start()

        self._check_queue(msg_queue)

    def _start_fallback_bruteforce(self):
        """Pixel-Bruteforce, wenn die RS-Rekonstruktion keine Lösung gefunden hat"""
        mode, max_iter, max_time = self._run_settings
        unknown = self.matrix.get_stats()['unknown_cells']
        question = ("Die Reed-Solomon-Rekonstruktion hat keine Lösung gefunden.\n"
                    f"Pixel-Bruteforce über {unknown} unbekannte Pixel versuchen?")
        if unknown > 30:
            question += f"\n\nAchtung: 2^{unknown} Kombinationen - nur eine Stichprobe ist machbar."
        if not messagebox.askyesno("Keine Lösung", question, parent=self):
            self._on_complete([])
            return
        engine = BruteforceEngine(self.matrix, self.validator)
        self._start_job(
            engine,
            lambda: engine.run(mode=mode, max_iterations=max_iter, max_time=max_time, parallel=True),
            "complete",
        )

    def _check_queue(self, msg_queue):
        """Pollt die Queue des Worker-Threads (läuft im Tk-Main-Thread)"""
        # Ein Lauf, der per "Zurück" verlassen oder durch einen neuen ersetzt wurde, pollt nicht weiter
        if not self.winfo_exists() or not self.is_running or msg_queue is not self.msg_queue:
            return

        try:
            while True:
                m_type, data = msg_queue.get_nowait()

                if m_type == "progress":
                    self._update_progress_ui(*data)
                elif m_type == "result":
                    self.results_view.add_result(data)
                elif m_type == "rs_complete":
                    # Fallback nur, wenn RS nichts fand und der Nutzer nicht abgebrochen hat
                    if data or self.active_job.stop_requested:
                        self._on_complete(data)
                    else:
                        self._start_fallback_bruteforce()
                    return # Stop polling
                elif m_type == "complete":
                    self._on_complete(data)
                    return # Stop polling

        except queue.Empty:
            pass

        self.after(50, self._check_queue, msg_queue)


    def _build_results_view(self):
        for w in self.winfo_children():
            w.destroy()
        
        main = ctk.CTkFrame(self, fg_color=Colors.BG_PRIMARY, corner_radius=Dimensions.CORNER_RADIUS_NONE)
        main.pack(fill="both", expand=True)
        
        # Header
        header = ctk.CTkFrame(main, fg_color=Colors.BG_SECONDARY, height=60, corner_radius=Dimensions.CORNER_RADIUS_NONE)
        header.pack(fill="x")
        header.pack_propagate(False)
        
        # Shadow line
        ctk.CTkFrame(main, fg_color="#d1d5db", height=1).pack(fill="x")
        
        self.header_title = ctk.CTkLabel(header, text="✨ Rekonstruktion läuft...", font=Fonts.HEADING, text_color=Colors.TEXT_PRIMARY)
        self.header_title.pack(side="left", padx=20, pady=10)
        
        self.progress_label = ctk.CTkLabel(header, text="0 / 0", font=Fonts.BODY, text_color=Colors.TEXT_PRIMARY)
        self.progress_label.pack(side="left", padx=20)
        
        self.btn_stop = ctk.CTkButton(
            header, text="⛔ Abbrechen", command=self._stop,
            width=120, height=32,
            fg_color="transparent",
            text_color=Colors.ERROR,
            hover_color="#fee2e2", # Red-50
            border_width=Dimensions.BORDER_WIDTH_THIN, border_color=Colors.ERROR,
            corner_radius=Dimensions.CORNER_RADIUS_M
        )
        self.btn_stop.pack(side="right", padx=20)
        
        self.progress_bar = ctk.CTkProgressBar(main, mode="indeterminate", height=4, progress_color=Colors.ACCENT, corner_radius=Dimensions.CORNER_RADIUS_NONE)
        self.progress_bar.pack(fill="x")
        self.progress_bar.start()
        
        # Untere Leiste zuerst packen, damit sie nie von der (wachsenden) Ergebnisansicht verdrängt wird
        bottom = ctk.CTkFrame(main, fg_color=Colors.BG_SECONDARY, height=60, corner_radius=Dimensions.CORNER_RADIUS_NONE)
        bottom.pack(fill="x", side="bottom")
        ctk.CTkFrame(bottom, fg_color="#d1d5db", height=1).pack(fill="x", side="top")
        
        ctk.CTkButton(
            bottom, text="⬅ Zurück zum Editor", command=self._back,
            width=180, height=36,
            fg_color=Colors.BG_CARD,
            text_color=Colors.TEXT_PRIMARY,
            hover_color=Colors.BG_CARD_HOVER,
            corner_radius=Dimensions.CORNER_RADIUS_M
        ).pack(side="left", padx=20, pady=12)
        
        self.results_view = ResultsView(main)
        self.results_view.pack(fill="both", expand=True, padx=20, pady=20)
    
    def _update_progress_ui(self, tested, valid, total):
        self.progress_label.configure(text=f"{tested:,} / {total:,} ({valid} gültig)")

    def _on_complete(self, results):
        self.is_running = False
        self.header_title.configure(text="✨ Rekonstruktion abgeschlossen" if results else "Keine Lösung gefunden")
        self.progress_bar.stop()
        self.progress_bar.pack_forget()
        self.btn_stop.configure(state="normal", text="✓ Fertig", command=self._back, fg_color=Colors.SUCCESS, text_color="#ffffff", hover_color="#2e8b57")
        
        stats = self.active_job.get_stats()
        if stats.get('mode') == 'rs':
            text = (f"Reed-Solomon-Rekonstruktion\nGeprüfte Formate: {stats['tested']}\n"
                    f"Lösungen: {stats['valid']}\nZeit: {stats.get('elapsed', 0):.1f}s")
        else:
            text = f"Tests: {stats['tested']:,}\nGültig: {stats['valid']}\nZeit: {stats.get('elapsed', 0):.1f}s"
        messagebox.showinfo("Fertig", text, parent=self)
    
    def _stop(self):
        if self.active_job:
            self.active_job.stop()
        self.btn_stop.configure(state="disabled", text="Gestoppt")
    
    def _back(self):
        if self.is_running:
            if not messagebox.askyesno("Abbrechen?", "Noch am Laufen. Wirklich abbrechen?", parent=self):
                return
            self._stop()
            self.is_running = False
        self._build_editor_view()


class MainWindow(MainWindowMixin, ctk.CTk):
    """Standalone-Hauptfenster"""
    def __init__(self, is_standalone=True):
        super().__init__()
        self._init_shared(is_standalone=is_standalone)


class MainWindowToplevel(MainWindowMixin, ctk.CTkToplevel):
    """Kindfenster für den Hub"""
    def __init__(self):
        super().__init__()
        self._init_shared(is_standalone=False)
        self.after(200, lambda: self.focus())


def run_app():
    MainWindow().mainloop()


if __name__ == "__main__":
    run_app()