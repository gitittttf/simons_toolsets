import customtkinter as ctk
import os
import pkgutil
import importlib
import inspect
import sys
from typing import Dict, Type
from PIL import Image, ImageTk

# Fix imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from core.base_tool import BaseTool

# --- THEME CONFIG ---
class HubColors:
    BG_DARK = "#0f172a"      # Deep Navy/Black
    BG_CARD = "#1e293b"      # Card Background
    BG_HOVER = "#334155"     # Hover
    TEXT_MAIN = "#f8fafc"    # White
    TEXT_SUB = "#94a3b8"     # Gray
    ACCENT = "#38bdf8"       # Sky Blue
    BORDER = "#334155"       # Border

class ToolHub(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # Setup Window
        self.title("Simon's Toolset Hub")
        self.geometry("1100x700")
        self.minsize(800, 600)
        
        # Theme
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.configure(fg_color=HubColors.BG_DARK)
        
        # State
        self.tools: Dict[str, BaseTool] = {}
        self.running_apps: Dict[str, BaseTool] = {}  # name -> tool_instance (mit .window)
        
        # UI
        self._build_sidebar()
        self._build_main_area()
        
        # Discover Tools
        self._discover_tools()
        self._render_tools()
        
        # Exit Handler
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, width=250, fg_color=HubColors.BG_CARD, corner_radius=0)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        
        # Logo / Title
        ctk.CTkLabel(
            self.sidebar, 
            text="🛠 Toolset Hub", 
            font=("Segoe UI", 24, "bold"),
            text_color=HubColors.TEXT_MAIN
        ).pack(pady=(40, 10), padx=20, anchor="w")
        
        ctk.CTkLabel(
            self.sidebar, 
            text="v2.0 • Hub Edition", 
            font=("Segoe UI", 12),
            text_color=HubColors.TEXT_SUB
        ).pack(pady=(0, 40), padx=20, anchor="w")
        
        # Stats
        self.lbl_running = ctk.CTkLabel(self.sidebar, text="Active Apps: 0", font=("Segoe UI", 12), text_color=HubColors.ACCENT)
        self.lbl_running.pack(side="bottom", pady=20, padx=20, anchor="w")

    def _build_main_area(self):
        self.main_area = ctk.CTkFrame(self, fg_color="transparent")
        self.main_area.pack(side="right", fill="both", expand=True, padx=30, pady=30)
        
        ctk.CTkLabel(
            self.main_area, 
            text="Available Tools", 
            font=("Segoe UI", 20, "bold"),
            text_color=HubColors.TEXT_MAIN
        ).pack(anchor="w", pady=(0, 20))
        
        self.grid_frame = ctk.CTkFrame(self.main_area, fg_color="transparent")
        self.grid_frame.pack(fill="both", expand=True)

    def _discover_tools(self):
        """Scans 'tools' directory for BaseTool implementations"""
        tools_path = os.path.join(os.path.dirname(__file__), 'tools')
        if not os.path.exists(tools_path):
            os.makedirs(tools_path)

        for _, name, ispkg in pkgutil.iter_modules([tools_path]):
            if ispkg:
                try:
                    module = importlib.import_module(f'tools.{name}.tool')
                    for item_name, item_obj in inspect.getmembers(module):
                        if (inspect.isclass(item_obj) and 
                            issubclass(item_obj, BaseTool) and 
                            item_obj is not BaseTool):
                            
                            # Instantiate
                            tool_instance = item_obj()
                            self.tools[tool_instance.name] = tool_instance
                            print(f"Loaded: {tool_instance.name}")
                except Exception as e:
                    print(f"Error loading {name}: {e}")

    def _render_tools(self):
        # Clear
        for w in self.grid_frame.winfo_children():
            w.destroy()
            
        row = 0
        col = 0
        
        for name, tool in self.tools.items():
            self._create_tool_card(tool, row, col)
            col += 1
            if col > 2: # 3 Columns
                col = 0
                row += 1

    def _create_tool_card(self, tool, row, col):
        card = ctk.CTkFrame(
            self.grid_frame, 
            fg_color=HubColors.BG_CARD, 
            corner_radius=15,
            border_width=1,
            border_color=HubColors.BORDER
        )
        card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
        
        # Icon (Placeholder)
        ctk.CTkLabel(
            card, text="📦", font=("Segoe UI", 32)
        ).pack(pady=(20, 10))
        
        # Title
        ctk.CTkLabel(
            card, text=tool.name, font=("Segoe UI", 16, "bold"), text_color=HubColors.TEXT_MAIN
        ).pack(pady=(0, 5))
        
        # Desc
        ctk.CTkLabel(
            card, text=tool.description, font=("Segoe UI", 12), 
            text_color=HubColors.TEXT_SUB,
            wraplength=200
        ).pack(pady=(0, 20), padx=10)
        
        # Button
        ctk.CTkButton(
            card, 
            text="Open", 
            command=lambda t=tool: self._launch_app(t),
            fg_color=HubColors.ACCENT,
            hover_color="#0ea5e9",
            text_color=HubColors.BG_DARK
        ).pack(pady=(0, 20))

    def _launch_app(self, tool):
        # Check if already running
        if tool.name in self.running_apps:
            print(f"Restoring {tool.name}...")
            # Bring to front
            try:
                # If minimized/hidden
                tool.window.deiconify()
                tool.window.lift()
                tool.window.focus_force()
                return
            except Exception as e:
                print(f"Window was gone: {e}")
                del self.running_apps[tool.name]
        
        # Launch new
        print(f"Launching {tool.name}...")
        try:
            window = tool.launch_gui(self)
            
            # Hook into window close event to just HIDE instead of destroy
            # This implements the "Phone App" behavior
            window.protocol("WM_DELETE_WINDOW", lambda t=tool: self._minimize_app(t))
            
            self.running_apps[tool.name] = tool
            self._update_stats()
            
        except Exception as e:
            print(f"Failed to launch: {e}")
            import traceback
            traceback.print_exc()

    def _minimize_app(self, tool):
        """Hides the app instead of closing it"""
        print(f"Minimizing {tool.name}...")
        tool.window.withdraw() # Hide
        
    def _update_stats(self):
        count = len(self.running_apps)
        self.lbl_running.configure(text=f"Active Apps: {count}")

    def _on_close(self):
        """Clean shutdown of Hub and all Apps"""
        print("Shutting down Hub...")
        
        for name, tool in self.running_apps.items():
            try:
                print(f"Closing {name}...")
                tool.cleanup() # Stop threads
                tool.window.destroy() # Destroy window
            except Exception as e:
                print(f"Error closing {name}: {e}")
        
        self.destroy() # Close Hub
        sys.exit(0)

if __name__ == "__main__":
    app = ToolHub()
    app.mainloop()
