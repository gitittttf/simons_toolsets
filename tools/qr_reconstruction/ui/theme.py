"""
Central UI Theme Configuration for QR Reconstruction Tool
"""

class Colors:
    """Frutiger Aero Theme - Windows Vista/7 Style"""
    # Backgrounds
    BG_PRIMARY = "#e8f4fc"          # Soft Sky Blue (Main Window)
    BG_SECONDARY = "#ffffff"         # Pure White (Panels, Content)
    BG_CARD = "#f0f8ff"              # Alice Blue (Cards)
    BG_CARD_HOVER = "#dbeeff"        # Lighter Hover for Cards
    
    # Text
    TEXT_PRIMARY = "#1a1a2e"         # Dark Navy (Main Text)
    TEXT_SECONDARY = "#4a5568"       # Medium Grey (Subtitles)
    TEXT_MUTED = "#718096"           # Light Grey (Hints, Disabled)
    TEXT_INVERSE = "#ffffff"         # White Text (on Accents)

    # UI Branding / Accents
    ACCENT = "#0078d4"               # Vista Blue (Primary Actions)
    ACCENT_HOVER = "#006cbd"         # Darker Blue (Hover)
    ACCENT_SECONDARY = "#38b000"     # Vista Green (Secondary/Success)
    
    # Status Indicators
    SUCCESS = "#38b000"              # Fresh Green
    WARNING = "#f59e0b"              # Warm Orange
    ERROR = "#dc2626"                # Clear Red
    ERROR_HOVER = "#b91c1c"          # Darker Red

    # Borders & Dividers
    BORDER = "#b8d4e8"               # Soft Blue Border
    BORDER_LIGHT = "#ffffff"         # Highlight Border
    
    # QR Grid Specific Colors
    QR_BLACK = "#1a1a2e"             # Dark Navy (filled modules)
    QR_WHITE = "#f8fafc"             # Almost White (empty modules)
    QR_LOCKED_BLACK = "#0f172a"      # Deep Navy (locked filled)
    QR_LOCKED_WHITE = "#ffffff"      # Pure White (locked empty)
    
    QR_UNLOCKED_BORDER = "#94a3b8"   # Soft Grey (unlocked cell border)
    QR_GRID_LINE = "#999999"         # Visible Grey (grid lines for empty cells)
    QR_LOCKED_BORDER = "#0078d4"     # Vista Blue (locked cell border)
    QR_PATTERN_BORDER = "#38b000"    # Vista Green (fixed pattern border)
    
    QR_HOVER = "#60a5fa"             # Light Hover Blue
    QR_PAINTING = "#f97316"          # Orange (while painting)

class Fonts:
    """Standardized Typography"""
    FAMILY = "Segoe UI"
    MONO_FAMILY = "Consolas"
    
    TITLE = (FAMILY, 28, "bold")
    HEADING = (FAMILY, 18, "bold")
    SUBHEADING = (FAMILY, 12, "bold")
    
    BODY = (FAMILY, 12)
    BODY_BOLD = (FAMILY, 12, "bold")
    SMALL = (FAMILY, 11)
    
    BUTTON = (FAMILY, 12, "bold")
    BUTTON_LARGE = (FAMILY, 14, "bold")
    
    MONO = (MONO_FAMILY, 12, "bold")

class Dimensions:
    """UI Metrics and Spacing"""
    # Containers
    CORNER_RADIUS_L = 0 #15
    CORNER_RADIUS_M = 0 #12
    CORNER_RADIUS_S = 0 #6
    CORNER_RADIUS_NONE = 0
    
    # Spacing
    PADDING_XS = 5
    PADDING_S = 10
    PADDING_M = 15
    PADDING_L = 20
    PADDING_XL = 30
    
    # Components
    BUTTON_HEIGHT = 30
    BUTTON_HEIGHT_L = 40
    BUTTON_WIDTH_S = 100
    
    # Borders
    BORDER_WIDTH_THIN = 1
    BORDER_WIDTH_DEFAULT = 2
    BORDER_WIDTH_THICK = 3
    BORDER_WIDTH_NONE = 0
    
    # Grid Editor Specifics
    GRID_CELL_SIZE_DEFAULT = 22      # Default pixel size for one QR module
    
    # Grid Editor Canvas
    GRID_OUTER_BORDER_WIDTH = 3      # Width of the blue accent border around the QR code
    GRID_HIGHLIGHT_THICKNESS = 0     # Canvas highlight thickness (0 removes ugly default border)
    
    # Cell Rendering
    GRID_CELL_BORDER_THIN = 2        # Border width for unlocked cells
    GRID_CELL_BORDER_MEDIUM = 3      # Border width for locked/fixed cells
    GRID_CELL_BORDER_THICK = 4       # Border width for hovered/painting cells
    GRID_CELL_BORDER_NONE = 0        # No border (for simple mode or background)

    # Marker Sizes (Text)
    # These are dividers. Size = CellSize / DIVIDER
    GRID_MARKER_FIXED_DIVIDER = 3.0  # Denominator for 'x' marker size (smaller)
    GRID_MARKER_LOCKED_DIVIDER = 2.5 # Denominator for 'o' marker size (larger)
    GRID_MARKER_FONT = "Arial"       # Font family for cell markers
