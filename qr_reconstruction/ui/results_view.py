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


# =============================================================================
# FARBEN (synchron mit main_window.py)
# =============================================================================
class Colors:
    """Farbdefinitionen"""
    
    BG_PRIMARY = "#0f0f1a"
    BG_SECONDARY = "#1a1a2e"
    BG_CARD = "#252540"
    BG_CARD_HOVER = "#303055"
    
    ACCENT = "#00d4aa"
    ACCENT_SECONDARY = "#6366f1"
    
    TEXT_PRIMARY = "#ffffff"
    TEXT_SECONDARY = "#a0a0b0"
    TEXT_MUTED = "#606070"
    
    SUCCESS = "#00ff88"
    WARNING = "#ffaa00"
    ERROR = "#ff4466"
    
    BORDER = "#303050"


class ResultsView(ctk.CTkFrame):
    """
    Zeigt Rekonstruktions-Ergebnisse mit modernem Design
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
            fg_color=Colors.BG_CARD,
            corner_radius=16,
            border_width=1,
            border_color=Colors.BORDER
        )
        left_card.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=0)
        
        # Header
        header_frame = ctk.CTkFrame(left_card, fg_color="transparent")
        header_frame.pack(fill="x", padx=20, pady=15)
        
        self.title_label = ctk.CTkLabel(
            header_frame,
            text="📋 Ergebnisse (0)",
            font=("Segoe UI", 18, "bold"),
            text_color=Colors.TEXT_PRIMARY
        )
        self.title_label.pack(side="left")
        
        # Export Button
        self.btn_export = ctk.CTkButton(
            header_frame,
            text="💾 Export",
            command=self._on_export,
            width=100,
            height=32,
            font=("Segoe UI", 11),
            fg_color=Colors.BG_SECONDARY,
            hover_color=Colors.BG_CARD_HOVER,
            text_color=Colors.TEXT_PRIMARY,
            corner_radius=16
        )
        self.btn_export.pack(side="right")
        
        # Table Frame
        table_container = ctk.CTkFrame(left_card, fg_color=Colors.BG_SECONDARY, corner_radius=12)
        table_container.pack(fill="both", expand=True, padx=15, pady=(0, 10))
        
        # Style für Treeview (Dark Theme)
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Dark.Treeview",
            background=Colors.BG_SECONDARY,
            foreground=Colors.TEXT_PRIMARY,
            fieldbackground=Colors.BG_SECONDARY,
            borderwidth=0,
            font=("Segoe UI", 11)
        )
        style.configure(
            "Dark.Treeview.Heading",
            background=Colors.BG_CARD,
            foreground=Colors.TEXT_PRIMARY,
            borderwidth=0,
            font=("Segoe UI", 11, "bold")
        )
        style.map("Dark.Treeview", background=[('selected', Colors.ACCENT_SECONDARY)])
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(table_container)
        scrollbar.pack(side="right", fill="y", pady=5)
        
        # Treeview
        columns = ("rank", "confidence", "type", "content")
        self.tree = ttk.Treeview(
            table_container,
            columns=columns,
            show="headings",
            yscrollcommand=scrollbar.set,
            height=18,
            style="Dark.Treeview"
        )
        
        # Spalten konfigurieren
        self.tree.heading("rank", text="#")
        self.tree.heading("confidence", text="Confidence")
        self.tree.heading("type", text="Typ")
        self.tree.heading("content", text="Inhalt")
        
        self.tree.column("rank", width=50, anchor="center")
        self.tree.column("confidence", width=100, anchor="center")
        self.tree.column("type", width=80, anchor="center")
        self.tree.column("content", width=400, anchor="w")
        
        self.tree.pack(side="left", fill="both", expand=True, pady=5, padx=5)
        scrollbar.config(command=self.tree.yview)
        
        # Bind Selection
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        
        # Pagination
        pagination_frame = ctk.CTkFrame(left_card, fg_color="transparent")
        pagination_frame.pack(fill="x", padx=20, pady=10)
        
        self.btn_prev = ctk.CTkButton(
            pagination_frame,
            text="◀ Zurück",
            command=self._prev_page,
            width=90,
            height=30,
            font=("Segoe UI", 11),
            fg_color=Colors.BG_SECONDARY,
            hover_color=Colors.BG_CARD_HOVER,
            text_color=Colors.TEXT_SECONDARY,
            corner_radius=15,
            state="disabled"
        )
        self.btn_prev.pack(side="left", padx=5)
        
        self.page_label = ctk.CTkLabel(
            pagination_frame,
            text="Seite 0 / 0",
            font=("Segoe UI", 11),
            text_color=Colors.TEXT_MUTED
        )
        self.page_label.pack(side="left", padx=15)
        
        self.btn_next = ctk.CTkButton(
            pagination_frame,
            text="Weiter ▶",
            command=self._next_page,
            width=90,
            height=30,
            font=("Segoe UI", 11),
            fg_color=Colors.BG_SECONDARY,
            hover_color=Colors.BG_CARD_HOVER,
            text_color=Colors.TEXT_SECONDARY,
            corner_radius=15,
            state="disabled"
        )
        self.btn_next.pack(side="left", padx=5)
        
        # Right Side: Details Card
        right_card = ctk.CTkFrame(
            self,
            fg_color=Colors.BG_CARD,
            corner_radius=16,
            border_width=1,
            border_color=Colors.BORDER
        )
        right_card.grid(row=0, column=1, sticky="nsew", padx=(10, 0), pady=0)
        
        # Details Header
        ctk.CTkLabel(
            right_card,
            text="🔍 Details",
            font=("Segoe UI", 16, "bold"),
            text_color=Colors.TEXT_PRIMARY
        ).pack(pady=(20, 15), padx=20, anchor="w")
        
        # QR Preview Frame
        preview_frame = ctk.CTkFrame(
            right_card,
            fg_color=Colors.BG_SECONDARY,
            corner_radius=12,
            height=180
        )
        preview_frame.pack(fill="x", padx=15, pady=5)
        preview_frame.pack_propagate(False)
        
        self.preview_label = ctk.CTkLabel(
            preview_frame,
            text="Wähle ein Ergebnis",
            font=("Segoe UI", 11),
            text_color=Colors.TEXT_MUTED
        )
        self.preview_label.pack(expand=True)
        
        # Confidence Display
        self.confidence_frame = ctk.CTkFrame(
            right_card,
            fg_color=Colors.BG_SECONDARY,
            corner_radius=12
        )
        self.confidence_frame.pack(fill="x", padx=15, pady=10)
        
        ctk.CTkLabel(
            self.confidence_frame,
            text="Confidence",
            font=("Segoe UI", 12, "bold"),
            text_color=Colors.TEXT_SECONDARY
        ).pack(pady=(10, 5), padx=15, anchor="w")
        
        self.confidence_bar = ctk.CTkProgressBar(
            self.confidence_frame,
            height=8,
            fg_color=Colors.BG_CARD,
            progress_color=Colors.ACCENT
        )
        self.confidence_bar.pack(fill="x", padx=15, pady=5)
        self.confidence_bar.set(0)
        
        self.confidence_label = ctk.CTkLabel(
            self.confidence_frame,
            text="0%",
            font=("Segoe UI", 24, "bold"),
            text_color=Colors.ACCENT
        )
        self.confidence_label.pack(pady=(5, 15))
        
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
                font=("Segoe UI", 10),
                text_color=Colors.TEXT_MUTED,
                width=80
            ).pack(side="left")
            
            bar = ctk.CTkProgressBar(
                row,
                height=6,
                fg_color=Colors.BG_SECONDARY,
                progress_color=Colors.ACCENT_SECONDARY,
                width=100
            )
            bar.pack(side="left", padx=5)
            bar.set(0)
            
            val_label = ctk.CTkLabel(
                row,
                text="0%",
                font=("Segoe UI", 10),
                text_color=Colors.TEXT_SECONDARY,
                width=40
            )
            val_label.pack(side="left")
            
            self.score_labels[key] = (bar, val_label)
        
        # Content Preview
        ctk.CTkLabel(
            right_card,
            text="Inhalt",
            font=("Segoe UI", 12, "bold"),
            text_color=Colors.TEXT_SECONDARY
        ).pack(pady=(15, 5), padx=20, anchor="w")
        
        self.content_text = ctk.CTkTextbox(
            right_card,
            height=100,
            font=("Consolas", 10),
            fg_color=Colors.BG_SECONDARY,
            text_color=Colors.TEXT_PRIMARY,
            corner_radius=10
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
        self.title_label.configure(text=f"📋 Ergebnisse ({len(self.results)})")
        
        if not self.results:
            self.page_label.configure(text="Seite 0 / 0")
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
                type_str = "🌐 URL"
            elif result.decoded_data:
                type_str = "📝 Text"
            else:
                type_str = "❓"
            
            content = result.decoded_data if result.decoded_data else "[Nicht dekodierbar]"
            if len(content) > 60:
                content = content[:57] + "..."
            
            self.tree.insert("", "end", values=(rank, confidence, type_str, content), tags=(str(i),))
        
        # Update Pagination
        self.page_label.configure(text=f"Seite {self.current_page + 1} / {total_pages}")
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
            
            # Scale
            scale = 6
            img = img.resize(
                (result.matrix.shape[1] * scale, result.matrix.shape[0] * scale),
                Image.Resampling.NEAREST
            )
            
            photo = ImageTk.PhotoImage(img)
            self.preview_label.configure(image=photo, text="")
            self.preview_label.image = photo
        except Exception as e:
            self.preview_label.configure(text=f"Vorschau-Fehler", image=None)
    
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