"""
QR-Grid-Editor - Nonogram-Style Interface
Ermöglicht das interaktive Bearbeiten von QR-Code-Zellen
"""

import customtkinter as ctk
from typing import Callable, Optional
import numpy as np
from ..core.qr_matrix import QRMatrix, CellState


class GridEditor(ctk.CTkFrame):
    """
    Interaktiver Grid-Editor für QR-Codes
    
    Features:
    - Click zum Ändern von Zellen (UNKNOWN -> BLACK -> WHITE -> UNKNOWN)
    - Visuell unterscheidbar: Locked vs. Unlocked
    - Hover-Effekt
    - Zoom/Scale-Unterstützung
    """
    
    # Farben
    COLOR_BLACK = "#000000"
    COLOR_WHITE = "#FFFFFF"
    COLOR_UNKNOWN = "#CCCCCC"
    COLOR_LOCKED_BORDER = "#0066CC"
    COLOR_UNLOCKED_BORDER = "#999999"
    COLOR_HOVER = "#FFFF00"
    COLOR_GRID_LINE = "#DDDDDD"
    
    def __init__(self, parent, matrix: QRMatrix, cell_size: int = 20):
        """
        Initialisiert den Grid-Editor
        
        Args:
            parent: Parent Widget
            matrix: QRMatrix Instanz
            cell_size: Größe einer Zelle in Pixeln
        """
        super().__init__(parent)
        
        self.matrix = matrix
        self.cell_size = cell_size
        
        # Callbacks
        self.on_cell_changed: Optional[Callable] = None
        
        # Canvas erstellen
        canvas_size = matrix.size * cell_size
        self.canvas = ctk.CTkCanvas(
            self,
            width=canvas_size,
            height=canvas_size,
            bg="white",
            highlightthickness=1,
            highlightbackground=self.COLOR_GRID_LINE
        )
        self.canvas.pack(padx=10, pady=10)
        
        # Cell-Tracking für Hover/Click
        self.cell_rects = {}  # (row, col) -> rectangle_id
        self.hovered_cell = None
        
        # Event-Bindings
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<Button-3>", self._on_right_click)
        self.canvas.bind("<Motion>", self._on_motion)
        
        # Initial Render
        self.render()
    
    def render(self):
        """Rendert das komplette Grid"""
        self.canvas.delete("all")
        self.cell_rects.clear()
        
        for i in range(self.matrix.size):
            for j in range(self.matrix.size):
                self._draw_cell(i, j)
        
        # Zeichne Grid-Linien
        self._draw_grid_lines()
    
    def _draw_cell(self, row: int, col: int):
        """Zeichnet eine einzelne Zelle"""
        x1 = col * self.cell_size
        y1 = row * self.cell_size
        x2 = x1 + self.cell_size
        y2 = y1 + self.cell_size
        
        value, is_locked = self.matrix.get_cell(row, col)
        
        # Bestimme Füllfarbe
        if value == CellState.BLACK:
            fill = self.COLOR_BLACK
        elif value == CellState.WHITE:
            fill = self.COLOR_WHITE
        else:  # UNKNOWN
            fill = self.COLOR_UNKNOWN
        
        # Bestimme Border-Farbe
        border = self.COLOR_LOCKED_BORDER if is_locked else self.COLOR_UNLOCKED_BORDER
        border_width = 2 if is_locked else 1
        
        # Zeichne Rechteck
        rect_id = self.canvas.create_rectangle(
            x1, y1, x2, y2,
            fill=fill,
            outline=border,
            width=border_width,
            tags=f"cell_{row}_{col}"
        )
        
        self.cell_rects[(row, col)] = rect_id
        
        # Zusätzliche Markierung für gesperrte feste Pattern
        if is_locked and self.matrix._is_fixed_pattern(row, col):
            # Kleines "L" für Locked-Fixed
            self.canvas.create_text(
                x1 + self.cell_size // 2,
                y1 + self.cell_size // 2,
                text="⚙",
                fill="#0066CC" if value == CellState.WHITE else "#FFFFFF",
                font=("Arial", max(8, self.cell_size // 3)),
                tags=f"lock_{row}_{col}"
            )
    
    def _draw_grid_lines(self):
        """Zeichnet Grid-Linien"""
        canvas_size = self.matrix.size * self.cell_size
        
        # Vertikale Linien
        for i in range(self.matrix.size + 1):
            x = i * self.cell_size
            self.canvas.create_line(
                x, 0, x, canvas_size,
                fill=self.COLOR_GRID_LINE,
                width=1
            )
        
        # Horizontale Linien
        for i in range(self.matrix.size + 1):
            y = i * self.cell_size
            self.canvas.create_line(
                0, y, canvas_size, y,
                fill=self.COLOR_GRID_LINE,
                width=1
            )
        
        # Dickere Linien alle 5 Zellen (für Orientierung)
        for i in range(0, self.matrix.size + 1, 5):
            x = i * self.cell_size
            y = i * self.cell_size
            self.canvas.create_line(x, 0, x, canvas_size, fill="#888888", width=2)
            self.canvas.create_line(0, y, canvas_size, y, fill="#888888", width=2)
    
    def _get_cell_from_pos(self, x: int, y: int) -> Optional[tuple]:
        """Konvertiert Canvas-Position zu (row, col)"""
        col = x // self.cell_size
        row = y // self.cell_size
        
        if 0 <= row < self.matrix.size and 0 <= col < self.matrix.size:
            return (row, col)
        return None
    
    def _on_click(self, event):
        """Left-Click: Toggle Cell Value"""
        cell = self._get_cell_from_pos(event.x, event.y)
        if not cell:
            return
        
        row, col = cell
        _, is_locked = self.matrix.get_cell(row, col)
        
        # Nur unlocked Zellen können geändert werden
        if not is_locked:
            self.matrix.toggle_cell(row, col)
            self._draw_cell(row, col)
            
            if self.on_cell_changed:
                self.on_cell_changed(row, col)
    
    def _on_right_click(self, event):
        """Right-Click: Lock/Unlock Cell"""
        cell = self._get_cell_from_pos(event.x, event.y)
        if not cell:
            return
        
        row, col = cell
        value, is_locked = self.matrix.get_cell(row, col)
        
        # Toggle Lock (nur wenn nicht fixed pattern)
        if not self.matrix._is_fixed_pattern(row, col):
            if is_locked:
                self.matrix.unlock_cell(row, col)
            else:
                if value != CellState.UNKNOWN:
                    self.matrix.lock_cell(row, col)
            
            self._draw_cell(row, col)
            
            if self.on_cell_changed:
                self.on_cell_changed(row, col)
    
    def _on_motion(self, event):
        """Hover-Effekt"""
        cell = self._get_cell_from_pos(event.x, event.y)
        
        if cell != self.hovered_cell:
            # Remove old hover
            if self.hovered_cell and self.hovered_cell in self.cell_rects:
                row, col = self.hovered_cell
                self._draw_cell(row, col)
            
            # Add new hover
            if cell and cell in self.cell_rects:
                rect_id = self.cell_rects[cell]
                self.canvas.itemconfig(rect_id, outline=self.COLOR_HOVER, width=3)
            
            self.hovered_cell = cell
    
    def update_cell(self, row: int, col: int):
        """Aktualisiert eine einzelne Zelle (von außen)"""
        self._draw_cell(row, col)
    
    def get_matrix(self) -> QRMatrix:
        """Gibt die aktuelle Matrix zurück"""
        return self.matrix
    
    def set_cell_size(self, size: int):
        """Ändert die Zellgröße und rendert neu"""
        self.cell_size = size
        canvas_size = self.matrix.size * size
        self.canvas.config(width=canvas_size, height=canvas_size)
        self.render()


class GridEditorControls(ctk.CTkFrame):
    """
    Control-Panel für den Grid-Editor
    """
    
    def __init__(self, parent, editor: GridEditor):
        super().__init__(parent)
        
        self.editor = editor
        
        # Header
        title = ctk.CTkLabel(
            self,
            text="Grid-Editor",
            font=("Arial", 16, "bold")
        )
        title.pack(pady=(10, 5))
        
        # Statistiken
        self.stats_label = ctk.CTkLabel(
            self,
            text="",
            font=("Arial", 12)
        )
        self.stats_label.pack(pady=5)
        
        # Separator
        ctk.CTkFrame(self, height=2, fg_color="#CCCCCC").pack(fill="x", pady=10)
        
        # Buttons
        btn_frame = ctk.CTkFrame(self)
        btn_frame.pack(pady=5, fill="x", padx=10)
        
        self.btn_reset = ctk.CTkButton(
            btn_frame,
            text="🔄 Reset",
            command=self._on_reset,
            width=100
        )
        self.btn_reset.pack(pady=5, fill="x")
        
        self.btn_clear_unlocked = ctk.CTkButton(
            btn_frame,
            text="🗑️ Clear Unlocked",
            command=self._on_clear_unlocked,
            width=100
        )
        self.btn_clear_unlocked.pack(pady=5, fill="x")
        
        # Separator
        ctk.CTkFrame(self, height=2, fg_color="#CCCCCC").pack(fill="x", pady=10)
        
        # Legende
        legend_frame = ctk.CTkFrame(self)
        legend_frame.pack(pady=5, fill="x", padx=10)
        
        ctk.CTkLabel(
            legend_frame,
            text="Steuerung:",
            font=("Arial", 12, "bold")
        ).pack(anchor="w", pady=(5, 2))
        
        ctk.CTkLabel(
            legend_frame,
            text="• Links-Click: Zelle ändern",
            font=("Arial", 10)
        ).pack(anchor="w", padx=10)
        
        ctk.CTkLabel(
            legend_frame,
            text="• Rechts-Click: Lock/Unlock",
            font=("Arial", 10)
        ).pack(anchor="w", padx=10)
        
        ctk.CTkLabel(
            legend_frame,
            text="• ⚙ = Feste Struktur",
            font=("Arial", 10)
        ).pack(anchor="w", padx=10)
        
        # Initial stats update
        self.update_stats()
    
    def update_stats(self):
        """Aktualisiert Statistiken"""
        stats = self.editor.matrix.get_stats()
        
        text = f"""Zellen: {stats['total_cells']}
Bekannt: {stats['known_cells']}
Unbekannt: {stats['unknown_cells']}
Vollständigkeit: {stats['completeness']:.1f}%

Schwarz: {stats['black_cells']}
Weiß: {stats['white_cells']}"""
        
        self.stats_label.configure(text=text)
    
    def _on_reset(self):
        """Reset Editor"""
        self.editor.matrix.reset()
        self.editor.render()
        self.update_stats()
    
    def _on_clear_unlocked(self):
        """Lösche alle unlocked Zellen"""
        for i in range(self.editor.matrix.size):
            for j in range(self.editor.matrix.size):
                if not self.editor.matrix.locked[i, j]:
                    self.editor.matrix.grid[i, j] = CellState.UNKNOWN
        
        self.editor.render()
        self.update_stats()