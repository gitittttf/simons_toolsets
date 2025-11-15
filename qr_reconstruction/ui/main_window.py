"""
Main Window - Hauptanwendungsfenster
Orchestriert alle Komponenten
"""

import customtkinter as ctk
from tkinter import messagebox
import threading
from typing import Optional
from .grid_editor import GridEditor, GridEditorControls
from .results_view import ResultsView
from ..core.qr_matrix import QRMatrix
from ..core.bruteforce import BruteforceEngine, BruteforceMode
from ..core.validator import QRValidator


class MainWindow(ctk.CTk):
    """
    Hauptfenster der Anwendung
    
    Aufbau:
    - Links: Grid-Editor mit Controls
    - Rechts: Konfigurations-Panel
    - Unten: Start-Button
    - Nach Start: Wechsel zu Results View
    """
    
    def __init__(self):
        super().__init__()
        
        # Window Setup
        self.title("QR-Code Rekonstruktion")
        self.geometry("1400x900")
        
        # Theme
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")
        
        # State
        self.matrix: Optional[QRMatrix] = None
        self.validator = QRValidator()
        self.bruteforce_engine: Optional[BruteforceEngine] = None
        self.bruteforce_thread: Optional[threading.Thread] = None
        self.is_running = False
        
        # Views
        self.editor_view: Optional[ctk.CTkFrame] = None
        self.results_view: Optional[ResultsView] = None
        
        # Build UI
        self._build_start_screen()
    
    def _build_start_screen(self):
        """Baut den Start-Screen (Grid-Größen-Auswahl)"""
        # Clear
        for widget in self.winfo_children():
            widget.destroy()
        
        # Container
        container = ctk.CTkFrame(self)
        container.pack(expand=True)
        
        # Title
        title = ctk.CTkLabel(
            container,
            text="🔍 QR-Code Rekonstruktion",
            font=("Arial", 32, "bold")
        )
        title.pack(pady=30)
        
        subtitle = ctk.CTkLabel(
            container,
            text="Rekonstruiere beschädigte QR-Codes durch intelligentes Bruteforcing",
            font=("Arial", 14)
        )
        subtitle.pack(pady=10)
        
        # Size Selection
        ctk.CTkLabel(
            container,
            text="Wähle die QR-Code-Größe:",
            font=("Arial", 16, "bold")
        ).pack(pady=(40, 20))
        
        size_frame = ctk.CTkFrame(container)
        size_frame.pack(pady=20)
        
        sizes = [
            (21, "Version 1 (21×21)"),
            (25, "Version 2 (25×25)"),
            (29, "Version 3 (29×29)"),
            (33, "Version 4 (33×33)"),
            (37, "Version 5 (37×37)"),
            (41, "Version 6 (41×41)")
        ]
        
        for size, label in sizes:
            btn = ctk.CTkButton(
                size_frame,
                text=label,
                command=lambda s=size: self._start_editor(s),
                width=200,
                height=40,
                font=("Arial", 14)
            )
            btn.pack(pady=5)
        
        # Footer
        footer = ctk.CTkLabel(
            container,
            text="© 2024 Simon's Toolset",
            font=("Arial", 10),
            text_color="gray"
        )
        footer.pack(side="bottom", pady=20)
    
    def _start_editor(self, size: int):
        """Startet den Editor mit gewählter Größe"""
        self.matrix = QRMatrix(size=size)
        self._build_editor_view()
    
    def _build_editor_view(self):
        """Baut den Editor-View"""
        # Clear
        for widget in self.winfo_children():
            widget.destroy()
        
        # Main Container
        main_container = ctk.CTkFrame(self)
        main_container.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Left Side: Editor
        left_frame = ctk.CTkFrame(main_container)
        left_frame.pack(side="left", fill="both", expand=True, padx=5)
        
        # Editor Title
        ctk.CTkLabel(
            left_frame,
            text=f"QR-Code Editor ({self.matrix.size}×{self.matrix.size})",
            font=("Arial", 18, "bold")
        ).pack(pady=10)
        
        # Grid Editor
        self.grid_editor = GridEditor(left_frame, self.matrix, cell_size=20)
        self.grid_editor.pack(pady=10)
        
        # Editor Controls (darunter)
        self.editor_controls = GridEditorControls(left_frame, self.grid_editor)
        self.editor_controls.pack(pady=10, fill="x")
        
        # Callback für Änderungen
        def on_cell_changed(row, col):
            self.editor_controls.update_stats()
        
        self.grid_editor.on_cell_changed = on_cell_changed
        
        # Right Side: Config
        right_frame = ctk.CTkFrame(main_container)
        right_frame.pack(side="right", fill="y", padx=5)
        
        # Config Panel
        self._build_config_panel(right_frame)
        
        # Bottom: Action Buttons
        bottom_frame = ctk.CTkFrame(self)
        bottom_frame.pack(fill="x", padx=10, pady=10)
        
        btn_back = ctk.CTkButton(
            bottom_frame,
            text="◀ Zurück",
            command=self._build_start_screen,
            width=120
        )
        btn_back.pack(side="left", padx=10)
        
        self.btn_start = ctk.CTkButton(
            bottom_frame,
            text="🚀 Rekonstruktion starten",
            command=self._start_bruteforce,
            width=250,
            height=50,
            font=("Arial", 16, "bold"),
            fg_color="#00AA00",
            hover_color="#008800"
        )
        self.btn_start.pack(side="right", padx=10)
    
    def _build_config_panel(self, parent):
        """Baut das Konfigurations-Panel"""
        # Title
        ctk.CTkLabel(
            parent,
            text="Bruteforce-Konfiguration",
            font=("Arial", 16, "bold")
        ).pack(pady=15)
        
        # Mode Selection
        ctk.CTkLabel(
            parent,
            text="Modus:",
            font=("Arial", 12, "bold")
        ).pack(pady=(10, 5), anchor="w", padx=10)
        
        self.mode_var = ctk.StringVar(value="fast")
        
        modes = [
            ("fast", "⚡ Schnell (1k Iterationen, 10s)"),
            ("accurate", "🎯 Akkurat (100k Iterationen, 5min)"),
            ("custom", "⚙️ Custom")
        ]
        
        for value, text in modes:
            radio = ctk.CTkRadioButton(
                parent,
                text=text,
                variable=self.mode_var,
                value=value,
                command=self._on_mode_change
            )
            radio.pack(anchor="w", padx=20, pady=5)
        
        # Custom Settings (initially hidden)
        self.custom_frame = ctk.CTkFrame(parent)
        self.custom_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(
            self.custom_frame,
            text="Custom Einstellungen:",
            font=("Arial", 11, "bold")
        ).pack(anchor="w", pady=5)
        
        # Max Iterations
        iter_frame = ctk.CTkFrame(self.custom_frame)
        iter_frame.pack(fill="x", pady=5)
        
        ctk.CTkLabel(iter_frame, text="Max. Iterationen:").pack(side="left", padx=5)
        self.iter_entry = ctk.CTkEntry(iter_frame, width=100)
        self.iter_entry.insert(0, "10000")
        self.iter_entry.pack(side="right", padx=5)
        
        # Max Time
        time_frame = ctk.CTkFrame(self.custom_frame)
        time_frame.pack(fill="x", pady=5)
        
        ctk.CTkLabel(time_frame, text="Max. Zeit (Sekunden):").pack(side="left", padx=5)
        self.time_entry = ctk.CTkEntry(time_frame, width=100)
        self.time_entry.insert(0, "60")
        self.time_entry.pack(side="right", padx=5)
        
        # Hide custom frame initially
        self.custom_frame.pack_forget()
        
        # Separator
        ctk.CTkFrame(parent, height=2, fg_color="#CCCCCC").pack(fill="x", pady=20)
        
        # Info
        info_text = """
ℹ️ Hinweise:

• Markiere bekannte Zellen
  (Links-Click zum Ändern,
   Rechts-Click zum Sperren)

• Je mehr Zellen bekannt,
  desto schneller & genauer

• Gesperrte Zellen = ⚙️
"""
        
        info_label = ctk.CTkLabel(
            parent,
            text=info_text,
            font=("Arial", 10),
            justify="left"
        )
        info_label.pack(pady=10, padx=10)
    
    def _on_mode_change(self):
        """Wird aufgerufen wenn Modus geändert wird"""
        if self.mode_var.get() == "custom":
            self.custom_frame.pack(fill="x", padx=10, pady=10)
        else:
            self.custom_frame.pack_forget()
    
    def _start_bruteforce(self):
        """Startet den Bruteforce-Prozess"""
        # Validierung
        stats = self.matrix.get_stats()
        
        if stats['unknown_cells'] == 0:
            messagebox.showinfo(
                "Keine unbekannten Zellen",
                "Es gibt keine unbekannten Zellen zum Rekonstruieren!"
            )
            return
        
        if stats['unknown_cells'] > 25:
            result = messagebox.askyesno(
                "Viele unbekannte Zellen",
                f"Du hast {stats['unknown_cells']} unbekannte Zellen.\n"
                f"Das entspricht {2**stats['unknown_cells']:,} Kombinationen!\n\n"
                "Das könnte sehr lange dauern. Fortfahren?"
            )
            if not result:
                return
        
        # Disable Start Button
        self.btn_start.configure(state="disabled", text="⏳ Läuft...")
        
        # Wechsel zu Results View
        self._build_results_view()
        
        # Get Config
        mode = self.mode_var.get()
        max_iter = None
        max_time = None
        
        if mode == "custom":
            try:
                max_iter = int(self.iter_entry.get())
                max_time = float(self.time_entry.get())
            except ValueError:
                messagebox.showerror("Ungültige Eingabe", "Bitte gültige Zahlen eingeben!")
                return
        
        # Starte Bruteforce in Thread
        self.is_running = True
        self.bruteforce_engine = BruteforceEngine(self.matrix, self.validator)
        
        # Callbacks
        self.bruteforce_engine.set_progress_callback(self._on_progress)
        self.bruteforce_engine.set_result_callback(self._on_new_result)
        
        def run_bruteforce():
            results = self.bruteforce_engine.run(
                mode=mode,
                max_iterations=max_iter,
                max_time=max_time,
                parallel=True
            )
            
            # Update UI (in main thread)
            self.after(0, lambda: self._on_bruteforce_complete(results))
        
        self.bruteforce_thread = threading.Thread(target=run_bruteforce, daemon=True)
        self.bruteforce_thread.start()
    
    def _build_results_view(self):
        """Baut die Results-Ansicht"""
        # Clear
        for widget in self.winfo_children():
            widget.destroy()
        
        # Header
        header = ctk.CTkFrame(self)
        header.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(
            header,
            text="🔍 Rekonstruktion läuft...",
            font=("Arial", 20, "bold")
        ).pack(side="left", padx=10)
        
        self.progress_label = ctk.CTkLabel(
            header,
            text="0 / 0 getestet (0 gültig)",
            font=("Arial", 14)
        )
        self.progress_label.pack(side="left", padx=20)
        
        # Stop Button
        self.btn_stop = ctk.CTkButton(
            header,
            text="⏹ Stoppen",
            command=self._stop_bruteforce,
            width=100,
            fg_color="#CC0000",
            hover_color="#AA0000"
        )
        self.btn_stop.pack(side="right", padx=10)
        
        # Progress Bar
        self.progress_bar = ctk.CTkProgressBar(self, mode="indeterminate")
        self.progress_bar.pack(fill="x", padx=10, pady=5)
        self.progress_bar.start()
        
        # Results View
        self.results_view = ResultsView(self)
        self.results_view.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Bottom: Back Button
        bottom = ctk.CTkFrame(self)
        bottom.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkButton(
            bottom,
            text="◀ Zurück zum Editor",
            command=self._back_to_editor,
            width=150
        ).pack(side="left", padx=10)
    
    def _on_progress(self, tested: int, valid: int, total: int):
        """Progress Callback"""
        self.after(0, lambda: self.progress_label.configure(
            text=f"{tested:,} / {total:,} getestet ({valid} gültig)"
        ))
    
    def _on_new_result(self, result):
        """New Result Callback"""
        self.after(0, lambda: self.results_view.add_result(result))
    
    def _on_bruteforce_complete(self, results):
        """Wird aufgerufen wenn Bruteforce fertig ist"""
        self.is_running = False
        
        # Update UI
        self.progress_bar.stop()
        self.progress_bar.pack_forget()
        
        self.btn_stop.configure(state="disabled")
        
        stats = self.bruteforce_engine.get_stats()
        
        messagebox.showinfo(
            "Rekonstruktion abgeschlossen",
            f"Fertig!\n\n"
            f"Getestet: {stats['tested']:,}\n"
            f"Gültige Ergebnisse: {stats['valid']}\n"
            f"Zeit: {stats.get('elapsed', 0):.1f}s"
        )
    
    def _stop_bruteforce(self):
        """Stoppt den laufenden Bruteforce"""
        if self.bruteforce_engine:
            self.bruteforce_engine.stop()
        
        self.btn_stop.configure(state="disabled", text="⏹ Gestoppt")
    
    def _back_to_editor(self):
        """Zurück zum Editor"""
        if self.is_running:
            result = messagebox.askyesno(
                "Bruteforce läuft",
                "Der Bruteforce-Prozess läuft noch. Wirklich abbrechen?"
            )
            if not result:
                return
            
            self._stop_bruteforce()
        
        self._build_editor_view()