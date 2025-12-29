"""
Results View - Moderne Ergebnisanzeige mit Dark Theme

Features:
- Card-basiertes Design
- Visuelle Confidence-Anzeige mit Farbskala
- Detaillierte Score-Aufschlüsselung
- QR-Code Vorschau
- Export-Funktionalität
"""

import customtkinter as ctk
from typing import List, Callable, Optional
from tkinter import ttk
import tkinter as tk
from PIL import Image, ImageTk
import numpy as np
from ..core.validator import ValidationResult


from .theme import Colors, Fonts, Dimensions

# =============================================================================
# THEME (Loaded from theme.py)
# =============================================================================


class ResultsView(ctk.CTkFrame):
    """
    Modern Results View
    """
    
    ITEMS_PER_PAGE = 50
    
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        
        self.results: List[ValidationResult] = []
        self.current_page = 0
        self.on_result_selected: Optional[Callable[[ValidationResult], None]] = None
        
        self._build_ui()
    
    def _build_ui(self):
        """Baut die UI auf"""
        # Main Layout: Left (Table) + Right (Details)
        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # Left Side: Table Card
        left_card = ctk.CTkFrame(
            self,
            fg_color=Colors.BG_SECONDARY,
            corner_radius=Dimensions.CORNER_RADIUS_L,
            border_width=Dimensions.BORDER_WIDTH_THIN
        )
        left_card.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=0)
        
        # Header
        header_frame = ctk.CTkFrame(left_card, fg_color="transparent")
        header_frame.pack(fill="x", padx=20, pady=15)
        
        self.title_label = ctk.CTkLabel(
            header_frame,
            text="📊 Ergebnisse",
            font=("Segoe UI", 16, "bold"),
            text_color=Colors.TEXT_PRIMARY
        )
        self.title_label.pack(side="left")
        
        # Export Button
        self.btn_export = ctk.CTkButton(
            header_frame,
            text="💾 Exportieren",
            command=self._on_export,
            width=100,
            height=30,
            font=("Segoe UI", 12),
            fg_color=Colors.BG_CARD,
            hover_color=Colors.BG_CARD_HOVER,
            text_color=Colors.ACCENT,
            corner_radius=Dimensions.CORNER_RADIUS_M
        )
        self.btn_export.pack(side="right")
        
        # Table Frame
        table_container = ctk.CTkFrame(left_card, fg_color="#ffffff", corner_radius=Dimensions.CORNER_RADIUS_M)
        table_container.pack(fill="both", expand=True, padx=20, pady=(0, 15))
        
        # Style für Treeview (Modern)
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Modern.Treeview",
            background="#ffffff",
            foreground=Colors.TEXT_PRIMARY,
            fieldbackground="#ffffff",
            borderwidth=0,
            font=("Segoe UI", 11),
            rowheight=28
        )
        style.configure(
            "Modern.Treeview.Heading",
            background=Colors.BG_CARD,
            foreground=Colors.TEXT_PRIMARY,
            borderwidth=0,
            font=("Segoe UI", 11, "bold")
        )
        style.map("Modern.Treeview", background=[('selected', Colors.ACCENT)], foreground=[('selected', '#ffffff')])
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(table_container)
        scrollbar.pack(side="right", fill="y")
        
        # Treeview
        columns = ("rank", "confidence", "type", "content")
        self.tree = ttk.Treeview(
            table_container,
            columns=columns,
            show="headings",
            yscrollcommand=scrollbar.set,
            height=18,
            style="Modern.Treeview"
        )
        
        # Spalten konfigurieren
        self.tree.heading("rank", text="#")
        self.tree.heading("confidence", text="Confidence")
        self.tree.heading("type", text="Typ")
        self.tree.heading("content", text="Inhalt")
        
        self.tree.column("rank", width=50, anchor="center")
        self.tree.column("confidence", width=90, anchor="center")
        self.tree.column("type", width=70, anchor="center")
        self.tree.column("content", width=400, anchor="w")
        
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.tree.yview)
        
        # Bind Selection
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        
        # Pagination
        pagination_frame = ctk.CTkFrame(left_card, fg_color="transparent")
        pagination_frame.pack(fill="x", padx=20, pady=15)
        
        self.btn_prev = ctk.CTkButton(
            pagination_frame,
            text="◀",
            command=self._prev_page,
            width=36,
            height=30,
            font=("Segoe UI", 12),
            fg_color=Colors.BG_CARD,
            hover_color=Colors.BG_CARD_HOVER,
            text_color=Colors.TEXT_PRIMARY,
            corner_radius=Dimensions.CORNER_RADIUS_L,
            state="disabled"
        )
        self.btn_prev.pack(side="left", padx=2)
        
        self.page_label = ctk.CTkLabel(
            pagination_frame,
            text="0 / 0",
            font=("Segoe UI", 12),
            text_color=Colors.TEXT_PRIMARY
        )
        self.page_label.pack(side="left", padx=15)
        
        self.btn_next = ctk.CTkButton(
            pagination_frame,
            text="▶",
            command=self._next_page,
            width=36,
            height=30,
            font=("Segoe UI", 12),
            fg_color=Colors.BG_CARD,
            hover_color=Colors.BG_CARD_HOVER,
            text_color=Colors.TEXT_PRIMARY,
            corner_radius=Dimensions.CORNER_RADIUS_L,
            state="disabled"
        )
        self.btn_next.pack(side="left", padx=2)
        
        # Right Side: Details Card
        right_card = ctk.CTkFrame(
            self,
            fg_color=Colors.BG_SECONDARY,
            corner_radius=Dimensions.CORNER_RADIUS_L,
            border_width=Dimensions.BORDER_WIDTH_THIN
        )
        right_card.grid(row=0, column=1, sticky="nsew", padx=(5, 0), pady=0)
        
        # Details Header
        ctk.CTkLabel(
            right_card,
            text="🔍 Details",
            font=("Segoe UI", 16, "bold"),
            text_color=Colors.TEXT_PRIMARY
        ).pack(pady=(15, 10), padx=15, anchor="w")
        
        # QR Preview Frame
        preview_frame = ctk.CTkFrame(
            right_card,
            fg_color="#ffffff",
            corner_radius=Dimensions.CORNER_RADIUS_M,
            height=200
        )
        preview_frame.pack(fill="x", padx=15, pady=5)
        preview_frame.pack_propagate(False)
        
        self.preview_label = ctk.CTkLabel(
            preview_frame,
            text="Keine Auswahl",
            font=("Segoe UI", 12),
            text_color=Colors.TEXT_MUTED
        )
        self.preview_label.pack(expand=True)
        
        # Confidence Display
        self.confidence_frame = ctk.CTkFrame(
            right_card,
            fg_color=Colors.BG_CARD,
            corner_radius=Dimensions.CORNER_RADIUS_M
        )
        self.confidence_frame.pack(fill="x", padx=15, pady=15)
        
        # Confidence Header Frame
        conf_header = ctk.CTkFrame(self.confidence_frame, fg_color="transparent")
        conf_header.pack(fill="x", pady=(10, 5), padx=10)
        
        ctk.CTkLabel(
            conf_header,
            text="Confidence Score",
            font=("Segoe UI", 12, "bold"),
            text_color=Colors.TEXT_PRIMARY
        ).pack(side="left")
        
        # Help Button
        ctk.CTkButton(
            conf_header,
            text="?",
            command=self._show_score_help,
            width=20,
            height=20,
            font=("Segoe UI", 11, "bold"),
            fg_color=Colors.BG_SECONDARY,
            text_color=Colors.ACCENT,
            hover_color=Colors.BG_CARD_HOVER,
            corner_radius=Dimensions.CORNER_RADIUS_M,
            border_width=Dimensions.BORDER_WIDTH_NONE
        ).pack(side="right")
        
        self.confidence_bar = ctk.CTkProgressBar(
            self.confidence_frame,
            height=8,
            fg_color="#ffffff",
            progress_color=Colors.ACCENT,
            corner_radius=Dimensions.CORNER_RADIUS_S
        )
        self.confidence_bar.pack(fill="x", padx=10, pady=5)
        self.confidence_bar.set(0)
        
        self.confidence_label = ctk.CTkLabel(
            self.confidence_frame,
            text="0%",
            font=("Segoe UI", 18, "bold"),
            text_color=Colors.ACCENT
        )
        self.confidence_label.pack(pady=(0, 10))
        
        # Score Breakdown
        self.scores_frame = ctk.CTkFrame(
            right_card,
            fg_color="transparent"
        )
        self.scores_frame.pack(fill="x", padx=15, pady=5)
        
        self.score_labels = {}
        scores = [
            ("structure", "Struktur"),
            ("pattern", "Muster"),
            ("density", "Dichte"),
            ("decode", "Dekodierung"),
            ("content", "Inhalt")
        ]
        
        for key, label in scores:
            row = ctk.CTkFrame(self.scores_frame, fg_color="transparent")
            row.pack(fill="x", pady=2)
            
            ctk.CTkLabel(
                row,
                text=label,
                font=("Segoe UI", 11),
                text_color=Colors.TEXT_SECONDARY,
                width=80, anchor="w"
            ).pack(side="left")
            
            bar = ctk.CTkProgressBar(
                row,
                height=5,
                fg_color=Colors.BG_CARD,
                progress_color=Colors.ACCENT_SECONDARY,
                width=100,
                corner_radius=Dimensions.CORNER_RADIUS_S
            )
            bar.pack(side="left", padx=5)
            bar.set(0)
            
            val_label = ctk.CTkLabel(
                row,
                text="0%",
                font=("Segoe UI", 11),
                text_color=Colors.TEXT_PRIMARY,
                width=35, anchor="e"
            )
            val_label.pack(side="left")
            
            self.score_labels[key] = (bar, val_label)
        
        # Content Preview
        ctk.CTkLabel(
            right_card,
            text="📄 Inhalt",
            font=("Segoe UI", 14, "bold"),
            text_color=Colors.TEXT_PRIMARY
        ).pack(pady=(15, 5), padx=15, anchor="w")
        
        self.content_text = ctk.CTkTextbox(
            right_card,
            height=100,
            font=("Consolas", 11),
            fg_color="#ffffff",
            text_color="#000000",
            corner_radius=Dimensions.CORNER_RADIUS_M,
            border_width=Dimensions.BORDER_WIDTH_THIN
        )
        self.content_text.pack(fill="x", padx=15, pady=(0, 15))
    
    def set_results(self, results: List[ValidationResult]):
        """Setzt neue Ergebnisse"""
        self.results = results
        self.current_page = 0
        self._update_display()
    
    def add_result(self, result: ValidationResult):
        """Fügt ein einzelnes Ergebnis hinzu (für Live-Updates)"""
        self.results.append(result)
        self.results.sort(key=lambda x: x.confidence, reverse=True)
        self._update_display()
    
    def clear(self):
        """Löscht alle Ergebnisse"""
        self.results = []
        self.current_page = 0
        self._update_display()
    
    def _update_display(self):
        """Aktualisiert die Anzeige"""
        # Lösche alte Einträge
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Update Titel
        self.title_label.configure(text=f"📊 Ergebnisse ({len(self.results)})")
        
        if not self.results:
            self.page_label.configure(text="0 / 0")
            self.btn_prev.configure(state="disabled")
            self.btn_next.configure(state="disabled")
            return
        
        # Berechne Pagination
        total_pages = (len(self.results) - 1) // self.ITEMS_PER_PAGE + 1
        start_idx = self.current_page * self.ITEMS_PER_PAGE
        end_idx = min(start_idx + self.ITEMS_PER_PAGE, len(self.results))
        
        # Füge Einträge hinzu
        for i in range(start_idx, end_idx):
            result = self.results[i]
            
            rank = i + 1
            confidence = f"{result.confidence:.1f}%"
            
            # Typ bestimmen
            if result.is_url:
                type_str = "🔗 URL"
            elif result.decoded_data:
                type_str = "📝 Text"
            else:
                type_str = "❓"
            
            content = result.decoded_data if result.decoded_data else "[N/A]"
            if len(content) > 60:
                content = content[:57] + "..."
            
            self.tree.insert("", "end", values=(rank, confidence, type_str, content), tags=(str(i),))
        
        # Update Pagination
        self.page_label.configure(text=f"{self.current_page + 1} / {total_pages}")
        self.btn_prev.configure(state="normal" if self.current_page > 0 else "disabled")
        self.btn_next.configure(state="normal" if self.current_page < total_pages - 1 else "disabled")
    
    def _prev_page(self):
        """Vorherige Seite"""
        if self.current_page > 0:
            self.current_page -= 1
            self._update_display()
    
    def _next_page(self):
        """Nächste Seite"""
        total_pages = (len(self.results) - 1) // self.ITEMS_PER_PAGE + 1
        if self.current_page < total_pages - 1:
            self.current_page += 1
            self._update_display()
    
    def _on_select(self, event):
        """Wenn ein Ergebnis ausgewählt wird"""
        selection = self.tree.selection()
        if not selection:
            return
        
        item = self.tree.item(selection[0])
        idx = int(item['tags'][0])
        result = self.results[idx]
        
        self._show_details(result)
        
        if self.on_result_selected:
            self.on_result_selected(result)
    
    def _show_details(self, result: ValidationResult):
        """Zeigt Details eines Ergebnisses"""
        # Confidence
        conf_value = result.confidence / 100.0
        self.confidence_bar.set(conf_value)
        self.confidence_label.configure(text=f"{result.confidence:.1f}%")
        
        # Farbe basierend auf Confidence
        if result.confidence >= 70:
            color = Colors.SUCCESS
        elif result.confidence >= 40:
            color = Colors.WARNING
        else:
            color = Colors.ERROR
        
        self.confidence_bar.configure(progress_color=color)
        self.confidence_label.configure(text_color=color)
        
        # Score Breakdown
        score_values = {
            'structure': result.structure_score,
            'pattern': result.pattern_score,
            'density': result.density_score,
            'decode': result.decode_score,
            'content': result.content_score
        }
        
        for key, (bar, label) in self.score_labels.items():
            value = score_values.get(key, 0) / 100.0
            bar.set(value)
            label.configure(text=f"{score_values.get(key, 0):.0f}%")
        
        # Content
        self.content_text.delete("1.0", "end")
        if result.decoded_data:
            self.content_text.insert("1.0", result.decoded_data)
        else:
            self.content_text.insert("1.0", "[Nicht dekodierbar]")
        
        # QR Preview
        try:
            img_array = np.uint8(255 - result.matrix * 255)
            img = Image.fromarray(img_array, mode='L')
            self.current_raw_image = img  # Store for popup
            
            # Calculate size ensuring it fits but maintaining aspect ratio (QR is square anyway)
            # Preview frame is height 200, so let's aim for ~180x180
            target_size = 180
            
            # Create CTkImage (High DPI supported)
            photo = ctk.CTkImage(
                light_image=img,
                dark_image=img,
                size=(target_size, target_size)
            )
            
            self.preview_label.configure(image=photo, text="", cursor="hand2")
            self.preview_label.image = photo
            
            # Bind Click
            self.preview_label.bind("<Button-1>", self._on_preview_click)
            
        except Exception as e:
            print(f"Preview Error: {e}")
            self.preview_label.configure(text=f"Vorschau-Fehler", image=None, cursor="")
            self.preview_label.unbind("<Button-1>")

    def _on_preview_click(self, event):
        """Opens the QR code in a large popup"""
        if not hasattr(self, 'current_raw_image') or not self.current_raw_image:
            return
            
        # Prevent multiple popups
        if hasattr(self, 'preview_popup') and self.preview_popup.winfo_exists():
            self.preview_popup.focus()
            return
            
        top = ctk.CTkToplevel(self)
        self.preview_popup = top # Store reference
        top.title("QR-Code Vorschau")
        top.geometry("650x700")
        
        # Make modal-like
        top.transient(self.winfo_toplevel())
        top.grab_set()
        
        # Container
        bg = ctk.CTkFrame(top, fg_color=Colors.BG_PRIMARY)
        bg.pack(fill="both", expand=True)

        # High-Res Image
        # Scale up nicely (e.g. 500px)
        # We use NEAREST for sharp pixels
        target_size = 500
        
        # Create scaled version for display
        # We scale the PIL image first using NEAREST to get sharp edges
        # Then we create a CTkImage from it.
        # But CTkImage also scales. 
        # Best practice for pixel art: Scale PIL image to target size using NEAREST, then pass to CTkImage.
        large_pil = self.current_raw_image.resize((target_size, target_size), Image.Resampling.NEAREST)
        
        large_photo = ctk.CTkImage(
            light_image=large_pil,
            dark_image=large_pil,
            size=(target_size, target_size)
        )
        
        lbl_img = ctk.CTkLabel(bg, text="", image=large_photo)
        lbl_img.pack(pady=40, padx=40, expand=True)
        
        # Buttons
        btn_frame = ctk.CTkFrame(bg, fg_color="transparent")
        btn_frame.pack(pady=(0, 40))
        
        ctk.CTkButton(
            btn_frame, 
            text="💾 Speichern", 
            command=lambda: self._save_preview_image(self.current_raw_image),
            fg_color=Colors.ACCENT,
            hover_color=Colors.ACCENT_HOVER,
            width=140
        ).pack(side="left", padx=10)
        
        ctk.CTkButton(
            btn_frame, 
            text="Schließen", 
            command=top.destroy,
            fg_color=Colors.BG_CARD,
            text_color=Colors.TEXT_PRIMARY,
            hover_color=Colors.BG_CARD_HOVER,
            width=140
        ).pack(side="left", padx=10)
        
        # Focus
        top.after(100, top.focus)

    def _save_preview_image(self, img):
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG Image", "*.png")],
            title="QR-Code speichern"
        )
        if path:
            # Scale up for saving (high quality)
            # Size 1000px is good
            large = img.resize((1000, 1000), Image.Resampling.NEAREST)
            large.save(path)
    
    def _on_export(self):
        """Exportiert Ergebnisse"""
        if not self.results:
            return
        
        from tkinter import filedialog
        import json
        from datetime import datetime
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("CSV", "*.csv"), ("Alle Dateien", "*.*")]
        )
        
        if not filename:
            return
        
        try:
            if filename.endswith('.json'):
                data = []
                for i, result in enumerate(self.results):
                    data.append({
                        'rank': i + 1,
                        'confidence': float(result.confidence),
                        'content': result.decoded_data,
                        'is_url': result.is_url,
                        'structure_score': float(result.structure_score),
                        'pattern_score': float(result.pattern_score),
                        'density_score': float(result.density_score),
                        'decode_score': float(result.decode_score),
                        'content_score': float(result.content_score)
                    })
                
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump({
                        'timestamp': datetime.now().isoformat(),
                        'total_results': len(data),
                        'results': data
                    }, f, indent=2, ensure_ascii=False)
            
            elif filename.endswith('.csv'):
                import csv
                with open(filename, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(['Rank', 'Confidence', 'Is_URL', 'Content', 'Structure', 'Pattern', 'Density', 'Decode', 'Content_Score'])
                    
                    for i, result in enumerate(self.results):
                        writer.writerow([
                            i + 1,
                            f"{result.confidence:.2f}",
                            result.is_url,
                            result.decoded_data or "",
                            f"{result.structure_score:.1f}",
                            f"{result.pattern_score:.1f}",
                            f"{result.density_score:.1f}",
                            f"{result.decode_score:.1f}",
                            f"{result.content_score:.1f}"
                        ])
            
            print(f"✓ Exportiert nach: {filename}")
        
        except Exception as e:
            print(f"Export-Fehler: {e}")

    def _show_score_help(self):
        """Zeigt Details zur Score-Berechnung"""
        if hasattr(self, 'score_help_popup') and self.score_help_popup.winfo_exists():
            self.score_help_popup.focus()
            return

        top = ctk.CTkToplevel(self)
        self.score_help_popup = top
        top.title("Wie wird der Score berechnet?")
        top.geometry("500x700")
        
        # Modal
        top.transient(self.winfo_toplevel())
        
        # Background
        bg = ctk.CTkFrame(top, fg_color=Colors.BG_PRIMARY)
        bg.pack(fill="both", expand=True)
        
        # Content Scrollable
        scroll = ctk.CTkScrollableFrame(bg, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Title
        ctk.CTkLabel(scroll, text="Score Berechnung", font=("Segoe UI", 20, "bold"), text_color=Colors.TEXT_PRIMARY).pack(anchor="w", pady=(0, 20))
        
        # Text
        desc = """Der Confidence Score ist ein gewichteter Durchschnitt aus verschiedenen Qualitätsmetriken. Hier ist, was sie bedeuten:

1. Struktur (Structure Score)
Prüft, ob die Grundbausteine eines QR-Codes vorhanden sind:
• Finder Patterns (Die 3 großen Quadrate)
• Alignment Patterns (Die kleinen Quadrate)
• Timing Patterns (Die gestrichelten Linien)
Ein niedriger Wert hier bedeutet, dass der Code "beschädigt" aussieht.

2. Muster (Pattern Score)
Analysiert die Verteilung von hellen und dunklen Modulen. Ein gültiger QR-Code folgt bestimmten statistischen Regeln.
Abweichungen deuten auf Rauschen oder falsche Pixel hin.

3. Dichte (Density Score)
Ein QR-Code hat typischerweise eine ausgeglichene Anzahl von schwarzen und weißen Modulen (~50:50). 
Starke Abweichungen (zu weiß oder zu schwarz) senken diesen Wert.

4. Dekodierung (Decode Score)
Dies ist der wichtigste Test. Wir versuchen, den Code mit einer Standard-Bibliothek (pyzbar) zu lesen.
• 100% = Code ist lesbar!
• 0% = Code konnte nicht gelesen werden.

5. Inhalt (Content Score)
Falls dekodiert, bewerten wir den Inhalt:
• Sieht es aus wie eine URL? (Pluspunkte)
• Sind es nur zufällige Zeichen? (Minuspunkte)
• Visuell lesbare Zeichen (ASCII) sind besser als Binärmüll.

Gesamt-Score = 
  (Struktur * 1.0) +
  (Muster * 0.5) + 
  (Dichte * 0.3) + 
  (Decode * 2.0) +
  (Inhalt * 0.5)
------------------------
  Summe der Gewichte

Ein Score über 80% bedeutet meistens einen Erfolg!
"""
        
        lbl = ctk.CTkLabel(
            scroll, 
            text=desc, 
            font=("Segoe UI", 12), 
            text_color=Colors.TEXT_PRIMARY, 
            justify="left",
            wraplength=420
        )
        lbl.pack(anchor="w")
        
        # Close
        ctk.CTkButton(
            bg, 
            text="Verstanden", 
            command=top.destroy,
            fg_color=Colors.ACCENT,
            text_color="#ffffff",
            hover_color=Colors.ACCENT_HOVER,
            width=200
        ).pack(pady=20)
