"""
Enterprise Architect Visual Design Rules, Dimension Standards, and Corporate Styling.
Follows the classic Sparx Systems Enterprise Architect corporate aesthetic.
"""

from typing import Dict, List, Optional, Tuple


def hex_to_ea_color(hex_str: str) -> int:
    """Converts a hex color string ('#RRGGBB' or 'RRGGBB') to Windows COLORREF integer."""
    hex_clean = hex_str.lstrip("#")
    if len(hex_clean) != 6:
        return 0
    r = int(hex_clean[0:2], 16)
    g = int(hex_clean[2:4], 16)
    b = int(hex_clean[4:6], 16)
    return r + (g << 8) + (b << 16)


# ------------------------------------------------------------------------------
# 1. Standard Element Canonical Dimensions (Width, Height) in Pixels
# ------------------------------------------------------------------------------
ELEMENT_CANONICAL_DIMENSIONS = {
    "Action": {"width": 170, "height": 55},
    "Decision": {"width": 55, "height": 42},
    "MergeNode": {"width": 55, "height": 42},
    "StateNode": {"width": 25, "height": 25},      # Initial / Final circle
    "ActivityInitial": {"width": 22, "height": 22},
    "ActivityFinal": {"width": 26, "height": 26},
    "Synchronization": {"width": 140, "height": 8}, # Fork / Join bar
    "Class": {"width": 170, "height": 90},
    "Interface": {"width": 170, "height": 80},
    "UseCase": {"width": 145, "height": 60},
    "Actor": {"width": 45, "height": 75},
    "Component": {"width": 160, "height": 75},
    "Object": {"width": 150, "height": 65},
    "Note": {"width": 160, "height": 70},
}

# ------------------------------------------------------------------------------
# 2. Classic Enterprise Architect Corporate Palette
# ------------------------------------------------------------------------------
CLASSIC_EA_PALETTE = {
    "Action": {
        "bg_color": hex_to_ea_color("#FFF8DB"),      # Soft cream / light gold
        "border_color": hex_to_ea_color("#5C4B14"),  # Warm dark brown
        "border_width": 1,
    },
    "Decision": {
        "bg_color": hex_to_ea_color("#DCF3D8"),      # Soft pastel green
        "border_color": hex_to_ea_color("#2E6930"),  # Forest olive green
        "border_width": 1,
    },
    "MergeNode": {
        "bg_color": hex_to_ea_color("#DCF3D8"),
        "border_color": hex_to_ea_color("#2E6930"),
        "border_width": 1,
    },
    "Class": {
        "bg_color": hex_to_ea_color("#F2F6FC"),      # Soft corporate blue/white
        "border_color": hex_to_ea_color("#29487D"),  # Slate blue
        "border_width": 1,
    },
    "Interface": {
        "bg_color": hex_to_ea_color("#EBF7EE"),      # Mint tint
        "border_color": hex_to_ea_color("#1C6B28"),
        "border_width": 1,
    },
    "UseCase": {
        "bg_color": hex_to_ea_color("#FAF0DE"),      # Warm beige
        "border_color": hex_to_ea_color("#7A4D00"),
        "border_width": 1,
    },
}

# ------------------------------------------------------------------------------
# 3. Layout Spacing Grid Constants (for Vertical Flow Pipelines)
# ------------------------------------------------------------------------------
GRID_CONSTANTS = {
    "LANE_WIDTH": 250,              # Standard width of each vertical swimlane/actor lane
    "LANE_PADDING": 40,             # Left margin before first lane starts
    "START_TOP": -70,               # Initial Y offset from top of diagram
    "STEP_VERTICAL_GAP": 55,        # Vertical distance between consecutive flow steps
    "DECISION_BRANCH_GAP": 45,      # Vertical gap from decision to branched actions
    "MAX_ACTION_TEXT_CHARS": 32,    # Character count before wrapping text or widening
}


CONTAINER_TYPES = {
    "ActivityPartition",
    "Partition",
    "Boundary",
    "Package",
    "Lane",
    "Swimlane",
}


def get_element_dimensions(element_type: str, text_length: int = 0) -> Tuple[int, int]:
    """Returns canonical (width, height) for an element type, dynamically adjusted if long text."""
    if element_type in CONTAINER_TYPES:
        return 0, 0

    spec = ELEMENT_CANONICAL_DIMENSIONS.get(element_type, {"width": 160, "height": 60})
    w = spec["width"]
    h = spec["height"]

    # If text is exceptionally long for an action, expand height to fit
    if element_type in ["Action", "Class"] and text_length > 60:
        h = max(h, 75)
    if element_type in ["Action", "Class"] and text_length > 100:
        h = max(h, 95)
        w = max(w, 190)

    return w, h


def build_style_string(
    existing_style: str = "",
    bg_color: Optional[int] = None,
    border_color: Optional[int] = None,
    border_width: Optional[int] = None,
) -> str:
    """Updates or injects BCol, LCol, LWth in an EA DiagramObject.Style string."""
    parts = {}
    if existing_style:
        for item in existing_style.split(";"):
            if "=" in item:
                k, v = item.split("=", 1)
                parts[k.strip()] = v.strip()

    if bg_color is not None:
        parts["BCol"] = str(bg_color)
    if border_color is not None:
        parts["LCol"] = str(border_color)
    if border_width is not None:
        parts["LWth"] = str(border_width)

    return ";".join([f"{k}={v}" for k, v in parts.items()]) + ";"
