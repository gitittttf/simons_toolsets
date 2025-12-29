import customtkinter as ctk
from typing import Callable, Optional, Set, Tuple
import numpy as np
from ..core.qr_matrix import QRMatrix, CellState

# ... Colors class (Same as before) ...
class Colors:
    """Frutiger Aero Theme - Windows Vista/7 Style"""
    # Glasmorphism-inspirierte Hintergründe
    BG_PRIMARY = "#e8f4fc"          # Sanftes Himmelblau
    BG_SECONDARY = "#ffffff"         # Reines Weiß (Glass-Panels)
    BG_CARD = "#f0f8ff"              # Alice Blue (Karten)
    BG_CARD_HOVER = "#dbeeff"        # Helleres Hover
    
    # Text auf hellem Hintergrund
    TEXT_PRIMARY = "#1a1a2e"         # Dunkles Navy
    TEXT_SECONDARY = "#4a5568"       # Mittelgrau
    TEXT_MUTED = "#718096"           # Hellgrau
    
    # Vista-typische Akzentfarben
    ACCENT = "#0078d4"               # Vista Blau
    ACCENT_HOVER = "#006cbd"         # Dunkleres Blau
    ACCENT_SECONDARY = "#38b000"     # Vista Grün
    
    # QR Farben (Aero-Stil)
    QR_BLACK = "#1a1a2e"             # Dunkles Navy
    QR_WHITE = "#f8fafc"             # Fast Weiß
    QR_LOCKED_BLACK = "#0f172a"      # Tiefes Navy für gelockt
    QR_LOCKED_WHITE = "#ffffff"      # Reines Weiß für gelockt
    QR_UNLOCKED_BORDER = "#94a3b8"   # Sanftes Grau
    QR_LOCKED_BORDER = "#0078d4"     # Vista Blau (gelockt)
    QR_PATTERN_BORDER = "#38b000"    # Vista Grün (Pattern)
    QR_HOVER = "#60a5fa"             # Helles Hover-Blau
    QR_PAINTING = "#f97316"          # Orange während des Malens
    
    # Status-Farben (Aero-Stil)
    SUCCESS = "#38b000"              # Frisches Grün
    WARNING = "#f59e0b"              # Warmes Orange
    ERROR = "#dc2626"                # Klares Rot


