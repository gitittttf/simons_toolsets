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
class Colors:
    BG_PRIMARY = "#0f0f1a"
    BG_SECONDARY = "#1a1a2e"
    BG_CARD = "#252540"
    BG_CARD_HOVER = "#303055"
    ACCENT = "#00d4aa"
    ACCENT_HOVER = "#00b894"
    ACCENT_SECONDARY = "#6366f1"
    TEXT_PRIMARY = "#ffffff"
    TEXT_SECONDARY = "#a0a0b0"
    TEXT_MUTED = "#606070"
    SUCCESS = "#00ff88"
    WARNING = "#ffaa00"
    ERROR = "#ff4466"
    BORDER = "#303050"


class Fonts:
    TITLE = ("Segoe UI", 36, "bold")
    HEADING = ("Segoe UI", 20, "bold")
    SUBHEADING = ("Segoe UI", 16, "bold")
    BODY = ("Segoe UI", 14)
    BODY_BOLD = ("Segoe UI", 14, "bold")
    SMALL = ("Segoe UI", 12)
    BUTTON = ("Segoe UI", 14)
    BUTTON_LARGE = ("Segoe UI", 16, "bold")


def setup_theme():
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("dark-blue")


# =============================================================================
# HAUPTFENSTER
# =============================================================================
class MainWindow(ctk.CTk):
    """Hauptfenster mit offiziellen QR-Code Größen"""
    
    def __init__(self):
        super().__init__()
        setup_theme()
        
        self.title("🔍 QR-Code Rekonstruktion")
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
        
        container = ctk.CTkFrame(self, fg_color=Colors.BG_PRIMARY)
        container.pack(fill="both", expand=True)
        
        center = ctk.CTkFrame(container, fg_color="transparent")
        center.place(relx=0.5, rely=0.45, anchor="center")
        
        # Logo & Title
        ctk.CTkLabel(center, text="🔍", font=("Segoe UI Emoji", 72), text_color=Colors.ACCENT).pack(pady=(0, 10))
        ctk.CTkLabel(center, text="QR-Code Rekonstruktion", font=Fonts.TITLE, text_color=Colors.TEXT_PRIMARY).pack(pady=(0, 5))
        ctk.CTkLabel(center, text="Rekonstruiere beschädigte QR-Codes durch intelligentes Bruteforcing", font=Fonts.BODY, text_color=Colors.TEXT_SECONDARY).pack(pady=(0, 40))
        
        # Divider
        ctk.CTkFrame(center, height=1, fg_color=Colors.BORDER).pack(fill="x", padx=100, pady=15)
        
        # Version Selection
        version_section = ctk.CTkFrame(center, fg_color="transparent")
        version_section.pack(pady=20)
        
        ctk.CTkLabel(version_section, text="QR-Code Version wählen:", font=Fonts.SUBHEADING, text_color=Colors.TEXT_PRIMARY).pack(pady=(0, 20))
        
        # Quick Select: Common Versions
        quick_frame = ctk.CTkFrame(version_section, fg_color="transparent")
        quick_frame.pack(pady=10)
        
        # Häufige Versionen als Buttons
        common_versions = [
            (1, "V1", "21×21"),
            (2, "V2", "25×25"),
            (3, "V3", "29×29"),
            (4, "V4", "33×33"),
            (5, "V5", "37×37"),
            (6, "V6", "41×41"),
        ]
        
        for i, (version, label, size_str) in enumerate(common_versions):
            size = QR_VERSIONS[version][0]
            btn = ctk.CTkButton(
                quick_frame,
                text=f"{label}\n{size_str}",
                command=lambda s=size: self._create_matrix(s),
                width=100,
                height=60,
                font=Fonts.BODY,
                fg_color=Colors.BG_CARD,
                hover_color=Colors.BG_CARD_HOVER,
                corner_radius=10,
                border_width=1,
                border_color=Colors.BORDER
            )
            btn.grid(row=0, column=i, padx=6, pady=5)
        
        # OR Divider
        ctk.CTkLabel(version_section, text="— oder wähle eine andere Version —", font=Fonts.SMALL, text_color=Colors.TEXT_MUTED).pack(pady=15)
        
        # Version Dropdown
        dropdown_frame = ctk.CTkFrame(version_section, fg_color=Colors.BG_CARD, corner_radius=12)
        dropdown_frame.pack(pady=10)
        
        input_row = ctk.CTkFrame(dropdown_frame, fg_color="transparent")
        input_row.pack(pady=20, padx=30)
        
        ctk.CTkLabel(input_row, text="Version:", font=Fonts.BODY, text_color=Colors.TEXT_PRIMARY).pack(side="left", padx=(0, 10))
        
        # Erstelle Version-Options
        version_options = []
        for v in range(1, 41):
            size = QR_VERSIONS[v][0]
            version_options.append(f"V{v} ({size}×{size})")
        
        self.version_var = ctk.StringVar(value=version_options[0])
        self.version_dropdown = ctk.CTkComboBox(
            input_row,
            values=version_options,
            variable=self.version_var,
            width=180,
            height=40,
            font=Fonts.BODY,
            fg_color=Colors.BG_SECONDARY,
            border_color=Colors.BORDER,
            button_color=Colors.ACCENT,
            button_hover_color=Colors.ACCENT_HOVER,
            dropdown_fg_color=Colors.BG_SECONDARY
        )
        self.version_dropdown.pack(side="left", padx=10)
        
        ctk.CTkButton(
            input_row,
            text="Starten →",
            command=self._start_from_dropdown,
            width=120,
            height=40,
            font=Fonts.BODY_BOLD,
            fg_color=Colors.ACCENT,
            hover_color=Colors.ACCENT_HOVER,
            text_color=Colors.BG_PRIMARY,
            corner_radius=20
        ).pack(side="left", padx=(15, 0))
        
        # Info
        ctk.CTkLabel(
            dropdown_frame,
            text="Offizieller QR-Code Standard: Version 1 (21×21) bis Version 40 (177×177)",
            font=Fonts.SMALL,
            text_color=Colors.TEXT_MUTED
        ).pack(pady=(0, 15))
        
        # Footer
        ctk.CTkLabel(
            container,
            text="© 2024 Simon's Toolset  •  Made with ❤️",
            font=Fonts.SMALL,
            text_color=Colors.TEXT_MUTED
        ).pack(side="bottom", pady=20)
    
    def _start_from_dropdown(self):
        """Startet mit ausgewählter Version"""
        selected = self.version_var.get()
        # Parse "V1 (21×21)" -> version 1
        version = int(selected.split("V")[1].split(" ")[0])
        size = QR_VERSIONS[version][0]
        self._create_matrix(size)
    
    def _create_matrix(self, size: int):
        """Erstellt Matrix mit korrekten QR-Patterns"""
        self.matrix = QRMatrix(size=size)
        self._build_editor_view()
    
    def _build_editor_view(self):
        """Editor View"""
        for widget in self.winfo_children():
            widget.destroy()
        
        main = ctk.CTkFrame(self, fg_color=Colors.BG_PRIMARY)
        main.pack(fill="both", expand=True)
        
        # Header (zuerst, von oben)
        header = ctk.CTkFrame(main, fg_color=Colors.BG_SECONDARY, height=70)
        header.pack(fill="x")
        header.pack_propagate(False)
        
        ctk.CTkButton(
            header, text="← Zurück",
            command=self._build_start_screen,
            width=100, height=38,
            font=Fonts.BODY,
            fg_color="transparent",
            hover_color=Colors.BG_CARD,
            text_color=Colors.TEXT_SECONDARY,
            border_width=1,
            border_color=Colors.BORDER
        ).pack(side="left", padx=20, pady=16)
        
        version = get_version_for_size(self.matrix.size)
        ctk.CTkLabel(
            header,
            text=f"📊 QR-Code Editor (Version {version}, {self.matrix.size}×{self.matrix.size})",
            font=Fonts.HEADING,
            text_color=Colors.TEXT_PRIMARY
        ).pack(side="left", padx=15)
        
        # Bottom: Action Bar (ZUERST packen mit side="bottom", vor content!)
        self._build_action_bar(main)
        
        # Content (expand=True nimmt restlichen Platz)
        content = ctk.CTkFrame(main, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=20, pady=15)
        
        # Left: Grid
        left = ctk.CTkFrame(content, fg_color=Colors.BG_CARD, corner_radius=16, border_width=1, border_color=Colors.BORDER)
        left.pack(side="left", fill="both", expand=True, padx=(0, 10))
        
        ctk.CTkLabel(left, text="QR-Code Grid", font=Fonts.SUBHEADING, text_color=Colors.TEXT_PRIMARY).pack(pady=(20, 5))
        ctk.CTkLabel(left, text="Klicke & ziehe zum Malen • Rechtsklick zum Sperren", font=Fonts.SMALL, text_color=Colors.TEXT_MUTED).pack(pady=(0, 10))
        
        # Dynamische Zellgröße basierend auf QR-Größe
        if self.matrix.size <= 33:
            cell_size = 20
        elif self.matrix.size <= 49:
            cell_size = 14
        elif self.matrix.size <= 77:
            cell_size = 10
        else:
            cell_size = 6
        
        self.grid_editor = GridEditor(left, self.matrix, cell_size=cell_size)
        self.grid_editor.pack(pady=10)
        
        self.editor_controls = GridEditorControls(left, self.grid_editor)
        self.editor_controls.pack(pady=10, padx=20, fill="x")
        
        def on_change(r, c):
            self.editor_controls.update_stats()
        
        self.grid_editor.on_cell_changed = on_change
        
        # Right: Config
        right = ctk.CTkFrame(content, fg_color=Colors.BG_CARD, corner_radius=16, border_width=1, border_color=Colors.BORDER, width=400)
        right.pack(side="right", fill="y", padx=(10, 0))
        right.pack_propagate(False)
        
        self._build_config(right)
    
    def _build_config(self, parent):
        """Konfigurations-Panel"""
        ctk.CTkLabel(parent, text="⚙️ Konfiguration", font=Fonts.HEADING, text_color=Colors.TEXT_PRIMARY).pack(pady=(25, 20), padx=20, anchor="w")
        
        # Mode
        mode_frame = ctk.CTkFrame(parent, fg_color=Colors.BG_SECONDARY, corner_radius=12)
        mode_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(mode_frame, text="Modus:", font=Fonts.BODY_BOLD, text_color=Colors.TEXT_PRIMARY).pack(pady=(15, 10), padx=15, anchor="w")
        
        self.mode_var = ctk.StringVar(value="fast")
        
        modes = [("fast", "⚡ Schnell (1k, 10s)"), ("accurate", "🎯 Akkurat (100k, 5min)"), ("custom", "⚙️ Custom")]
        
        for val, label in modes:
            ctk.CTkRadioButton(
                mode_frame, text=label,
                variable=self.mode_var, value=val,
                command=self._on_mode_change,
                font=Fonts.BODY,
                fg_color=Colors.ACCENT,
                hover_color=Colors.ACCENT_HOVER
            ).pack(anchor="w", padx=15, pady=4)
        
        ctk.CTkFrame(mode_frame, height=10, fg_color="transparent").pack()
        
        # Custom
        self.custom_frame = ctk.CTkFrame(parent, fg_color=Colors.BG_SECONDARY, corner_radius=12)
        
        ctk.CTkLabel(self.custom_frame, text="Custom:", font=Fonts.BODY_BOLD, text_color=Colors.TEXT_PRIMARY).pack(pady=(15, 10), padx=15, anchor="w")
        
        row1 = ctk.CTkFrame(self.custom_frame, fg_color="transparent")
        row1.pack(fill="x", padx=15, pady=5)
        ctk.CTkLabel(row1, text="Max Tests:", font=Fonts.BODY, text_color=Colors.TEXT_PRIMARY).pack(side="left")
        self.iter_entry = ctk.CTkEntry(row1, width=100, font=Fonts.BODY, fg_color=Colors.BG_CARD, border_color=Colors.BORDER)
        self.iter_entry.insert(0, "10000")
        self.iter_entry.pack(side="right")
        
        row2 = ctk.CTkFrame(self.custom_frame, fg_color="transparent")
        row2.pack(fill="x", padx=15, pady=5)
        ctk.CTkLabel(row2, text="Max Zeit (s):", font=Fonts.BODY, text_color=Colors.TEXT_PRIMARY).pack(side="left")
        self.time_entry = ctk.CTkEntry(row2, width=100, font=Fonts.BODY, fg_color=Colors.BG_CARD, border_color=Colors.BORDER)
        self.time_entry.insert(0, "60")
        self.time_entry.pack(side="right")
        
        ctk.CTkFrame(self.custom_frame, height=15, fg_color="transparent").pack()
        
        # Divider
        ctk.CTkFrame(parent, height=1, fg_color=Colors.BORDER).pack(fill="x", padx=20, pady=20)
        
        # Tips
        ctk.CTkLabel(parent, text="💡 Tipps", font=Fonts.BODY_BOLD, text_color=Colors.TEXT_PRIMARY).pack(padx=20, anchor="w")
        
        tips = ["• Mehr gelockte Pixel = schneller", "• URLs werden gut erkannt", "• Bei >25 unbekannt: sehr langsam"]
        for tip in tips:
            ctk.CTkLabel(parent, text=tip, font=Fonts.SMALL, text_color=Colors.TEXT_MUTED).pack(padx=20, anchor="w", pady=2)
    
    def _on_mode_change(self):
        if self.mode_var.get() == "custom":
            self.custom_frame.pack(fill="x", padx=20, pady=10)
        else:
            self.custom_frame.pack_forget()
    
    def _build_action_bar(self, parent):
        """Action Bar"""
        bar = ctk.CTkFrame(parent, fg_color=Colors.BG_SECONDARY, height=90)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)
        
        # Start Button
        self.btn_start = ctk.CTkButton(
            bar,
            text="🚀 Rekonstruktion starten",
            command=self._start_bruteforce,
            width=320,
            height=55,
            font=Fonts.BUTTON_LARGE,
            fg_color=Colors.ACCENT,
            hover_color=Colors.ACCENT_HOVER,
            text_color=Colors.BG_PRIMARY,
            corner_radius=27
        )
        self.btn_start.pack(side="right", padx=30, pady=17)
        
        # Quick Stats
        self.quick_stats = ctk.CTkLabel(bar, text="", font=Fonts.BODY, text_color=Colors.TEXT_SECONDARY)
        self.quick_stats.pack(side="left", padx=30, pady=17)
        self._update_quick_stats()
    
    def _update_quick_stats(self):
        if self.matrix and hasattr(self, 'quick_stats'):
            stats = self.matrix.get_stats()
            self.quick_stats.configure(text=f"📊 Version {stats['version']} • {stats['unknown_cells']} unbekannte Pixel")
    
    def _start_bruteforce(self):
        """Bruteforce starten"""
        stats = self.matrix.get_stats()
        unknown = stats['unknown_cells']
        
        if unknown == 0:
            messagebox.showinfo("Fertig", "Alle Pixel sind bereits bekannt!", parent=self)
            return
        
        if unknown > 30:
            if not messagebox.askyesno("Warnung", f"{unknown} unbekannte Pixel = extrem viele Kombinationen!\nDas wird sehr lange dauern. Fortfahren?", parent=self):
                return
        
        self.btn_start.configure(state="disabled", text="⏳ Startet...")
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
        
        main = ctk.CTkFrame(self, fg_color=Colors.BG_PRIMARY)
        main.pack(fill="both", expand=True)
        
        # Header
        header = ctk.CTkFrame(main, fg_color=Colors.BG_SECONDARY, height=80)
        header.pack(fill="x")
        header.pack_propagate(False)
        
        ctk.CTkLabel(header, text="🔄 Rekonstruktion...", font=Fonts.HEADING, text_color=Colors.TEXT_PRIMARY).pack(side="left", padx=25, pady=25)
        
        self.progress_label = ctk.CTkLabel(header, text="0 / 0", font=Fonts.BODY, text_color=Colors.ACCENT)
        self.progress_label.pack(side="left", padx=20)
        
        self.btn_stop = ctk.CTkButton(header, text="⏹ Stop", command=self._stop, width=100, height=40, fg_color=Colors.ERROR, hover_color="#cc3355", corner_radius=20)
        self.btn_stop.pack(side="right", padx=25)
        
        self.progress_bar = ctk.CTkProgressBar(main, mode="indeterminate", height=4, progress_color=Colors.ACCENT)
        self.progress_bar.pack(fill="x")
        self.progress_bar.start()
        
        self.results_view = ResultsView(main)
        self.results_view.pack(fill="both", expand=True, padx=20, pady=15)
        
        bottom = ctk.CTkFrame(main, fg_color=Colors.BG_SECONDARY, height=70)
        bottom.pack(fill="x", side="bottom")
        
        ctk.CTkButton(bottom, text="← Editor", command=self._back, width=150, height=40, fg_color="transparent", hover_color=Colors.BG_CARD, border_width=1, border_color=Colors.BORDER, corner_radius=20).pack(side="left", padx=20, pady=15)
    
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