import customtkinter as ctk
import numpy as np
from PIL import Image, ImageTk
from typing import Any, Callable, Optional, Set, Tuple
from ..core.qr_matrix import QRMatrix, CellState
from ..core.analysis import (
    BLOCK_AMBIGUOUS, BLOCK_CORRECTED, BLOCK_OK, BLOCK_UNSOLVABLE, SolvabilityReport,
)

from .theme import Colors, Dimensions

# =============================================================================
# THEME (Loaded from theme.py)
# =============================================================================

# Overlay-Farbe je Block-Status (siehe core.analysis)
OVERLAY_COLORS = {
    BLOCK_OK: Colors.OVERLAY_OK,
    BLOCK_CORRECTED: Colors.OVERLAY_CORRECTED,
    BLOCK_AMBIGUOUS: Colors.OVERLAY_AMBIGUOUS,
    BLOCK_UNSOLVABLE: Colors.OVERLAY_UNSOLVABLE,
}


class GridEditor(ctk.CTkFrame):
    """
    Zoomable & Pannable Grid Editor (Photoshop-style)

    Bedienung:
      Linksklick/-ziehen   Schwarz/Weiß malen (Zelle wird bekannt)
      Rechtsklick/-ziehen  Zelle als unbekannt markieren bzw. wieder als bekannt übernehmen
      Mausrad              Zoom, Strg+Linksklick oder Mittelklick: verschieben

    "Bekannt" entspricht matrix.locked; unbekannte Zellen werden grau mit "?" gezeichnet.
    """
    
    def __init__(self, parent, matrix: QRMatrix, cell_size=22):
        super().__init__(parent, fg_color="transparent")
        self.matrix = matrix
        
        # View State
        self.scale = 1.0
        self.base_cell_size = float(cell_size)
        
        # Start centered (will be calculated in _center_view)
        self.offset_x = 0.0
        self.offset_y = 0.0
        
        # Interaction State
        self.last_mouse_x = 0
        self.last_mouse_y = 0
        self.is_panning = False
        
        # Painting State
        self.is_drawing = False
        self.draw_value = None
        self.painted_cells: Set[Tuple[int, int]] = set()
        
        # Locking State
        self.is_locking = False
        self.lock_value = None
        self.locked_cells: Set[Tuple[int, int]] = set()
        
        self.hovered_cell = None
        # Solange der Nutzer nicht selbst zoomt/verschiebt, bleibt der Code bei Größenänderung zentriert
        self.user_moved_view = False
        
        # Foto-Hintergrund (entzerrtes Bild aus dem Import)
        self.photo: Optional[np.ndarray] = None
        self.show_photo = False
        # (Schlüssel, PhotoImage) - nur bei Zoom/Pan neu skalieren
        self._photo_cache: Tuple[Any, Any] = (None, None)
        
        # Overlay (Lösbarkeit je Block, Format-Info)
        self.overlay_enabled = False
        self.overlay_report: Optional[SolvabilityReport] = None
        self._overlay_format_cells: Set[Tuple[int, int]] = set()
        
        # Callbacks
        self.on_cell_changed: Optional[Callable] = None
        
        # Canvas Container
        self.canvas_frame = ctk.CTkFrame(self, fg_color=Colors.BG_SECONDARY, corner_radius=0)
        self.canvas_frame.pack(fill="both", expand=True)
        
        # Canvas
        self.canvas = ctk.CTkCanvas(
            self.canvas_frame,
            bg="#2d2d2d", # Dark gray background for better contrast
            highlightthickness=Dimensions.GRID_HIGHLIGHT_THICKNESS
        )
        self.canvas.pack(fill="both", expand=True)
        
        # Bindings
        self.canvas.bind("<Configure>", self._on_resize)
        
        # Zoom (Wheel)
        self.canvas.bind("<MouseWheel>", self._on_wheel)      # Windows
        self.canvas.bind("<Button-4>", self._on_wheel)        # Linux Up
        self.canvas.bind("<Button-5>", self._on_wheel)        # Linux Down
        
        # Mouse Move (Hover)
        self.canvas.bind("<Motion>", self._on_motion)
        
        # Left Click (Draw/Pan)
        self.canvas.bind("<Button-1>", self._on_left_down)
        self.canvas.bind("<B1-Motion>", self._on_left_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_left_up)
        
        # Right Click (Lock)
        self.canvas.bind("<Button-3>", self._on_right_down)
        self.canvas.bind("<B3-Motion>", self._on_right_drag)
        self.canvas.bind("<ButtonRelease-3>", self._on_right_up)
        
        # Middle Click (Pan)
        self.canvas.bind("<Button-2>", self._on_middle_down) # Windows/Linux Middle
        self.canvas.bind("<B2-Motion>", self._on_middle_drag)
        self.canvas.bind("<ButtonRelease-2>", self._on_middle_up)

        self._init_cells_white()
        
        # Initial Center
        self.after(100, self._center_view)

    def _init_cells_white(self):
        for i in range(self.matrix.size):
            for j in range(self.matrix.size):
                if not self.matrix.locked[i, j]:
                    self.matrix.grid[i, j] = CellState.WHITE

    def _center_view(self):
        """Centers the QR code in the canvas and fits it if needed"""
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        
        if cw <= 1 or ch <= 1:
            self.after(100, self._center_view)
            return

        qr_px = self.matrix.size * self.base_cell_size
        
        # Calculate scale to fit with margin (80%)
        target_scale = 1.0
        if qr_px > min(cw, ch) * 0.8:
            target_scale = (min(cw, ch) * 0.8) / qr_px
        
        self.scale = target_scale
        
        # Re-calc pixel size with new scale
        qr_px_scaled = qr_px * self.scale
        
        self.offset_x = (cw - qr_px_scaled) / 2
        self.offset_y = (ch - qr_px_scaled) / 2
            
        self.render()

    def _to_screen(self, r, c) -> Tuple[float, float, float]:
        size = self.base_cell_size * self.scale
        x = c * size + self.offset_x
        y = r * size + self.offset_y
        return x, y, size
    
    def _to_grid(self, x, y) -> Optional[Tuple[int, int]]:
        size = self.base_cell_size * self.scale
        if size == 0: return None
        
        c = int((x - self.offset_x) / size)
        r = int((y - self.offset_y) / size)
        
        if 0 <= r < self.matrix.size and 0 <= c < self.matrix.size:
            return r, c
        return None

    def render(self):
        self.canvas.delete("all")
        
        cell_pixel_size = self.base_cell_size * self.scale
        if cell_pixel_size < 1: cell_pixel_size = 1 # Safety
        
        total_size = self.matrix.size * cell_pixel_size
        
        # Draw Background (Board)
        self.canvas.create_rectangle(
            self.offset_x, self.offset_y,
            self.offset_x + total_size, self.offset_y + total_size,
            fill="#ffffff", outline=Colors.QR_UNLOCKED_BORDER, width=0,
            tags="board_bg"
        )
        
        if self.show_photo and self.photo is not None:
            self._draw_photo(total_size)
        
        # Simple mode for tiny cells to improve performance
        simple_mode = cell_pixel_size < 4
        
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        
        # Draw Margin (pixels) to prevent blank edges during fast pans
        margin = 100 
        
        for r in range(self.matrix.size):
            # Culling: Only draw visible rows (with margin)
            uy = r * cell_pixel_size + self.offset_y
            if uy > ch + margin or uy + cell_pixel_size < -margin:
                continue
                
            for c in range(self.matrix.size):
                ux = c * cell_pixel_size + self.offset_x
                if ux > cw + margin or ux + cell_pixel_size < -margin:
                    continue
                
                self._draw_single_cell(r, c, cell_pixel_size, simple_mode)
        
        # Outer Border
        self.canvas.create_rectangle(
            self.offset_x, self.offset_y,
            self.offset_x + total_size, self.offset_y + total_size,
            outline=Colors.ACCENT, width=Dimensions.GRID_OUTER_BORDER_WIDTH
        )

    def set_photo(self, photo: Optional[np.ndarray], show: bool = True):
        """Setzt das entzerrte Foto (Graubild, quadratisch) als Hintergrund"""
        self.photo = photo
        self.show_photo = show and photo is not None
        self._photo_cache = (None, None)
        self.render()

    def _draw_photo(self, total_size: float):
        """Zeichnet den sichtbaren Ausschnitt des Fotos (gecacht, solange sich Zoom/Ausschnitt nicht ändern)"""
        if self.photo is None:
            return
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        # Sichtbarer Bereich in Grid-Pixeln
        x0, y0 = max(0.0, -self.offset_x), max(0.0, -self.offset_y)
        x1, y1 = min(total_size, cw - self.offset_x), min(total_size, ch - self.offset_y)
        if x1 - x0 < 1 or y1 - y0 < 1:
            return
        key = (round(total_size), round(x0), round(y0), round(x1), round(y1))
        if self._photo_cache[0] != key:
            scale = self.photo.shape[0] / total_size
            crop = self.photo[int(y0 * scale):max(int(y0 * scale) + 1, int(y1 * scale)),
                              int(x0 * scale):max(int(x0 * scale) + 1, int(x1 * scale))]
            image = Image.fromarray(crop).resize((key[3] - key[1], key[4] - key[2]), Image.Resampling.BILINEAR)
            self._photo_cache = (key, ImageTk.PhotoImage(image))
        self.canvas.create_image(self.offset_x + key[1], self.offset_y + key[2],
                                 image=self._photo_cache[1], anchor="nw")

    def set_overlay(self, report: Optional[SolvabilityReport], enabled: Optional[bool] = None):
        """Setzt die Analyse für das Overlay (und optional, ob es angezeigt wird) und zeichnet neu"""
        self.overlay_report = report
        self._overlay_format_cells = set(report.format_cells) if report else set()
        if enabled is not None:
            self.overlay_enabled = enabled
        self.render()

    def _overlay_color(self, r, c) -> Optional[str]:
        report = self.overlay_report
        if not self.overlay_enabled or report is None:
            return None
        if (r, c) in self._overlay_format_cells:
            return Colors.OVERLAY_FORMAT
        if (report.module_affected is not None and report.module_block is not None
                and report.module_affected[r, c]):
            block = report.module_block[r, c]
            if 0 <= block < len(report.blocks):
                return OVERLAY_COLORS[report.blocks[block].status]
        return None

    def _draw_single_cell(self, r, c, size, simple_mode):
        x = c * size + self.offset_x
        y = r * size + self.offset_y
        
        val = self.matrix.grid[r, c]
        known = self.matrix.locked[r, c]
        fixed = self.matrix._is_fixed_pattern(r, c)
        
        if self.show_photo and self.photo is not None:
            self._draw_photo_cell(x, y, size, val, known, fixed, simple_mode)
        else:
            self._draw_plain_cell(x, y, size, val, known, fixed, simple_mode)

        # Overlay als farbiger Innenrahmen (Stipple-Füllungen gibt es nicht auf allen Plattformen)
        overlay = self._overlay_color(r, c)
        if overlay:
            inset = max(1.0, size * 0.12)
            self.canvas.create_rectangle(
                x + inset, y + inset, x + size - inset, y + size - inset,
                outline=overlay, width=max(1, int(size * 0.12)),
            )

    def _draw_photo_cell(self, x, y, size, val, known, fixed, simple_mode):
        """Foto sichtbar lassen: bekannt = kleiner Punkt in der abgetasteten Farbe, unbekannt = orange '?'"""
        if fixed or simple_mode:
            return
        if known:
            r = size * 0.16
            cx, cy = x + size / 2, y + size / 2
            fill = Colors.QR_LOCKED_BLACK if val == CellState.BLACK else Colors.QR_LOCKED_WHITE
            self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill=fill, outline=Colors.ACCENT, width=1)
        else:
            self.canvas.create_rectangle(x + 1, y + 1, x + size - 1, y + size - 1,
                                         outline=Colors.QR_PAINTING, width=2)
            if size > 12:
                self.canvas.create_text(x + size / 2, y + size / 2, text="?", fill=Colors.QR_PAINTING,
                                        font=(Dimensions.GRID_MARKER_FONT,
                                              int(size / Dimensions.GRID_MARKER_LOCKED_DIVIDER), "bold"))

    def _draw_plain_cell(self, x, y, size, val, known, fixed, simple_mode):
        if fixed:
            fill = Colors.QR_LOCKED_BLACK if val == CellState.BLACK else Colors.QR_LOCKED_WHITE
            outline = Colors.QR_PATTERN_BORDER
        elif known:
            fill = Colors.QR_LOCKED_BLACK if val == CellState.BLACK else Colors.QR_LOCKED_WHITE
            outline = Colors.QR_GRID_LINE
        else:
            fill = Colors.QR_UNKNOWN
            outline = Colors.QR_GRID_LINE

        if simple_mode:
            self.canvas.create_rectangle(x, y, x+size, y+size, fill=fill, width=Dimensions.GRID_CELL_BORDER_NONE)
        else:
            self.canvas.create_rectangle(x, y, x+size, y+size, fill=fill, outline=outline, width=Dimensions.GRID_CELL_BORDER_THIN)
            
            # Markers
            if size > 12:
                cx, cy = x + size/2, y + size/2
                if fixed:
                     tcol = "#ffffff" if val == CellState.BLACK else Colors.QR_PATTERN_BORDER
                     self.canvas.create_text(
                         cx, cy, text="x", fill=tcol, 
                         font=(Dimensions.GRID_MARKER_FONT, int(size/Dimensions.GRID_MARKER_FIXED_DIVIDER))
                     )
                elif not known:
                     self.canvas.create_text(
                         cx, cy, text="?", fill=Colors.QR_UNKNOWN_MARK,
                         font=(Dimensions.GRID_MARKER_FONT, int(size/Dimensions.GRID_MARKER_LOCKED_DIVIDER))
                     )

    def _draw_cursor_hl(self, r, c):
        self.canvas.delete("hl")
        if r is not None:
             x, y, size = self._to_screen(r, c)
             self.canvas.create_rectangle(
                 x, y, x+size, y+size,
                 outline=Colors.QR_HOVER, 
                 width=Dimensions.GRID_CELL_BORDER_THICK, 
                 tags="hl"
             )

    def _on_resize(self, event):
        if not self.user_moved_view:
            self._center_view()

    def _on_wheel(self, event):
        x, y = event.x, event.y
        scale_delta = 1.0
        
        if event.num == 5 or event.delta < 0:
            scale_delta = 0.9
        else:
            scale_delta = 1.1
            
        self.user_moved_view = True
        new_scale = self.scale * scale_delta
        if new_scale < 0.05: new_scale = 0.05
        if new_scale > 20.0: new_scale = 20.0
        
        # Zoom towards cursor
        self.offset_x = x - (x - self.offset_x) * (new_scale / self.scale)
        self.offset_y = y - (y - self.offset_y) * (new_scale / self.scale)
        self.scale = new_scale
        
        self.render()

    # --- LEFT CLICK (Draw or Ctrl+Pan) ---
    def _on_left_down(self, event):
        self.last_mouse_x = event.x
        self.last_mouse_y = event.y
        
        # Ctrl -> Pan
        if event.state & 0x4 or event.state & 0x20000: # Control key
            self.is_panning = True
            self.user_moved_view = True
            self.canvas.config(cursor="fleur")
            return

        cell = self._to_grid(event.x, event.y)
        if cell:
            r, c = cell
            if not self.matrix._is_fixed_pattern(r, c):
                self.is_drawing = True
                # Erste Zelle bestimmt die Farbe des Strichs: unbekannt/weiß → schwarz, schwarz → weiß
                known_black = self.matrix.locked[r, c] and self.matrix.grid[r, c] == CellState.BLACK
                self.draw_value = CellState.WHITE if known_black else CellState.BLACK
                self._paint(r, c)
                self.painted_cells.add(cell)
                self.render()
                self._notify()

    def _on_left_drag(self, event):
        if self.is_panning:
            dx = event.x - self.last_mouse_x
            dy = event.y - self.last_mouse_y
            
            # OPTIMIZATION: Move existing items instead of redraw
            self.canvas.move("all", dx, dy)
            
            self.offset_x += dx
            self.offset_y += dy
            self.last_mouse_x = event.x
            self.last_mouse_y = event.y
            # Do NOT call render() here for performance!
            return
            
        if self.is_drawing:
            cell = self._to_grid(event.x, event.y)
            if cell and cell not in self.painted_cells:
                r, c = cell
                if not self.matrix._is_fixed_pattern(r, c):
                    self._paint(r, c)
                    self.painted_cells.add(cell)
                    self.render()
                    self._notify()

    def _paint(self, r, c):
        """Gemalte Zellen sind bekannt"""
        self.matrix.grid[r, c] = self.draw_value
        self.matrix.locked[r, c] = True

    def _on_left_up(self, event):
        if self.is_panning:
             # Final render to clean up edges/culling after move
             self.render()
             
        self.is_panning = False
        self.is_drawing = False
        self.painted_cells.clear()
        self.canvas.config(cursor="")

    # --- RIGHT CLICK (unbekannt markieren / wieder als bekannt übernehmen) ---
    def _on_right_down(self, event):
        cell = self._to_grid(event.x, event.y)
        if cell:
            r, c = cell
            if not self.matrix._is_fixed_pattern(r, c):
                self.is_locking = True
                # Erste Zelle bestimmt die Richtung: bekannt → unbekannt oder umgekehrt
                self.lock_value = not self.matrix.locked[r, c]
                self._set_known(r, c, self.lock_value)
                self.locked_cells.add(cell)
                self.render()
                self._notify()
                
    def _on_right_drag(self, event):
         if self.is_locking:
            cell = self._to_grid(event.x, event.y)
            if cell and cell not in self.locked_cells:
                r, c = cell
                if not self.matrix._is_fixed_pattern(r, c):
                    self._set_known(r, c, self.lock_value)
                    self.locked_cells.add(cell)
                    self.render()
                    self._notify()
                    
    def _set_known(self, r, c, known: bool):
        """Der Farbwert bleibt beim Unbekannt-Markieren erhalten und kommt beim Zurückschalten wieder"""
        self.matrix.locked[r, c] = known
        if known and self.matrix.grid[r, c] == CellState.UNKNOWN:
            self.matrix.grid[r, c] = CellState.WHITE

    def _on_right_up(self, event):
        self.is_locking = False
        self.locked_cells.clear()

    # --- MIDDLE CLICK (Pan) ---
    def _on_middle_down(self, event):
        self.is_panning = True
        self.user_moved_view = True
        self.last_mouse_x = event.x
        self.last_mouse_y = event.y
        self.canvas.config(cursor="fleur")

    def _on_middle_drag(self, event):
        if self.is_panning:
            dx = event.x - self.last_mouse_x
            dy = event.y - self.last_mouse_y
            
            # OPTIMIZATION: Move existing items instead of redraw
            self.canvas.move("all", dx, dy)
            
            self.offset_x += dx
            self.offset_y += dy
            self.last_mouse_x = event.x
            self.last_mouse_y = event.y
            # Do NOT call render() here for performance!

    def _on_middle_up(self, event):
        if self.is_panning:
             # Final render to clean up
             self.render()
        self.is_panning = False
        self.canvas.config(cursor="")

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

    def set_cell_size(self, size):
        self.base_cell_size = float(size)
        self.render()