class GridEditor(ctk.CTkFrame):
    """
    Zoomable & Pannable Grid Editor
    """
    
    def __init__(self, parent, matrix: QRMatrix):
        super().__init__(parent, fg_color="transparent")
        
        self.matrix = matrix
        
        # View State
        self.scale = 1.0
        self.offset_x = 50.0
        self.offset_y = 50.0
        self.base_cell_size = 20
        
        # Interaction State
        self.last_mouse_x = 0
        self.last_mouse_y = 0
        self.is_panning = False
        
        self.is_drawing = False
        self.draw_value = None
        self.painted_cells: Set[Tuple[int, int]] = set()
        
        self.is_locking = False
        self.lock_value = None
        self.locked_cells: Set[Tuple[int, int]] = set()
        
        self.hovered_cell = None
        
        # Callbacks
        self.on_cell_changed: Optional[Callable] = None
        
        # UI
        self.canvas_frame = ctk.CTkFrame(self, fg_color=Colors.BG_SECONDARY, corner_radius=0)
        self.canvas_frame.pack(fill="both", expand=True)
        
        self.canvas = ctk.CTkCanvas(
            self.canvas_frame,
            bg="#e5e5e5", # Neutral gray background like Photoshop
            highlightthickness=0
        )
        self.canvas.pack(fill="both", expand=True)
        
        # Bindings
        self.canvas.bind("<Configure>", self._on_resize)
        
        # Zoom (Wheel)
        self.canvas.bind("<MouseWheel>", self._on_wheel)      # Windows
        self.canvas.bind("<Button-4>", self._on_wheel)        # Linux Up
        self.canvas.bind("<Button-5>", self._on_wheel)        # Linux Down
        
        # Mouse Move (Hover & Drag)
        self.canvas.bind("<Motion>", self._on_motion)
        
        # Left Click (Draw)
        self.canvas.bind("<Button-1>", self._on_left_down)
        self.canvas.bind("<B1-Motion>", self._on_left_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_left_up)
        
        # Right Click (Lock)
        self.canvas.bind("<Button-3>", self._on_right_down)
        self.canvas.bind("<B3-Motion>", self._on_right_drag)
        self.canvas.bind("<ButtonRelease-3>", self._on_right_up)
        
        # Ctrl + Click (Pan) - We handle this logic in _on_left_down checking state
        
        self._init_cells_white()
        self.render()

    def _init_cells_white(self):
        for i in range(self.matrix.size):
            for j in range(self.matrix.size):
                if not self.matrix.locked[i, j]:
                    self.matrix.grid[i, j] = CellState.WHITE

    # --- Coordinate Transforms ---
    
    def _to_screen(self, r, c) -> Tuple[float, float, float]:
        """Returns x, y, size"""
        size = self.base_cell_size * self.scale
        x = c * size + self.offset_x
        y = r * size + self.offset_y
        return x, y, size
    
    def _to_grid(self, x, y) -> Optional[Tuple[int, int]]:
        """Returns r, c"""
        size = self.base_cell_size * self.scale
        c = int((x - self.offset_x) / size)
        r = int((y - self.offset_y) / size)
        
        if 0 <= r < self.matrix.size and 0 <= c < self.matrix.size:
            return r, c
        return None

    # --- Rendering ---

    def render(self):
        self.canvas.delete("all")
        
        # Optimize: Only draw visible? For now, standard QR (max 177x177) is fine to draw all ~30k rects if simple.
        # But Tkinter Canvas can get slow with >10k items.
        # Max QR V40 is 177*177 = 31329 items. That will lagg.
        # V10 is 57x57 = 3249 items. Fast.
        # We should only draw if reasonable or optimize.
        # Actually, draw using `create_rectangle` is okay-ish.
        # But for large QRs, we might need image-based rendering if it lags.
        # Let's try standard vector first.
        
        cell_pixel_size = self.base_cell_size * self.scale
        
        # Draw Background (Grid Area)
        total_size = self.matrix.size * cell_pixel_size
        self.canvas.create_rectangle(
            self.offset_x, self.offset_y,
            self.offset_x + total_size, self.offset_y + total_size,
            fill="white", outline=Colors.QR_UNLOCKED_BORDER
        )
        
        # Draw Cells
        # To optimize: Draw only non-white cells? No, we need borders.
        # Optimization: Use one complex polygon or image?
        # Let's stick to rects for now but maybe skip drawing fully white unlocked ones if we have a white background?
        # Yes, unlocked white cells are just "gap".
        
        for r in range(self.matrix.size):
            for c in range(self.matrix.size):
                self._draw_single_cell(r, c, cell_pixel_size)
    
        # Grid overlay (optional, maybe only at high zoom or low version)
        if self.scale > 0.5:
             self.canvas.create_rectangle(
                self.offset_x, self.offset_y,
                self.offset_x + total_size, self.offset_y + total_size,
                outline=Colors.ACCENT_SECONDARY, width=1, tags="border"
            )

    def _draw_single_cell(self, r, c, size):
        x = c * size + self.offset_x
        y = r * size + self.offset_y
        
        val = self.matrix.grid[r, c]
        locked = self.matrix.locked[r, c]
        fixed = self.matrix._is_fixed_pattern(r, c)
        
        # Skip standard white unlocked cells (optimization)
        if val == CellState.WHITE and not locked and not fixed:
            # Just draw selection/hover if needed, but base is empty
            # If we want a grid look, we need lines.
            # Let's draw lines separately?
            pass
        else:
            # Colors
            if fixed:
                color = Colors.QR_LOCKED_BLACK if val == CellState.BLACK else Colors.QR_LOCKED_WHITE
                outline = Colors.QR_PATTERN_BORDER
            elif locked:
                color = Colors.QR_LOCKED_BLACK if val == CellState.BLACK else Colors.QR_LOCKED_WHITE
                outline = Colors.QR_LOCKED_BORDER
            else:
                color = Colors.QR_BLACK # Only for black
                outline = Colors.QR_UNLOCKED_BORDER
            
            # Optimization: Don't draw valid white empty cells, only draw Black or Locked/Fixed
            if val == CellState.WHITE and not locked and not fixed:
                return

            self.canvas.create_rectangle(
                x, y, x + size, y + size,
                fill=color, outline=outline,
                tags=f"c_{r}_{c}"
            )
            
            # Markers
            if size > 10:
                cx, cy = x + size/2, y + size/2
                if fixed:
                    tc = "white" if val == CellState.BLACK else Colors.QR_PATTERN_BORDER
                    self.canvas.create_text(cx, cy, text="◆", fill=tc, font=("Arial", int(size/3)))
                elif locked:
                    tc = "white" if val == CellState.BLACK else Colors.ACCENT
                    self.canvas.create_text(cx, cy, text="✓", fill=tc, font=("Arial", int(size/2.5)))

    def _draw_cursor_hl(self, r, c):
        self.canvas.delete("hl")
        if r is not None:
             x, y, size = self._to_screen(r, c)
             self.canvas.create_rectangle(
                 x, y, x+size, y+size,
                 outline=Colors.QR_HOVER, width=2, tags="hl"
             )

    # --- Events ---

    def _on_resize(self, event):
        # Maybe center grid?
        pass

    def _on_wheel(self, event):
        # Zoom logic
        x, y = event.x, event.y
        
        # Check delta
        if event.num == 5 or event.delta < 0:
            factor = 0.9
        else:
            factor = 1.1
            
        new_scale = self.scale * factor
        # Limit zoom
        if new_scale < 0.1: new_scale = 0.1
        if new_scale > 20.0: new_scale = 20.0
        
        # Adjust offset to zoom towards mouse
        self.offset_x = x - (x - self.offset_x) * (new_scale / self.scale)
        self.offset_y = y - (y - self.offset_y) * (new_scale / self.scale)
        self.scale = new_scale
        
        self.render()

    def _on_left_down(self, event):
        self.last_mouse_x = event.x
        self.last_mouse_y = event.y
        
        # Check for Ctrl -> Pan
        if event.state & 0x0004: # Control key mask (usually 4)
            self.is_panning = True
            self.canvas.config(cursor="fleur")
            return

        # Drawing
        cell = self._to_grid(event.x, event.y)
        if cell:
            r, c = cell
            if not self.matrix.locked[r, c] and not self.matrix._is_fixed_pattern(r, c):
                self.is_drawing = True
                curr = self.matrix.grid[r, c]
                self.draw_value = CellState.BLACK if curr == CellState.WHITE else CellState.WHITE
                self.matrix.grid[r, c] = self.draw_value
                self.painted_cells.add(cell)
                self.render() # Full render is safer for artifacts, though slower.
                self._notify()

    def _on_left_drag(self, event):
        if self.is_panning:
            dx = event.x - self.last_mouse_x
            dy = event.y - self.last_mouse_y
            self.offset_x += dx
            self.offset_y += dy
            self.last_mouse_x = event.x
            self.last_mouse_y = event.y
            self.render() # Or just move items? Render is cleaner for simplicity
            return
            
        if self.is_drawing:
            cell = self._to_grid(event.x, event.y)
            if cell and cell not in self.painted_cells:
                r, c = cell
                if not self.matrix.locked[r, c] and not self.matrix._is_fixed_pattern(r, c):
                    self.matrix.grid[r, c] = self.draw_value
                    self.painted_cells.add(cell)
                    self.render()
                    self._notify()

    def _on_left_up(self, event):
        self.is_panning = False
        self.is_drawing = False
        self.painted_cells.clear()
        self.canvas.config(cursor="")

    def _on_right_down(self, event):
        cell = self._to_grid(event.x, event.y)
        if cell:
            r, c = cell
            if not self.matrix._is_fixed_pattern(r, c):
                self.is_locking = True
                curr = self.matrix.locked[r, c]
                self.lock_value = not curr
                self.matrix.locked[r, c] = self.lock_value
                self.locked_cells.add(cell)
                self.render()
                self._notify()
                
    def _on_right_drag(self, event):
         if self.is_locking:
            cell = self._to_grid(event.x, event.y)
            if cell and cell not in self.locked_cells:
                r, c = cell
                if not self.matrix._is_fixed_pattern(r, c):
                    self.matrix.locked[r, c] = self.lock_value
                    self.locked_cells.add(cell)
                    self.render()
                    self._notify()
                    
    def _on_right_up(self, event):
        self.is_locking = False
        self.locked_cells.clear()

    def _on_motion(self, event):
        if not self.is_panning and not self.is_drawing and not self.is_locking:
            cell = self._to_grid(event.x, event.y)
            if cell != self.hovered_cell:
                self.hovered_cell = cell
                r = cell[0] if cell else None
                c = cell[1] if cell else None
                self._draw_cursor_hl(r, c)

    def _notify(self):
        if self.on_cell_changed:
            self.on_cell_changed(0, 0)

# Statistics Panel (Simplified for Sidebar)
class StatisticsPanel(ctk.CTkFrame):
     def __init__(self, parent, matrix):
        super().__init__(parent, fg_color="transparent")
        self.matrix = matrix
        # ... logic similar to previous but vertical layout ...
        # (I will reimplement simpler stats here)
        self.lbl_unknown = ctk.CTkLabel(self, text="0 Unknown")
        self.lbl_unknown.pack()
        
     def update(self):
         # ... update logic ...
         pass

# Controls (Just Buttons)
class GridEditorControls(ctk.CTkFrame):
    def __init__(self, parent, editor):
        super().__init__(parent, fg_color="transparent")
        self.editor = editor
        # Buttons logic
