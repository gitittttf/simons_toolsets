"""
Dialog zum Setzen/Korrigieren der vier Ecken eines QR-Codes in einem Bild

Die Ecken müssen nicht pixelgenau sein: Der Import justiert sie anschließend anhand der festen
Muster nach (core.image_import.refine_corners). Die Reihenfolge ist egal, solange die Punkte
im Umlaufsinn liegen - die Orientierung wird beim Abtasten automatisch bestimmt.
"""

from typing import Callable, Optional

import customtkinter as ctk
import numpy as np
from PIL import Image, ImageTk

from ..core import image_import
from .theme import Colors, Dimensions, Fonts

MAX_VIEW = (900, 640)   # maximale Anzeigegröße des Bilds im Dialog
HANDLE_RADIUS = 9


class CornerDialog(ctk.CTkToplevel):
    """
    Args:
        image: BGR-Bild (numpy)
        corners: Startwerte (z.B. von OpenCV) oder None
        on_accept: wird mit den Ecken (4×2, Bildkoordinaten) aufgerufen
    """

    def __init__(self, parent, image: np.ndarray, corners: Optional[np.ndarray],
                 on_accept: Callable[[np.ndarray], None]):
        super().__init__(parent)
        self.title("Ecken des QR-Codes festlegen")
        self.configure(fg_color=Colors.BG_PRIMARY)
        self.resizable(False, False)
        self.image = image
        self.on_accept = on_accept
        self.detected = corners is not None

        h, w = image.shape[:2]
        self.zoom = min(MAX_VIEW[0] / w, MAX_VIEW[1] / h, 1.0)
        view_w, view_h = int(w * self.zoom), int(h * self.zoom)
        rgb = Image.fromarray(image[:, :, ::-1]).resize((view_w, view_h), Image.Resampling.LANCZOS)

        start = corners if corners is not None else image_import.default_corners(image)
        self.points = [list(p) for p in np.array(start, dtype=np.float32) * self.zoom]
        self._drag_index: Optional[int] = None

        hint = ("OpenCV hat den Code gefunden - Ecken bei Bedarf korrigieren." if self.detected else
                "Kein Code automatisch gefunden. Ziehe die vier Punkte auf die Ecken des QR-Codes.")
        self.hint_label = ctk.CTkLabel(self, text=hint, font=Fonts.BODY, text_color=Colors.TEXT_PRIMARY)
        self.hint_label.pack(padx=15, pady=(12, 2), anchor="w")
        ctk.CTkLabel(
            self, font=Fonts.SMALL, text_color=Colors.TEXT_MUTED,
            text="Ungefähr reicht: die Ecken werden anhand der Finder- und Timing-Muster nachjustiert."
        ).pack(padx=15, pady=(0, 8), anchor="w")

        self.canvas = ctk.CTkCanvas(self, width=view_w, height=view_h, highlightthickness=0, bg="#2d2d2d")
        self.canvas.pack(padx=15)
        self._photo = ImageTk.PhotoImage(rgb)
        self.canvas.create_image(0, 0, image=self._photo, anchor="nw")
        self.canvas.bind("<Button-1>", self._on_down)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", lambda e: setattr(self, '_drag_index', None))

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(fill="x", padx=15, pady=12)
        ctk.CTkButton(buttons, text="Automatisch erkennen", command=self._auto_detect,
                      fg_color=Colors.BG_CARD, text_color=Colors.TEXT_PRIMARY, hover_color=Colors.BG_CARD_HOVER,
                      border_width=Dimensions.BORDER_WIDTH_THIN, border_color=Colors.BORDER,
                      corner_radius=Dimensions.CORNER_RADIUS_M).pack(side="left")
        ctk.CTkButton(buttons, text="Abbrechen", command=self.destroy,
                      fg_color="transparent", text_color=Colors.TEXT_SECONDARY, hover_color=Colors.BG_CARD_HOVER,
                      corner_radius=Dimensions.CORNER_RADIUS_M).pack(side="right", padx=(8, 0))
        ctk.CTkButton(buttons, text="✓ Übernehmen", command=self._accept,
                      fg_color=Colors.ACCENT, hover_color=Colors.ACCENT_HOVER, font=Fonts.BUTTON,
                      corner_radius=Dimensions.CORNER_RADIUS_M).pack(side="right")

        self._draw()
        self.transient(parent.winfo_toplevel())
        self.after(100, self._make_modal)

    def _make_modal(self):
        try:
            self.grab_set()
            self.focus()
        except Exception:  # Fenster noch nicht sichtbar (z.B. in Tests)
            pass

    def _draw(self):
        self.canvas.delete("overlay")
        flat = [coord for p in self.points for coord in p]
        self.canvas.create_polygon(*flat, outline=Colors.ACCENT, fill="", width=2, tags="overlay")
        for i, (x, y) in enumerate(self.points):
            r = HANDLE_RADIUS
            self.canvas.create_oval(x - r, y - r, x + r, y + r, fill=Colors.ACCENT, outline="#ffffff",
                                    width=2, tags="overlay")
            self.canvas.create_text(x, y, text=str(i + 1), fill="#ffffff",
                                    font=(Dimensions.GRID_MARKER_FONT, 9, "bold"), tags="overlay")

    def _on_down(self, event):
        distances = [np.hypot(event.x - x, event.y - y) for x, y in self.points]
        nearest = int(np.argmin(distances))
        self._drag_index = nearest if distances[nearest] < HANDLE_RADIUS * 3 else None
        if self._drag_index is not None:
            self._on_drag(event)

    def _on_drag(self, event):
        if self._drag_index is None:
            return
        width, height = int(self.canvas.cget("width")), int(self.canvas.cget("height"))
        self.points[self._drag_index] = [min(max(event.x, 0), width), min(max(event.y, 0), height)]
        self._draw()

    def _auto_detect(self):
        corners = image_import.detect_corners(self.image)
        if corners is None:
            self.hint_label.configure(text="Kein Code gefunden - bitte die Ecken von Hand setzen.",
                                      text_color=Colors.ERROR)
            return
        self.points = [list(p) for p in corners * self.zoom]
        self.hint_label.configure(text="Code gefunden.", text_color=Colors.SUCCESS)
        self._draw()

    def corners(self) -> np.ndarray:
        """Ecken in Bildkoordinaten"""
        return np.array(self.points, dtype=np.float32) / self.zoom

    def _accept(self):
        corners = self.corners()
        self.destroy()
        self.on_accept(corners)
