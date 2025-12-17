"""
QR-Grid-Editor - Nonogram-Style mit Drag-to-Paint

Features:
- Drag-to-Paint: Halten und ziehen zum Malen
- Weiß/Schwarz Toggle (nicht gelockte = unbekannt)
- Verbessertes visuelles Feedback
"""

import customtkinter as ctk
from typing import Callable, Optional, Set, Tuple
import numpy as np
from ..core.qr_matrix import QRMatrix, CellState


# =============================================================================
# FARBEN
# =============================================================================
class Colors:
    """Farbdefinitionen"""
    BG_PRIMARY = "#0f0f1a"
    BG_SECONDARY = "#1a1a2e"
    BG_CARD = "#252540"
    BG_CARD_HOVER = "#303055"
    
    TEXT_PRIMARY = "#ffffff"
    TEXT_SECONDARY = "#a0a0b0"
    TEXT_MUTED = "#606070"
    
    ACCENT = "#00d4aa"
    ACCENT_SECONDARY = "#6366f1"
    
    # QR Farben
    QR_BLACK = "#1a1a2e"
    QR_WHITE = "#e8e8f0"
    QR_LOCKED_BLACK = "#0a0a15"     # Dunkleres Schwarz für gelockt
    QR_LOCKED_WHITE = "#ffffff"     # Reines Weiß für gelockt
    QR_UNLOCKED_BORDER = "#505070"
    QR_LOCKED_BORDER = "#00d4aa"
    QR_PATTERN_BORDER = "#6366f1"
    QR_HOVER = "#ffd700"
    QR_PAINTING = "#ff6b6b"         # Rot während des Malens
    
    SUCCESS = "#00ff88"
    WARNING = "#ffaa00"
    ERROR = "#ff4466"


