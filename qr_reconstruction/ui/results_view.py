"""
Results View - Zeigt Bruteforce-Ergebnisse in sortierter Tabelle
"""

import customtkinter as ctk
from typing import List, Callable, Optional
from tkinter import ttk
import tkinter as tk
from PIL import Image, ImageTk
import numpy as np
from ..core.validator import ValidationResult


class ResultsView(ctk.CTkFrame):
    """
    Zeigt Rekonstruktions-Ergebnisse als sortierte Tabelle
    
    Features:
    - Sortiert nach Confidence
    - Paginierung (100 Ergebnisse pro Seite)
    - Export-Funktion
    - Detail-Ansicht mit QR-Code-Preview
    """
    
    ITEMS_PER_PAGE = 100
    
    def __init__(self, parent):
        super().__init__(parent)
        
        self.results: List[ValidationResult] = []
        self.current_page = 0
        self.on_result_selected: Optional[Callable[[ValidationResult], None]] = None
        
        self._build_ui()
    
    def _build_ui(self):
        """Baut die UI auf"""
        # Header
        header_frame = ctk.CTkFrame(self)
        header_frame.pack(fill="x", padx=10, pady=10)
        
        self.title_label = ctk.CTkLabel(
            header_frame,
            text="Ergebnisse (0)",
            font=("Arial", 18, "bold")
        )
        self.title_label.pack(side="left", padx=10)
        
        # Export-Button
        self.btn_export = ctk.CTkButton(
            header_frame,
            text="💾 Exportieren",
            command=self._on_export,
            width=120
        )
        self.btn_export.pack(side="right", padx=10)
        
        # Tabelle
        table_frame = ctk.CTkFrame(self)
        table_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(table_frame)
        scrollbar.pack(side="right", fill="y")
        
        # Treeview (Tabelle)
        columns = ("rank", "confidence", "content")
        self.tree = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings",
            yscrollcommand=scrollbar.set,
            height=20
        )
        
        # Spalten konfigurieren
        self.tree.heading("rank", text="#")
        self.tree.heading("confidence", text="Confidence")
        self.tree.heading("content", text="Inhalt")
        
        self.tree.column("rank", width=50, anchor="center")
        self.tree.column("confidence", width=120, anchor="center")
        self.tree.column("content", width=500, anchor="w")
        
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self.tree.yview)
        
        # Bind Selection
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        
        # Pagination Controls
        pagination_frame = ctk.CTkFrame(self)
        pagination_frame.pack(fill="x", padx=10, pady=10)
        
        self.btn_prev = ctk.CTkButton(
            pagination_frame,
            text="◀ Zurück",
            command=self._prev_page,
            width=100,
            state="disabled"
        )
        self.btn_prev.pack(side="left", padx=5)
        
        self.page_label = ctk.CTkLabel(
            pagination_frame,
            text="Seite 0 / 0",
            font=("Arial", 12)
        )
        self.page_label.pack(side="left", padx=20)
        
        self.btn_next = ctk.CTkButton(
            pagination_frame,
            text="Weiter ▶",
            command=self._next_page,
            width=100,
            state="disabled"
        )
        self.btn_next.pack(side="left", padx=5)
        
        # Detail-Frame (rechts)
        self.detail_frame = ctk.CTkFrame(self)
        self.detail_frame.pack(side="right", fill="y", padx=10, pady=10)
        
        ctk.CTkLabel(
            self.detail_frame,
            text="Details",
            font=("Arial", 14, "bold")
        ).pack(pady=10)
        
        self.detail_text = ctk.CTkTextbox(
            self.detail_frame,
            width=250,
            height=300,
            font=("Courier", 10)
        )
        self.detail_text.pack(padx=10, pady=10)
        
        # QR-Code Preview
        self.preview_label = ctk.CTkLabel(
            self.detail_frame,
            text=""
        )
        self.preview_label.pack(pady=10)
    
    def set_results(self, results: List[ValidationResult]):
        """
        Setzt neue Ergebnisse
        
        Args:
            results: Liste von ValidationResult (sollte bereits sortiert sein)
        """
        self.results = results
        self.current_page = 0
        self._update_display()
    
    def add_result(self, result: ValidationResult):
        """Fügt ein einzelnes Ergebnis hinzu (für Live-Updates)"""
        self.results.append(result)
        # Re-sortiere
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
        self.title_label.configure(text=f"Ergebnisse ({len(self.results)})")
        
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
            content = result.decoded_data if result.decoded_data else "[Nicht dekodierbar]"
            
            # Kürze langen Content
            if len(content) > 80:
                content = content[:77] + "..."
            
            self.tree.insert("", "end", values=(rank, confidence, content), tags=(str(i),))
        
        # Update Pagination Controls
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
        
        # Update Details
        self._show_details(result)
        
        # Callback
        if self.on_result_selected:
            self.on_result_selected(result)
    
    def _show_details(self, result: ValidationResult):
        """Zeigt Details eines Ergebnisses"""
        # Text
        details = f"""
Confidence: {result.confidence:.2f}%

Struktur: {result.structure_score:.1f}%
Muster: {result.pattern_score:.1f}%
Dichte: {result.density_score:.1f}%
Dekodierung: {result.decode_score:.1f}%

Inhalt:
{result.decoded_data if result.decoded_data else '[Nicht dekodierbar]'}
"""
        
        self.detail_text.delete("1.0", "end")
        self.detail_text.insert("1.0", details)
        
        # QR-Code Preview
        try:
            # Erstelle PIL Image aus Matrix
            img_array = np.uint8(255 - result.matrix * 255)
            img = Image.fromarray(img_array, mode='L')
            
            # Scale up
            scale = 5
            img = img.resize((result.matrix.shape[1] * scale, result.matrix.shape[0] * scale), Image.NEAREST)
            
            # Konvertiere zu PhotoImage
            photo = ImageTk.PhotoImage(img)
            self.preview_label.configure(image=photo)
            self.preview_label.image = photo  # Keep reference
        
        except Exception as e:
            print(f"Preview-Fehler: {e}")
    
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
                # JSON Export
                data = []
                for i, result in enumerate(self.results):
                    data.append({
                        'rank': i + 1,
                        'confidence': float(result.confidence),
                        'content': result.decoded_data,
                        'structure_score': float(result.structure_score),
                        'pattern_score': float(result.pattern_score),
                        'density_score': float(result.density_score),
                        'decode_score': float(result.decode_score)
                    })
                
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump({
                        'timestamp': datetime.now().isoformat(),
                        'total_results': len(data),
                        'results': data
                    }, f, indent=2, ensure_ascii=False)
            
            elif filename.endswith('.csv'):
                # CSV Export
                import csv
                with open(filename, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(['Rank', 'Confidence', 'Content', 'Structure', 'Pattern', 'Density', 'Decode'])
                    
                    for i, result in enumerate(self.results):
                        writer.writerow([
                            i + 1,
                            f"{result.confidence:.2f}",
                            result.decoded_data or "",
                            f"{result.structure_score:.1f}",
                            f"{result.pattern_score:.1f}",
                            f"{result.density_score:.1f}",
                            f"{result.decode_score:.1f}"
                        ])
            
            print(f"✓ Exportiert nach: {filename}")
        
        except Exception as e:
            print(f"Export-Fehler: {e}")