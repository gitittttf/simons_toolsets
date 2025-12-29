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
import sys
from typing import Optional
from .grid_editor import GridEditor
from .results_view import ResultsView
from ..core.qr_matrix import QRMatrix, QR_VERSIONS, get_version_for_size
from ..core.bruteforce import BruteforceEngine
from ..core.validator import QRValidator


from .theme import Colors, Fonts, Dimensions
def setup_theme():
    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("blue")

# =============================================================================
# HAUPTFENSTER
# =============================================================================
# =============================================================================
# HAUPTFENSTER
# =============================================================================
class MainWindowMixin:
    """Shared implementation for both Standalone (CTk) and Hub-Tool (CTkToplevel)"""
    
    def _init_shared(self, is_standalone=True):
        self.is_standalone = is_standalone
        self.protocol("WM_DELETE_WINDOW", self._on_close)



class MainWindow(ctk.CTk, MainWindowMixin):
    """Standalone Root Window"""
    def __init__(self, is_standalone=True):
        super().__init__()
        self._init_shared(is_standalone=True)

class MainWindowToplevel(ctk.CTkToplevel, MainWindowMixin):
    """Child Window for Hub"""
    def __init__(self):
        super().__init__()
        self._init_shared(is_standalone=False)
        # Toplevel specifics
        self.after(200, lambda: self.focus())

        setup_theme()
        
        self.title("✨ QR-Code Rekonstruktion ✨")
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

    def _on_close(self):
        """Clean exit handler"""
        if self.is_running and self.bruteforce_engine:
            self.bruteforce_engine.stop()
        
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

    # ... (Theme code skipped) ...

    def _on_progress(self, tested, valid, total):
        # FIX: Ensure main thread update
        # Using separate thread for callbacks might be risky.
        try:
            # Check if window still exists
            if not self.winfo_exists(): return 
            
            # Schedule update
            self.after(10, lambda t=tested, v=valid, tot=total: self._update_progress_ui(t, v, tot))
        except:
            pass

    def _update_progress_ui(self, tested, valid, total):
        try:
            self.progress_label.configure(text=f"{tested:,} / {total:,} ({valid} gültig)")
        except:
            pass
    
    def _on_result(self, result):
        try:
            if not self.winfo_exists(): return
            self.after(10, lambda r=result: self.results_view.add_result(r))
        except:
            pass
    
    def _on_complete(self, results):
        self.is_running = False
        try:
            self.progress_bar.stop()
            self.progress_bar.pack_forget()
            self.btn_stop.configure(state="normal", text="✓ Fertig", command=self._back, fg_color=Colors.SUCCESS, text_color="#ffffff", hover_color="#2e8b57")
            
            stats = self.bruteforce_engine.get_stats()
            # Only show messagebox if window is focused/active
            messagebox.showinfo("Fertig", f"Tests: {stats['tested']:,}\nGültig: {stats['valid']}\nZeit: {stats.get('elapsed', 0):.1f}s", parent=self)
        except:
            pass

    # ... (Rest of code) ...
    

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
        self._build_editor_view()
    
    def _build_editor_view(self):
        """Editor View mit neuem Sidebar-Layout"""
        for widget in self.winfo_children():
            widget.destroy()
        
        main = ctk.CTkFrame(self, fg_color="#333333", corner_radius=Dimensions.CORNER_RADIUS_NONE)
        main.pack(fill="both", expand=True)
        
        # 1. Canvas Area (Left/Center) - Takes available space
        canvas_container = ctk.CTkFrame(main, fg_color="#333333", corner_radius=Dimensions.CORNER_RADIUS_NONE)
        canvas_container.pack(fill="both", expand=True, side="left")
        
        self.grid_editor = GridEditor(canvas_container, self.matrix)
        self.grid_editor.pack(fill="both", expand=True)
        
        def on_change(r, c):
            self._update_stats_sidebar()
        self.grid_editor.on_cell_changed = on_change
        
        # 2. Sidebar (Right) - Fixed width
        sidebar = ctk.CTkFrame(main, fg_color=Colors.BG_CARD, width=320, corner_radius=Dimensions.CORNER_RADIUS_NONE)
        sidebar.pack(fill="y", side="right")
        sidebar.pack_propagate(False) # Fixed width
        
        # Sidebar Content
        ctk.CTkLabel(sidebar, text="QR Rekonstruktion", font=Fonts.HEADING, text_color=Colors.TEXT_PRIMARY).pack(pady=(20, 5), padx=20, anchor="w")
        ctk.CTkLabel(sidebar, text=f"Version {self.matrix.size}x{self.matrix.size}", font=Fonts.BODY, text_color=Colors.TEXT_MUTED).pack(pady=(0, 20), padx=20, anchor="w")
        
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
        
        items = ["Unbekannt", "Kombinationen", "Zeit"]
        for item in items:
            row = ctk.CTkFrame(stats_frame, fg_color="transparent")
            row.pack(fill="x", pady=2)
            ctk.CTkLabel(row, text=item, font=Fonts.SMALL, text_color=Colors.TEXT_MUTED).pack(side="left")
            lbl = ctk.CTkLabel(row, text="-", font=Fonts.BODY_BOLD, text_color=Colors.TEXT_PRIMARY)
            lbl.pack(side="right")
            self.stats_labels[item] = lbl

    def _build_sidebar_controls(self, parent):
        ctk.CTkLabel(parent, text="Werkzeuge", font=Fonts.SUBHEADING, text_color=Colors.TEXT_PRIMARY).pack(padx=20, anchor="w", pady=(0, 10))
        
        # Buttons Grid
        btn_grid = ctk.CTkFrame(parent, fg_color="transparent")
        btn_grid.pack(fill="x", padx=15)
        
        def reset():
            self.matrix.reset()
            self.grid_editor._init_cells_white()
            self.grid_editor.render()
            self._update_stats_sidebar()
            
        def all_white():
            import numpy as np
            from ..core.qr_matrix import CellState
            # Set unlocked to white
            mask = ~self.matrix.locked
            self.matrix.grid[mask] = CellState.WHITE
            self.grid_editor.render()
            self._update_stats_sidebar()
            
        def unlock_all():
            # Unlock un-fixed
            for r in range(self.matrix.size):
                for c in range(self.matrix.size):
                    if not self.matrix._is_fixed_pattern(r, c):
                        self.matrix.locked[r, c] = False
            self.grid_editor.render()
            self._update_stats_sidebar()
            
        btns = [("Reset", reset), ("Alles Weiß", all_white), ("Unlock All", unlock_all)]
        for txt, cmd in btns:
            ctk.CTkButton(
                btn_grid, text=txt, command=cmd,
                height=32, font=Fonts.BODY,
                fg_color=Colors.BG_PRIMARY, text_color=Colors.TEXT_PRIMARY,
                hover_color=Colors.BG_CARD_HOVER, border_width=0
            ).pack(fill="x", pady=4)
        
        # Hints
        ctk.CTkLabel(parent, text="Steuerung:", font=Fonts.SMALL, text_color=Colors.TEXT_MUTED).pack(padx=20, anchor="w", pady=(20, 5))
        hints = ["Linksklick: Malen", "Rechtsklick: Sperren", "Scroll: Zoom", "Ctrl+Klick: Bewegen"]
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
        self.mode_desc = ctk.CTkLabel(parent, text="Schnelltest (1k Versuche, 30s)", font=Fonts.SMALL, text_color=Colors.TEXT_MUTED, wraplength=280, justify="left")
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
            self.mode_desc.configure(text="Schnelltest für kleine Fehler.\nMax 1.000 Versuche oder 30s.")
            self.custom_inputs.pack_forget()
        elif choice == "accurate":
            self.mode_desc.configure(text="Tiefensuche für bis zu ~15 fehlende Pixel.\nMax 50.000 Versuche oder 120s.")
            self.custom_inputs.pack_forget()
        elif choice == "custom":
            self.mode_desc.configure(text="Benutzerdefinierte Limits.\nLeerlassen = Keine Grenze.")
            self.custom_inputs.pack(padx=20, pady=10, fill="x")


    def _update_stats_sidebar(self):
        if not hasattr(self, 'stats_labels'): return
        
        import numpy as np
        total = self.matrix.size * self.matrix.size
        locked = int(np.sum(self.matrix.locked))
        unknown = total - locked
        
        self.stats_labels["Unbekannt"].configure(text=str(unknown))
        
        if unknown <= 63:
            combos = f"2^{unknown}" if unknown > 20 else f"{2**unknown:,}"
        else:
            combos = f"2^{unknown}"
        self.stats_labels["Kombinationen"].configure(text=combos)
        
        # Est Time
        if unknown > 25:
             t = "∞"
        elif unknown == 0:
             t = "0s"
        else:
             # Rough est
             tests = 2**unknown
             secs = tests / 2000 # Assume 2k/sec
             if secs < 60: t = f"{secs:.1f}s"
             elif secs < 3600: t = f"{secs/60:.1f}m"
             else: t = f"{secs/3600:.1f}h"
             
        self.stats_labels["Zeit"].configure(text=t)

    # _build_config and _build_action_bar are replaced by sidebar methods
    # We remove them implicitly by overwriting _build_editor_view which called them.
    # But we need to make sure _start_bruteforce still works (it uses self.iter_entry which is gone).
    # We simplified mode selection to just Dropdown.
    # We need to update _start_bruteforce to not crash on missing widgets.

    
    def _build_action_bar(self, parent):
        """Action Bar"""
        bar = ctk.CTkFrame(parent, fg_color=Colors.BG_SECONDARY, height=70, corner_radius=Dimensions.CORNER_RADIUS_NONE)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)
        
        # Top border shadow
        ctk.CTkFrame(bar, fg_color=Colors.BORDER, height=1).pack(fill="x", side="top")
        
        # Start Button
        self.btn_start = ctk.CTkButton(
            bar,
            text="✨ Rekonstruktion starten",
            command=self._start_bruteforce,
            width=240,
            height=40,
            font=Fonts.BUTTON_LARGE,
            fg_color=Colors.ACCENT,
            text_color="#ffffff",
            hover_color=Colors.ACCENT_HOVER,
            corner_radius=Dimensions.CORNER_RADIUS_L
        )
        self.btn_start.pack(side="right", padx=20, pady=15)
        
        # Quick Stats
        self.quick_stats = ctk.CTkLabel(bar, text="", font=Fonts.BODY, text_color=Colors.TEXT_PRIMARY)
        self.quick_stats.pack(side="left", padx=30, pady=15)
        self._update_quick_stats()
    
    def _update_quick_stats(self):
        if self.matrix and hasattr(self, 'quick_stats'):
            stats = self.matrix.get_stats()
            self.quick_stats.configure(text=f"📊 Version {stats['version']}  •  {stats['unknown_cells']} Unbekannte Zellen")
            
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
        
        if hasattr(self, 'btn_start'):
            self.btn_start.configure(state="disabled", text="⏳ Arbeite...")
            
        self._build_results_view()
        
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
        
        self.is_running = True
        self.bruteforce_engine = BruteforceEngine(self.matrix, self.validator)
        
        # --- THREAD SAFETY FIX ---
        import queue
        self.msg_queue = queue.Queue()
        
        def on_progress(p, v, m): # Args: tested, valid, max
            self.msg_queue.put(("progress", (p, v, m)))
            
        def on_result(r):
            self.msg_queue.put(("result", r))
            
        self.bruteforce_engine.set_progress_callback(on_progress)
        self.bruteforce_engine.set_result_callback(on_result)
        
        def run():
            results = self.bruteforce_engine.run(mode=mode, max_iterations=max_iter, max_time=max_time, parallel=True)
            self.msg_queue.put(("complete", results))
        
        self.bruteforce_thread = threading.Thread(target=run, daemon=True)
        self.bruteforce_thread.start()
        
        # Start Polling
        self._check_queue()

    def _check_queue(self):
        """Polls the queue for messages from the worker thread"""
        if not self.winfo_exists():
            return
            
        try:
            import queue
            while True:
                msg = self.msg_queue.get_nowait()
                m_type, data = msg
                
                if m_type == "progress":
                    # data is (tested, valid, max)
                    # We can update the UI here if we have a progress callback target
                    # But the previous implementation called self._on_progress
                    # Let's adapt it.
                    pass 
                elif m_type == "result":
                    self._on_result(data)
                elif m_type == "complete":
                    self._on_complete(data)
                    return # Stop polling
                    
        except queue.Empty:
            pass
            
        if self.is_running:
            self.after(50, self._check_queue)


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
        
        ctk.CTkLabel(header, text="✨ Rekonstruktion läuft...", font=Fonts.HEADING, text_color=Colors.TEXT_PRIMARY).pack(side="left", padx=20, pady=10)
        
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
        
        self.results_view = ResultsView(main)
        self.results_view.pack(fill="both", expand=True, padx=20, pady=20)
        
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
    
    def _on_progress(self, tested, valid, total):
        # FIX: Ensure main thread update
        try:
            if not self.winfo_exists(): return 
            self.after(10, lambda t=tested, v=valid, tot=total: self._update_progress_ui(t, v, tot))
        except:
            pass

    def _update_progress_ui(self, tested, valid, total):
        try:
            self.progress_label.configure(text=f"{tested:,} / {total:,} ({valid} gültig)")
        except:
            pass
    
    def _on_result(self, result):
        try:
            if not self.winfo_exists(): return
            self.after(10, lambda r=result: self.results_view.add_result(r))
        except:
            pass
    
    def _on_complete(self, results):
        self.is_running = False
        self.progress_bar.stop()
        self.progress_bar.pack_forget()
        self.btn_stop.configure(state="normal", text="✓ Fertig", command=self._back, fg_color=Colors.SUCCESS, text_color="#ffffff", hover_color="#2e8b57")
        
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