class GridEditor(ctk.CTkFrame):
    """
    Nonogram-Style Grid-Editor mit Drag-to-Paint
    
    Logik:
    - Alle Zellen starten als WEISS (nicht gelockt)
    - Links-Klick: Toggle Schwarz/Weiß
    - Rechts-Klick: Toggle Lock (gelockt = bekannt)
    - Drag: Malen in die Richtung des ersten Klicks
    - Unlocked Zellen = Unbekannt für Bruteforce
    """
    
    def __init__(self, parent, matrix: QRMatrix, cell_size: int = 22):
        super().__init__(parent, fg_color="transparent")
        
        self.matrix = matrix
        self.cell_size = cell_size
        
        # Callbacks
        self.on_cell_changed: Optional[Callable] = None
        
        # Drag-Paint State (Links-Klick)
        self.is_dragging = False
        self.drag_value = None  # CellState beim Start des Drags
        self.painted_cells: Set[Tuple[int, int]] = set()
        
        # Drag-Lock State (Rechts-Klick)
        self.is_locking = False
        self.lock_value = None  # True/False beim Start des Lock-Drags
        self.locked_cells: Set[Tuple[int, int]] = set()
        
        # Hover State
        self.hovered_cell = None
        
        # Canvas Container
        canvas_size = matrix.size * cell_size + 4
        
        self.canvas_frame = ctk.CTkFrame(self, fg_color=Colors.BG_SECONDARY, corner_radius=12)
        self.canvas_frame.pack(padx=15, pady=15)
        
        self.canvas = ctk.CTkCanvas(
            self.canvas_frame,
            width=canvas_size,
            height=canvas_size,
            bg=Colors.BG_SECONDARY,
            highlightthickness=0
        )
        self.canvas.pack(padx=10, pady=10)
        
        # Cell tracking
        self.cell_rects = {}
        
        # Events - Links-Klick für Malen
        self.canvas.bind("<Button-1>", self._on_left_down)
        self.canvas.bind("<B1-Motion>", self._on_left_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_left_up)
        
        # Events - Rechts-Klick für Locken
        self.canvas.bind("<Button-3>", self._on_right_down)
        self.canvas.bind("<B3-Motion>", self._on_right_drag)
        self.canvas.bind("<ButtonRelease-3>", self._on_right_up)
        
        # Hover
        self.canvas.bind("<Motion>", self._on_motion)
        self.canvas.bind("<Leave>", self._on_leave)
        
        # Initial Render
        self._init_cells_white()
        self.render()
    
    def _init_cells_white(self):
        """Initialisiert alle nicht-festen Zellen auf Weiß"""
        for i in range(self.matrix.size):
            for j in range(self.matrix.size):
                if not self.matrix.locked[i, j]:
                    self.matrix.grid[i, j] = CellState.WHITE
    
    def render(self):
        """Rendert das Grid"""
        self.canvas.delete("all")
        self.cell_rects.clear()
        
        for i in range(self.matrix.size):
            for j in range(self.matrix.size):
                self._draw_cell(i, j)
        
        self._draw_grid_lines()
    
    def _draw_cell(self, row: int, col: int, is_hovered: bool = False, is_painting: bool = False):
        """Zeichnet eine Zelle"""
        self.canvas.delete(f"cell_{row}_{col}")
        self.canvas.delete(f"marker_{row}_{col}")
        
        x1 = col * self.cell_size + 2
        y1 = row * self.cell_size + 2
        x2 = x1 + self.cell_size - 2
        y2 = y1 + self.cell_size - 2
        
        value, is_locked = self.matrix.get_cell(row, col)
        is_fixed = self.matrix._is_fixed_pattern(row, col)
        
        # Füllfarbe
        if is_locked or is_fixed:
            fill = Colors.QR_LOCKED_BLACK if value == CellState.BLACK else Colors.QR_LOCKED_WHITE
        else:
            fill = Colors.QR_BLACK if value == CellState.BLACK else Colors.QR_WHITE
        
        # Border
        if is_painting:
            border = Colors.QR_PAINTING
            border_width = 3
        elif is_hovered:
            border = Colors.QR_HOVER
            border_width = 3
        elif is_fixed:
            border = Colors.QR_PATTERN_BORDER
            border_width = 2
        elif is_locked:
            border = Colors.QR_LOCKED_BORDER
            border_width = 2
        else:
            border = Colors.QR_UNLOCKED_BORDER
            border_width = 1
        
        rect_id = self.canvas.create_rectangle(
            x1, y1, x2, y2,
            fill=fill,
            outline=border,
            width=border_width,
            tags=f"cell_{row}_{col}"
        )
        self.cell_rects[(row, col)] = rect_id
        
        # Marker
        if self.cell_size >= 16:
            if is_fixed:
                text_color = Colors.QR_WHITE if value == CellState.BLACK else Colors.QR_PATTERN_BORDER
                self.canvas.create_text(
                    (x1 + x2) // 2, (y1 + y2) // 2,
                    text="◆", fill=text_color,
                    font=("Segoe UI", max(7, self.cell_size // 4)),
                    tags=f"marker_{row}_{col}"
                )
            elif is_locked:
                text_color = Colors.QR_WHITE if value == CellState.BLACK else Colors.ACCENT
                self.canvas.create_text(
                    (x1 + x2) // 2, (y1 + y2) // 2,
                    text="✓", fill=text_color,
                    font=("Segoe UI", max(8, self.cell_size // 3)),
                    tags=f"marker_{row}_{col}"
                )
    
    def _draw_grid_lines(self):
        """Grid-Linien"""
        size = self.matrix.size * self.cell_size + 2
        
        # Linien alle 7 Zellen
        for i in range(0, self.matrix.size + 1, 7):
            pos = i * self.cell_size + 2
            if pos < size:
                self.canvas.create_line(pos, 0, pos, size, fill=Colors.ACCENT_SECONDARY, width=1, tags="grid")
                self.canvas.create_line(0, pos, size, pos, fill=Colors.ACCENT_SECONDARY, width=1, tags="grid")
    
    def _get_cell(self, x: int, y: int) -> Optional[Tuple[int, int]]:
        """Position zu Zelle"""
        col = (x - 2) // self.cell_size
        row = (y - 2) // self.cell_size
        if 0 <= row < self.matrix.size and 0 <= col < self.matrix.size:
            return (row, col)
        return None
    
    def _on_left_down(self, event):
        """Start Drag-Paint"""
        cell = self._get_cell(event.x, event.y)
        if not cell:
            return
        
        row, col = cell
        if self.matrix.locked[row, col] or self.matrix._is_fixed_pattern(row, col):
            return
        
        # Toggle und merke den neuen Wert
        current = self.matrix.grid[row, col]
        new_value = CellState.BLACK if current == CellState.WHITE else CellState.WHITE
        
        self.matrix.grid[row, col] = new_value
        self.drag_value = new_value
        self.is_dragging = True
        self.painted_cells = {cell}
        
        self._draw_cell(row, col, is_painting=True)
        self._notify_change()
    
    def _on_left_drag(self, event):
        """Drag-Paint fortsetzen"""
        if not self.is_dragging:
            return
        
        cell = self._get_cell(event.x, event.y)
        if not cell or cell in self.painted_cells:
            return
        
        row, col = cell
        if self.matrix.locked[row, col] or self.matrix._is_fixed_pattern(row, col):
            return
        
        # Male mit dem gleichen Wert wie beim Start
        self.matrix.grid[row, col] = self.drag_value
        self.painted_cells.add(cell)
        
        self._draw_cell(row, col, is_painting=True)
        self._notify_change()
    
    def _on_left_up(self, event):
        """Drag beenden"""
        if self.is_dragging:
            # Redraw all painted cells without painting highlight
            for row, col in self.painted_cells:
                self._draw_cell(row, col)
            
            self.is_dragging = False
            self.drag_value = None
            self.painted_cells.clear()
    
    def _on_right_down(self, event):
        """Start Drag-Lock"""
        cell = self._get_cell(event.x, event.y)
        if not cell:
            return
        
        row, col = cell
        if self.matrix._is_fixed_pattern(row, col):
            return
        
        # Toggle und merke den neuen Lock-Status
        current_locked = self.matrix.locked[row, col]
        new_locked = not current_locked
        
        self.matrix.locked[row, col] = new_locked
        self.lock_value = new_locked  # Merke ob wir locken oder unlocken
        self.is_locking = True
        self.locked_cells = {cell}
        
        self._draw_cell(row, col, is_painting=True)
        self._notify_change()
    
    def _on_right_drag(self, event):
        """Drag-Lock fortsetzen"""
        if not self.is_locking:
            return
        
        cell = self._get_cell(event.x, event.y)
        if not cell or cell in self.locked_cells:
            return
        
        row, col = cell
        if self.matrix._is_fixed_pattern(row, col):
            return
        
        # Lock/Unlock mit dem gleichen Status wie beim Start
        self.matrix.locked[row, col] = self.lock_value
        self.locked_cells.add(cell)
        
        self._draw_cell(row, col, is_painting=True)
        self._notify_change()
    
    def _on_right_up(self, event):
        """Lock-Drag beenden"""
        if self.is_locking:
            # Redraw all locked cells
            for row, col in self.locked_cells:
                self._draw_cell(row, col)
            
            self.is_locking = False
            self.lock_value = None
            self.locked_cells.clear()
    
    def _on_motion(self, event):
        """Hover"""
        if self.is_dragging:
            return
        
        cell = self._get_cell(event.x, event.y)
        
        if cell != self.hovered_cell:
            if self.hovered_cell:
                r, c = self.hovered_cell
                self._draw_cell(r, c)
            
            if cell:
                r, c = cell
                self._draw_cell(r, c, is_hovered=True)
            
            self.hovered_cell = cell
    
    def _on_leave(self, event):
        """Mouse leaves"""
        if self.hovered_cell:
            r, c = self.hovered_cell
            self._draw_cell(r, c)
        self.hovered_cell = None
    
    def _notify_change(self):
        """Callback aufrufen"""
        if self.on_cell_changed:
            self.on_cell_changed(0, 0)  # Generische Benachrichtigung
    
    def get_matrix(self) -> QRMatrix:
        return self.matrix
    
    def set_cell_size(self, size: int):
        self.cell_size = size
        canvas_size = self.matrix.size * size + 4
        self.canvas.config(width=canvas_size, height=canvas_size)
        self.render()


class StatisticsPanel(ctk.CTkFrame):
    """
    Statistik-Panel mit detaillierten Informationen
    """
    
    def __init__(self, parent, matrix: QRMatrix):
        super().__init__(parent, fg_color=Colors.BG_SECONDARY, corner_radius=12)
        
        self.matrix = matrix
        
        # Title
        ctk.CTkLabel(
            self, text="📊 Statistiken",
            font=("Segoe UI", 16, "bold"),
            text_color=Colors.TEXT_PRIMARY
        ).pack(pady=(15, 10), padx=15, anchor="w")
        
        # Stats Container
        self.stats_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.stats_frame.pack(fill="x", padx=15, pady=(0, 15))
        
        # Labels
        self.labels = {}
        stats_items = [
            ("total", "Gesamt"),
            ("locked", "Bekannt (gelockt)"),
            ("unknown", "Unbekannt"),
            ("combinations", "Kombinationen"),
            ("est_time", "Geschätzte Zeit"),
        ]
        
        for key, label in stats_items:
            row = ctk.CTkFrame(self.stats_frame, fg_color="transparent")
            row.pack(fill="x", pady=3)
            
            ctk.CTkLabel(
                row, text=f"{label}:",
                font=("Segoe UI", 12),
                text_color=Colors.TEXT_MUTED,
                width=140
            ).pack(side="left")
            
            val_label = ctk.CTkLabel(
                row, text="-",
                font=("Consolas", 12, "bold"),
                text_color=Colors.TEXT_PRIMARY
            )
            val_label.pack(side="left")
            self.labels[key] = val_label
        
        self.update()
    
    def update(self):
        """Aktualisiert die Statistiken"""
        total = self.matrix.size * self.matrix.size
        locked = int(np.sum(self.matrix.locked))
        unknown = total - locked
        
        # Kombinationen (exakt)
        if unknown <= 63:
            combinations = 2 ** unknown
            combo_str = f"{combinations:,}"
        else:
            # Sehr große Zahl - wissenschaftliche Notation
            exp = unknown
            combo_str = f"2^{unknown} ≈ 10^{int(unknown * 0.301)}"
        
        # Geschätzte Zeit (bei ~200 Tests/Sekunde)
        if unknown <= 63:
            tests_per_sec = 200
            seconds = combinations / tests_per_sec
            
            if seconds < 1:
                time_str = "< 1 Sekunde"
            elif seconds < 60:
                time_str = f"~{seconds:.0f} Sekunden"
            elif seconds < 3600:
                time_str = f"~{seconds/60:.0f} Minuten"
            elif seconds < 86400:
                time_str = f"~{seconds/3600:.1f} Stunden"
            elif seconds < 86400 * 365:
                time_str = f"~{seconds/86400:.0f} Tage"
            elif seconds < 86400 * 365 * 1000:
                time_str = f"~{seconds/(86400*365):.0f} Jahre"
            else:
                time_str = "∞ (zu viele)"
        else:
            time_str = "∞ (zu viele)"
        
        self.labels["total"].configure(text=f"{total}")
        self.labels["locked"].configure(text=f"{locked}")
        self.labels["unknown"].configure(text=f"{unknown}")
        self.labels["combinations"].configure(text=combo_str)
        self.labels["est_time"].configure(text=time_str)


class GridEditorControls(ctk.CTkFrame):
    """
    Vereinfachte Controls mit Statistik-Panel
    """
    
    def __init__(self, parent, editor: GridEditor):
        super().__init__(parent, fg_color="transparent")
        
        self.editor = editor
        
        # Grid Layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        
        # Left: Statistics
        self.stats_panel = StatisticsPanel(self, editor.matrix)
        self.stats_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 5), pady=5)
        
        # Right: Controls
        controls = ctk.CTkFrame(self, fg_color=Colors.BG_SECONDARY, corner_radius=12)
        controls.grid(row=0, column=1, sticky="nsew", padx=(5, 0), pady=5)
        
        ctk.CTkLabel(
            controls, text="🎮 Steuerung",
            font=("Segoe UI", 16, "bold"),
            text_color=Colors.TEXT_PRIMARY
        ).pack(pady=(15, 10), padx=15, anchor="w")
        
        legend = [
            ("Links-Klick + Drag", "Malen (Schwarz/Weiß)"),
            ("Rechts-Klick", "Locken/Unlocken"),
            ("◆", "Festes QR-Muster"),
            ("✓", "Bekanntes Feld (gelockt)"),
        ]
        
        for sym, desc in legend:
            row = ctk.CTkFrame(controls, fg_color="transparent")
            row.pack(fill="x", padx=15, pady=2)
            ctk.CTkLabel(row, text=sym, font=("Segoe UI", 11, "bold"), text_color=Colors.ACCENT, width=130).pack(side="left")
            ctk.CTkLabel(row, text=desc, font=("Segoe UI", 11), text_color=Colors.TEXT_MUTED).pack(side="left")
        
        # Buttons
        btn_frame = ctk.CTkFrame(controls, fg_color="transparent")
        btn_frame.pack(fill="x", pady=15, padx=15)
        
        ctk.CTkButton(
            btn_frame, text="🔄 Reset",
            command=self._reset,
            width=90, height=36,
            font=("Segoe UI", 12),
            fg_color=Colors.BG_CARD,
            hover_color=Colors.BG_CARD_HOVER,
            corner_radius=18
        ).pack(side="left", padx=3)
        
        ctk.CTkButton(
            btn_frame, text="⬜ Alle Weiß",
            command=self._all_white,
            width=100, height=36,
            font=("Segoe UI", 12),
            fg_color=Colors.BG_CARD,
            hover_color=Colors.BG_CARD_HOVER,
            corner_radius=18
        ).pack(side="left", padx=3)
        
        ctk.CTkButton(
            btn_frame, text="🔓 Unlock All",
            command=self._unlock_all,
            width=110, height=36,
            font=("Segoe UI", 12),
            fg_color=Colors.BG_CARD,
            hover_color=Colors.BG_CARD_HOVER,
            corner_radius=18
        ).pack(side="left", padx=3)
    
    def update_stats(self):
        """Update statistics"""
        self.stats_panel.update()
    
    def _reset(self):
        self.editor.matrix.reset()
        self.editor._init_cells_white()
        self.editor.render()
        self.update_stats()
    
    def _all_white(self):
        for i in range(self.editor.matrix.size):
            for j in range(self.editor.matrix.size):
                if not self.editor.matrix.locked[i, j]:
                    self.editor.matrix.grid[i, j] = CellState.WHITE
        self.editor.render()
        self.update_stats()
    
    def _unlock_all(self):
        for i in range(self.editor.matrix.size):
            for j in range(self.editor.matrix.size):
                if not self.editor.matrix._is_fixed_pattern(i, j):
                    self.editor.matrix.locked[i, j] = False
        self.editor.render()
        self.update_stats()