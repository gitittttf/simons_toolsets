"""
Main Window - Mit offiziellen QR-Code Größen

Features:
- Nur offizielle QR-Versionen (1-40, Größen 21-177)
- Dropdown für Versionsauswahl
- Korrekte Pattern-Generierung
"""

import customtkinter as ctk
from tkinter import messagebox
import threading
from typing import Optional
from .grid_editor import GridEditor, GridEditorControls
from .results_view import ResultsView
from ..core.qr_matrix import QRMatrix, QR_VERSIONS, get_version_for_size
from ..core.bruteforce import BruteforceEngine
from ..core.validator import QRValidator


# =============================================================================
# FARBEN & FONTS
# =============================================================================
# =============================================================================
# FARBEN & FONTS
# =============================================================================
class Colors:
    """Classic Windows 95/98/2000 Theme"""
    # Classic Gray Scheme
    BG_PRIMARY = "#c0c0c0"          # Standard Windows Gray
    BG_SECONDARY = "#dfdfdf"         # 3D Light
    BG_CARD = "#c0c0c0"              # Same as background
    BG_CARD_HOVER = "#d0d0d0"        # Slightly lighter
    
    # Classic Accents
    ACCENT = "#000080"               # Title Bar Blue
    ACCENT_HOVER = "#101090"         # Slightly lighter blue
    ACCENT_SECONDARY = "#008080"     # Teal/Cyan
    
    # Text
    TEXT_PRIMARY = "#000000"         # Black
    TEXT_SECONDARY = "#404040"       # Dark Gray
    TEXT_MUTED = "#808080"           # Shadow Gray
    
    # Status
    SUCCESS = "#008000"              # Dark Green
    WARNING = "#808000"              # Olive
    ERROR = "#ff0000"                # Standard Red
    ERROR_HOVER = "#cc0000"
    
    # Border / 3D Effects
    BORDER = "#808080"               # Dark Shadow
    BORDER_LIGHT = "#ffffff"         # Highlight

class Fonts:
    TITLE = ("Tahoma", 24, "bold")
    HEADING = ("Tahoma", 14, "bold")
    SUBHEADING = ("Tahoma", 11, "bold")
    BODY = ("Tahoma", 11)
    BODY_BOLD = ("Tahoma", 11, "bold")
    SMALL = ("Tahoma", 10)
    BUTTON = ("Tahoma", 11)
    BUTTON_LARGE = ("Tahoma", 11, "bold")

def setup_theme():
    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("blue")

