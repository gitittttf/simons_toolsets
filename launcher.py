import os
import sys
import importlib
import pkgutil
import inspect
import tkinter as tk
from tkinter import messagebox
from typing import List, Type
import customtkinter as ctk

# Füge Root zum Path hinzu
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.base_tool import BaseTool

class Launcher(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("Simon's Toolset Launcher")
        self.geometry("800x600")
        
        # Theme Setup
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        self.tools: List[Type[BaseTool]] = []
        self._discover_tools()
        
        self._build_ui()
        
    def _discover_tools(self):
        """Findet automatisch alle Tools im 'tools' Ordner"""
        tools_path = os.path.join(os.path.dirname(__file__), "tools")
        
        if not os.path.exists(tools_path):
            os.makedirs(tools_path)
            return

        # Iteriere durch alle Unterordner in 'tools'
        for _, name, ispkg in pkgutil.iter_modules([tools_path]):
            if ispkg:
                try:
                    # Importiere das Modul
                    module = importlib.import_module(f"tools.{name}.tool")
                    
                    # Suche nach BaseTool-Implementierungen
                    for item_name, item in inspect.getmembers(module):
                        if (inspect.isclass(item) and 
                            issubclass(item, BaseTool) and 
                            item is not BaseTool):
                            self.tools.append(item)
                            print(f"Tool gefunden: {item_name}")
                except ImportError as e:
                    print(f"Konnte Tool '{name}' nicht laden: {e}")
                except Exception as e:
                    print(f"Fehler beim Laden von Tool '{name}': {e}")

    def _build_ui(self):
        # Header
        header = ctk.CTkFrame(self, height=80, corner_radius=0)
        header.pack(fill="x")
        
        ctk.CTkLabel(
            header, 
            text="Simon's Toolset Collection", 
            font=("Roboto", 24, "bold")
        ).pack(pady=20)
        
        # Content
        content = ctk.CTkScrollableFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=20, pady=20)
        
        if not self.tools:
            ctk.CTkLabel(content, text="Keine Tools gefunden.", font=("Roboto", 16)).pack(pady=50)
            return
            
        for ToolClass in self.tools:
            # Instanziere Tool um Infos zu bekommen
            # (Wir machen das hier lazy, aber für den Launcher ist es ok)
            try:
                # Wir instanzieren es nicht wirklich komplett, sondern nutzen die Properties
                # Da Properties auf der Klasse ohne Instanz schwierig sind wenn sie abstract sind,
                # instanzieren wir es. BaseTool __init__ ist leer.
                tool_instance = ToolClass()
                self._create_tool_card(content, tool_instance)
            except Exception as e:
                print(f"Fehler beim Anzeigen von {ToolClass}: {e}")

    def _create_tool_card(self, parent, tool: BaseTool):
        card = ctk.CTkFrame(parent, corner_radius=10)
        card.pack(fill="x", pady=10)
        
        # Info
        info_frame = ctk.CTkFrame(card, fg_color="transparent")
        info_frame.pack(side="left", fill="both", expand=True, padx=15, pady=15)
        
        ctk.CTkLabel(
            info_frame, 
            text=tool.name, 
            font=("Roboto", 18, "bold"),
            anchor="w"
        ).pack(fill="x")
        
        ctk.CTkLabel(
            info_frame, 
            text=f"v{tool.version} • {tool.author}", 
            font=("Roboto", 12),
            text_color="gray",
            anchor="w"
        ).pack(fill="x")
        
        ctk.CTkLabel(
            info_frame, 
            text=tool.description, 
            font=("Roboto", 14),
            wraplength=500,
            anchor="w"
        ).pack(fill="x", pady=(5, 0))
        
        # Button
        btn = ctk.CTkButton(
            card, 
            text="Starten", 
            width=100, 
            height=40,
            command=lambda: self._launch_tool(tool)
        )
        btn.pack(side="right", padx=15)

    def _launch_tool(self, tool: BaseTool):
        self.withdraw()  # Hide launcher
        try:
            print(f"Starte {tool.name}...")
            tool.run()
        except Exception as e:
            messagebox.showerror("Fehler", f"Tool abgestürzt:\n{e}")
            import traceback
            traceback.print_exc()
        finally:
            self.deiconify() # Show launcher again when tool closes

if __name__ == "__main__":
    app = Launcher()
    app.mainloop()