# =============================================================================
# HAUPTFENSTER
# =============================================================================
class MainWindow(ctk.CTk):
    """Hauptfenster im Classic Windows Style"""
    
    def __init__(self):
        super().__init__()
        setup_theme()
        
        self.title("QR-Code Rekonstruktion")
        self.geometry("1550x980")
        self.minsize(1200, 800)
        self.configure(fg_color=Colors.BG_PRIMARY)
        
        # State
        self.matrix: Optional[QRMatrix] = None
        self.validator = QRValidator()
        self.bruteforce_engine: Optional[BruteforceEngine] = None
        self.bruteforce_thread: Optional[threading.Thread] = None
        self.is_running = False
        
        # UI Components
        self.grid_editor: Optional[GridEditor] = None
        self.editor_controls: Optional[GridEditorControls] = None
        self.results_view: Optional[ResultsView] = None
        
        self._build_start_screen()
    
    def _build_start_screen(self):
        """Start-Screen mit Versionsauswahl"""
        for widget in self.winfo_children():
            widget.destroy()
        
        container = ctk.CTkFrame(self, fg_color=Colors.BG_PRIMARY, corner_radius=0)
        container.pack(fill="both", expand=True)
        
        center = ctk.CTkFrame(container, fg_color=Colors.BG_PRIMARY, border_width=2, border_color=Colors.BORDER, corner_radius=0)
        center.place(relx=0.5, rely=0.45, anchor="center")
        
        # Title
        ctk.CTkLabel(center, text="QR-Code Rekonstruktion", font=Fonts.TITLE, text_color=Colors.TEXT_PRIMARY).pack(pady=(20, 5), padx=40)
        ctk.CTkLabel(center, text="Beschädigte QR-Codes wiederherstellen", font=Fonts.BODY, text_color=Colors.TEXT_SECONDARY).pack(pady=(0, 30))
        
        # Divider
        ctk.CTkFrame(center, height=2, fg_color=Colors.BORDER, corner_radius=0).pack(fill="x", padx=20, pady=10)
        
        # Version Selection
        version_section = ctk.CTkFrame(center, fg_color="transparent", corner_radius=0)
        version_section.pack(pady=20)
        
        ctk.CTkLabel(version_section, text="QR-Code Version wählen:", font=Fonts.SUBHEADING, text_color=Colors.TEXT_PRIMARY).pack(pady=(0, 20))
        
        # Quick Select
        quick_frame = ctk.CTkFrame(version_section, fg_color="transparent", corner_radius=0)
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
                width=90,
                height=50,
                font=Fonts.BODY,
                fg_color=Colors.BG_PRIMARY,
                text_color=Colors.TEXT_PRIMARY,
                hover_color=Colors.BG_CARD_HOVER,
                corner_radius=0,
                border_width=2,
                border_color=Colors.BORDER
            )
            btn.grid(row=0, column=i, padx=5, pady=5)
        
        # OR Divider
        ctk.CTkLabel(version_section, text="- oder -", font=Fonts.SMALL, text_color=Colors.TEXT_MUTED).pack(pady=10)
        
        # Version Dropdown
        input_row = ctk.CTkFrame(version_section, fg_color="transparent", corner_radius=0)
        input_row.pack(pady=10)
        
        ctk.CTkLabel(input_row, text="Version:", font=Fonts.BODY, text_color=Colors.TEXT_PRIMARY).pack(side="left", padx=(0, 10))
        
        version_options = []
        for v in range(1, 41):
            size = QR_VERSIONS[v][0]
            version_options.append(f"V{v} ({size}x{size})")
        
        self.version_var = ctk.StringVar(value=version_options[0])
        self.version_dropdown = ctk.CTkComboBox(
            input_row,
            values=version_options,
            variable=self.version_var,
            width=180,
            height=30,
            font=Fonts.BODY,
            fg_color="#ffffff",
            border_color=Colors.BORDER,
            button_color=Colors.BG_PRIMARY,
            button_hover_color=Colors.BG_CARD_HOVER,
            dropdown_fg_color="#ffffff",
            dropdown_text_color="#000000",
            corner_radius=0,
            border_width=2
        )
        self.version_dropdown.pack(side="left", padx=10)
        
        ctk.CTkButton(
            input_row,
            text="Starten",
            command=self._start_from_dropdown,
            width=100,
            height=30,
            font=Fonts.BODY_BOLD,
            fg_color=Colors.BG_PRIMARY,
            text_color=Colors.TEXT_PRIMARY,
            hover_color=Colors.BG_CARD_HOVER,
            corner_radius=0,
            border_width=2,
            border_color=Colors.BORDER
        ).pack(side="left", padx=(10, 0))
        
        # Info
        ctk.CTkLabel(
            center,
            text="Version 1 (21x21) bis Version 40 (177x177)",
            font=Fonts.SMALL,
            text_color=Colors.TEXT_MUTED
        ).pack(pady=(10, 20))

    def _start_from_dropdown(self):
        """Startet mit ausgewählter Version"""
        selected = self.version_var.get()
        # Parse "V1 (21x21)" -> version 1
        version = int(selected.split("V")[1].split(" ")[0])
        size = QR_VERSIONS[version][0]
        self._create_matrix(size)
    
    def _create_matrix(self, size: int):
        """Erstellt Matrix"""
        self.matrix = QRMatrix(size=size)
        self._build_editor_view()
    
    def _build_editor_view(self):
        """Editor View"""
        for widget in self.winfo_children():
            widget.destroy()
        
        main = ctk.CTkFrame(self, fg_color=Colors.BG_PRIMARY, corner_radius=0)
        main.pack(fill="both", expand=True)
        
        # Toolbar (Classic Windows Toolbar style)
        toolbar = ctk.CTkFrame(main, fg_color=Colors.BG_PRIMARY, height=40, corner_radius=0, border_width=0)
        toolbar.pack(fill="x", side="top", pady=(0, 0))
        
        # Separator line
        ctk.CTkFrame(main, fg_color="#808080", height=1, corner_radius=0).pack(fill="x")
        ctk.CTkFrame(main, fg_color="#ffffff", height=1, corner_radius=0).pack(fill="x")
        
        ctk.CTkButton(
            toolbar, text="Zurück",
            command=self._build_start_screen,
            width=80, height=26,
            font=Fonts.BUTTON,
            fg_color=Colors.BG_PRIMARY,
            text_color=Colors.TEXT_PRIMARY,
            hover_color=Colors.BG_CARD_HOVER,
            border_width=2,
            border_color=Colors.BORDER,
            corner_radius=0
        ).pack(side="left", padx=5, pady=5)
        
        version = get_version_for_size(self.matrix.size)
        ctk.CTkLabel(
            toolbar,
            text=f"QR-Code Editor - V{version} ({self.matrix.size}x{self.matrix.size})",
            font=Fonts.BODY_BOLD,
            text_color=Colors.TEXT_PRIMARY
        ).pack(side="left", padx=10)
        
        # Action Bar (Bottom)
        self._build_action_bar(main)
        
        # Content
        content = ctk.CTkFrame(main, fg_color=Colors.BG_PRIMARY, corner_radius=0)
        content.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Left: Grid Container
        left_container = ctk.CTkFrame(content, fg_color=Colors.BG_PRIMARY, corner_radius=0, border_width=2, border_color=Colors.BORDER)
        left_container.pack(side="left", fill="both", expand=True, padx=(0, 5))
        
        ctk.CTkLabel(left_container, text="Grid: Links=Malen, Rechts=Sperren", font=Fonts.SMALL, text_color=Colors.TEXT_MUTED).pack(pady=5)
        
        # Grid
        if self.matrix.size <= 33:
            cell_size = 20
        elif self.matrix.size <= 49:
            cell_size = 14
        elif self.matrix.size <= 77:
            cell_size = 10
        else:
            cell_size = 6
        
        self.grid_editor = GridEditor(left_container, self.matrix, cell_size=cell_size)
        self.grid_editor.pack(pady=5)
        
        self.editor_controls = GridEditorControls(left_container, self.grid_editor)
        self.editor_controls.pack(pady=5, padx=5, fill="x")
        
        def on_change(r, c):
            self.editor_controls.update_stats()
        
        self.grid_editor.on_cell_changed = on_change
        
        # Right: Config
        right = ctk.CTkFrame(content, fg_color=Colors.BG_PRIMARY, corner_radius=0, border_width=2, border_color=Colors.BORDER, width=350)
        right.pack(side="right", fill="y", padx=(0, 0))
        right.pack_propagate(False)
        
        self._build_config(right)
    
    def _build_config(self, parent):
        """Konfigurations-Panel"""
        # "Title Bar" for the panel
        title_bar = ctk.CTkFrame(parent, fg_color=Colors.ACCENT, height=24, corner_radius=0)
        title_bar.pack(fill="x", padx=2, pady=2)
        ctk.CTkLabel(title_bar, text="Einstellungen", font=("Tahoma", 11, "bold"), text_color="#ffffff").pack(side="left", padx=5)

        # Mode
        mode_frame = ctk.CTkFrame(parent, fg_color=Colors.BG_PRIMARY, corner_radius=0, border_width=1, border_color="#808080")
        mode_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(mode_frame, text="Modus:", font=Fonts.BODY_BOLD, text_color=Colors.TEXT_PRIMARY).pack(pady=(5, 5), padx=5, anchor="w")
        
        self.mode_var = ctk.StringVar(value="fast")
        
        modes = [("fast", "Schnell (1k Tests)"), ("accurate", "Genau (100k Tests)"), ("custom", "Benutzerdefiniert")]
        
        for val, label in modes:
            ctk.CTkRadioButton(
                mode_frame, text=label,
                variable=self.mode_var, value=val,
                command=self._on_mode_change,
                font=Fonts.BODY,
                fg_color=Colors.ACCENT,
                hover_color=Colors.ACCENT_HOVER,
                text_color=Colors.TEXT_PRIMARY
            ).pack(anchor="w", padx=10, pady=2)
        
        # Custom
        self.custom_frame = ctk.CTkFrame(parent, fg_color=Colors.BG_PRIMARY, corner_radius=0)
        
        row1 = ctk.CTkFrame(self.custom_frame, fg_color="transparent")
        row1.pack(fill="x", padx=5, pady=2)
        ctk.CTkLabel(row1, text="Max Tests:", font=Fonts.BODY, text_color=Colors.TEXT_PRIMARY).pack(side="left")
        self.iter_entry = ctk.CTkEntry(row1, width=80, font=Fonts.BODY, fg_color="#ffffff", border_color=Colors.BORDER, corner_radius=0, border_width=2)
        self.iter_entry.insert(0, "10000")
        self.iter_entry.pack(side="right")
        
        row2 = ctk.CTkFrame(self.custom_frame, fg_color="transparent")
        row2.pack(fill="x", padx=5, pady=2)
        ctk.CTkLabel(row2, text="Zeit (s):", font=Fonts.BODY, text_color=Colors.TEXT_PRIMARY).pack(side="left")
        self.time_entry = ctk.CTkEntry(row2, width=80, font=Fonts.BODY, fg_color="#ffffff", border_color=Colors.BORDER, corner_radius=0, border_width=2)
        self.time_entry.insert(0, "60")
        self.time_entry.pack(side="right")
        
        # Tips
        tip_frame = ctk.CTkFrame(parent, fg_color="#ffffe1", corner_radius=0, border_width=1, border_color="#000000") # ToopTip yellow
        tip_frame.pack(fill="x", padx=10, pady=20)
        
        ctk.CTkLabel(tip_frame, text="Info", font=Fonts.BODY_BOLD, text_color="#000000").pack(anchor="w", padx=5, pady=(5,0))
        tips = ["- Mehr gelockte Pixel = schneller", "- URLs werden gut erkannt", "- >25 unbekannt = sehr langsam"]
        for tip in tips:
            ctk.CTkLabel(tip_frame, text=tip, font=Fonts.SMALL, text_color="#000000").pack(anchor="w", padx=5, pady=0)

    def _on_mode_change(self):
        if self.mode_var.get() == "custom":
            self.custom_frame.pack(fill="x", padx=10, pady=5)
        else:
            self.custom_frame.pack_forget()
    
    def _build_action_bar(self, parent):
        """Action Bar"""
        bar = ctk.CTkFrame(parent, fg_color=Colors.BG_PRIMARY, height=60, corner_radius=0, border_width=2, border_color=Colors.BORDER)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)
        
        # Start Button
        self.btn_start = ctk.CTkButton(
            bar,
            text="Rekonstruktion starten",
            command=self._start_bruteforce,
            width=200,
            height=30,
            font=Fonts.BUTTON_LARGE,
            fg_color=Colors.BG_PRIMARY,
            text_color=Colors.TEXT_PRIMARY,
            hover_color=Colors.BG_CARD_HOVER,
            corner_radius=0,
            border_width=2,
            border_color=Colors.BORDER
        )
        self.btn_start.pack(side="right", padx=10, pady=12)
        
        # Quick Stats
        self.quick_stats = ctk.CTkLabel(bar, text="", font=Fonts.BODY, text_color=Colors.TEXT_PRIMARY)
        self.quick_stats.pack(side="left", padx=15, pady=12)
        self._update_quick_stats()
    
    def _update_quick_stats(self):
        if self.matrix and hasattr(self, 'quick_stats'):
            stats = self.matrix.get_stats()
            self.quick_stats.configure(text=f"Version {stats['version']} | {stats['unknown_cells']} Unbekannt")
            
    def _start_bruteforce(self):
        """Bruteforce starten"""
        stats = self.matrix.get_stats()
        unknown = stats['unknown_cells']
        
        if unknown == 0:
            messagebox.showinfo("Info", "Alle Pixel sind bereits bekannt!", parent=self)
            return
            
        if unknown > 30:
            if not messagebox.askyesno("Warnung", f"{unknown} unbekannte Pixel = Extrem viele Kombinationen!\nFortfahren?", parent=self):
                return
        
        self.btn_start.configure(state="disabled", text="Arbeitet...")
        self._build_results_view()
        
        mode = self.mode_var.get()
        max_iter = None
        max_time = None
        
        if mode == "custom":
            try:
                max_iter = int(self.iter_entry.get())
                max_time = float(self.time_entry.get())
            except:
                pass
        
        self.is_running = True
        self.bruteforce_engine = BruteforceEngine(self.matrix, self.validator)
        self.bruteforce_engine.set_progress_callback(self._on_progress)
        self.bruteforce_engine.set_result_callback(self._on_result)
        
        def run():
            results = self.bruteforce_engine.run(mode=mode, max_iterations=max_iter, max_time=max_time, parallel=True)
            self.after(0, lambda: self._on_complete(results))
        
        self.bruteforce_thread = threading.Thread(target=run, daemon=True)
        self.bruteforce_thread.start()

    def _build_results_view(self):
        for w in self.winfo_children():
            w.destroy()
        
        main = ctk.CTkFrame(self, fg_color=Colors.BG_PRIMARY, corner_radius=0)
        main.pack(fill="both", expand=True)
        
        # Header
        header = ctk.CTkFrame(main, fg_color=Colors.BG_PRIMARY, height=50, corner_radius=0, border_width=2, border_color=Colors.BORDER)
        header.pack(fill="x")
        header.pack_propagate(False)
        
        ctk.CTkLabel(header, text="Rekonstruktion läuft...", font=Fonts.HEADING, text_color=Colors.TEXT_PRIMARY).pack(side="left", padx=15, pady=10)
        
        self.progress_label = ctk.CTkLabel(header, text="0 / 0", font=Fonts.BODY, text_color=Colors.TEXT_PRIMARY)
        self.progress_label.pack(side="left", padx=20)
        
        self.btn_stop = ctk.CTkButton(
            header, text="Stop", command=self._stop,
            width=80, height=26,
            fg_color=Colors.BG_PRIMARY,
            text_color=Colors.ERROR,
            hover_color=Colors.BG_CARD_HOVER,
            border_width=2, border_color=Colors.ERROR,
            corner_radius=0
        )
        self.btn_stop.pack(side="right", padx=15)
        
        self.progress_bar = ctk.CTkProgressBar(main, mode="indeterminate", height=10, progress_color=Colors.ACCENT, corner_radius=0)
        self.progress_bar.pack(fill="x")
        self.progress_bar.start()
        
        self.results_view = ResultsView(main)
        self.results_view.pack(fill="both", expand=True, padx=5, pady=5)
        
        bottom = ctk.CTkFrame(main, fg_color=Colors.BG_PRIMARY, height=50, corner_radius=0, border_width=0)
        bottom.pack(fill="x", side="bottom")
        ctk.CTkFrame(bottom, fg_color="#808080", height=1).pack(fill="x", side="top")
        
        ctk.CTkButton(
            bottom, text="Zurück zum Editor", command=self._back,
            width=150, height=30,
            fg_color=Colors.BG_PRIMARY,
            text_color=Colors.TEXT_PRIMARY,
            hover_color=Colors.BG_CARD_HOVER,
            border_width=2, border_color=Colors.BORDER,
            corner_radius=0
        ).pack(side="left", padx=10, pady=10)
    
    def _on_progress(self, tested, valid, total):
        self.after(0, lambda: self.progress_label.configure(text=f"{tested:,} / {total:,} ({valid} gültig)"))
    
    def _on_result(self, result):
        self.after(0, lambda: self.results_view.add_result(result))
    
    def _on_complete(self, results):
        self.is_running = False
        self.progress_bar.stop()
        self.progress_bar.pack_forget()
        self.btn_stop.configure(state="disabled", text="✓ Fertig")
        
        stats = self.bruteforce_engine.get_stats()
        messagebox.showinfo("Fertig", f"Tests: {stats['tested']:,}\nGültig: {stats['valid']}\nZeit: {stats.get('elapsed', 0):.1f}s", parent=self)
    
    def _stop(self):
        if self.bruteforce_engine:
            self.bruteforce_engine.stop()
        self.btn_stop.configure(state="disabled", text="Gestoppt")
    
    def _back(self):
        if self.is_running:
            if not messagebox.askyesno("Abbrechen?", "Noch am Laufen. Wirklich abbrechen?", parent=self):
                return
            self._stop()
        self._build_editor_view()


def run_app():
    MainWindow().mainloop()


if __name__ == "__main__":
    run_app()