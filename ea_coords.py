"""
Coordinate and layout helpers for Enterprise Architect diagrams.

EA Diagram Coordinate System:
- left: X coordinate of top-left corner (positive, increasing to the right)
- right: X coordinate of bottom-right corner (right = left + width)
- top: Y coordinate of top-left corner (typically negative in EA, e.g., -100)
- bottom: Y coordinate of bottom-right corner (bottom = top - height, e.g., -180)
"""

from typing import Any, Dict, List, Optional, Tuple

from ea_visual_rules import (
    GRID_CONSTANTS,
    get_element_dimensions,
)


def calculate_grid_positions(
    item_count: int,
    cols: int = 3,
    start_left: int = 80,
    start_top: int = -80,
    item_width: int = 150,
    item_height: int = 90,
    spacing_x: int = 60,
    spacing_y: int = 60,
) -> List[Dict[str, int]]:
    """Calculates grid coordinates (left, top, right, bottom) for N items."""
    positions = []
    for i in range(item_count):
        row = i // cols
        col = i % cols
        left = start_left + col * (item_width + spacing_x)
        top = start_top - row * (item_height + spacing_y)
        right = left + item_width
        bottom = top - item_height
        positions.append({
            "left": left,
            "top": top,
            "right": right,
            "bottom": bottom
        })
    return positions


def calculate_decision_waypoints(
    decision_box: Dict[str, int],
    target_box: Dict[str, int]
) -> str:
    """
    Calculates exact orthogonal waypoint (X:Y;) for a decision branch.
    Produces clean right-angled branching:
    Line exits horizontally from diamond side vertex (left/right) at decision_center_y,
    travels to target_center_x, and turns 90 degrees downward into the target element.
    """
    d_left = decision_box["left"]
    d_top = decision_box["top"]
    d_right = decision_box["right"]
    d_bottom = decision_box["bottom"]

    t_left = target_box["left"]
    t_top = target_box["top"]
    t_right = target_box["right"]
    t_bottom = target_box["bottom"]

    decision_center_y = int((d_top + d_bottom) / 2)
    decision_center_x = int((d_left + d_right) / 2)
    target_center_x = int((t_left + t_right) / 2)

    # If target is to the left or right of decision node
    if abs(target_center_x - decision_center_x) > 20:
        return f"{target_center_x}:{decision_center_y};"
    return ""


def layout_vertical_workflow(
    lanes: List[str],
    steps: List[Dict[str, Any]],
    lane_width: int = 250,
    lane_padding: int = 40,
    vertical_gap: int = 55,
    start_top: int = -70
) -> Dict[str, Any]:
    """
    Automated vertical workflow layout engine.
    Calculates flawless non-overlapping coordinates, swimlane distribution,
    and 90-degree orthogonal connections between consecutive steps and decision forks.
    """
    lane_map = {}
    for idx, lane_name in enumerate(lanes):
        l_x = lane_padding + idx * lane_width
        c_x = l_x + lane_width // 2
        lane_map[lane_name.lower().strip()] = {
            "index": idx,
            "name": lane_name,
            "left": l_x,
            "center_x": c_x,
            "width": lane_width
        }

    # If steps reference lanes by index
    for idx, lane_name in enumerate(lanes):
        lane_map[str(idx)] = lane_map[lane_name.lower().strip()]

    default_lane_key = lanes[0].lower().strip() if lanes else "0"

    placed_elements = {}
    current_y = start_top

    for step in steps:
        step_id = str(step.get("id", step.get("name")))
        name = step.get("name", "Paso")
        elem_type = step.get("type", "Action")
        lane_key = str(step.get("lane", default_lane_key)).lower().strip()
        lane_info = lane_map.get(lane_key, list(lane_map.values())[0])

        w, h = get_element_dimensions(elem_type, len(name))
        c_x = lane_info["center_x"]
        left = c_x - w // 2
        right = left + w
        top = current_y
        bottom = top - h

        placed_elements[step_id] = {
            "id": step_id,
            "name": name,
            "type": elem_type,
            "lane": lane_info["name"],
            "left": left,
            "top": top,
            "right": right,
            "bottom": bottom,
            "width": w,
            "height": h,
            "center_x": c_x,
            "center_y": (top + bottom) // 2
        }

        # Advance vertical cursor
        current_y = bottom - vertical_gap

    # Calculate connections and waypoints
    computed_connections = []
    for step in steps:
        step_id = str(step.get("id", step.get("name")))
        src_info = placed_elements.get(step_id)
        if not src_info:
            continue

        # Single next connection
        if "next" in step and step["next"]:
            tgt_id = str(step["next"])
            tgt_info = placed_elements.get(tgt_id)
            if tgt_info:
                # If target is in another lane, calculate orthogonal waypoint
                waypoint = ""
                if abs(tgt_info["center_x"] - src_info["center_x"]) > 20:
                    waypoint = f"{tgt_info['center_x']}:{src_info['center_y']};"

                computed_connections.append({
                    "source_id": step_id,
                    "target_id": tgt_id,
                    "guard": step.get("guard", ""),
                    "waypoint": waypoint,
                    "line_style": 3 if waypoint else 8
                })

        # Decision branches
        if "branches" in step and isinstance(step["branches"], list):
            for b in step["branches"]:
                tgt_id = str(b.get("target_id", b.get("target")))
                tgt_info = placed_elements.get(tgt_id)
                guard = b.get("guard", "")
                if tgt_info:
                    waypoint = ""
                    if abs(tgt_info["center_x"] - src_info["center_x"]) > 20:
                        waypoint = f"{tgt_info['center_x']}:{src_info['center_y']};"

                    computed_connections.append({
                        "source_id": step_id,
                        "target_id": tgt_id,
                        "guard": guard,
                        "waypoint": waypoint,
                        "line_style": 3 if waypoint else 8
                    })

    return {
        "lanes": [v for k, v in lane_map.items() if not k.isdigit()],
        "elements": placed_elements,
        "connections": computed_connections
    }


def sanitize_bounds(
    left: int,
    top: int,
    right: int,
    bottom: int,
    default_width: int = 140,
    default_height: int = 80
) -> Tuple[int, int, int, int]:
    """Ensures valid coordinates for an EA DiagramObject."""
    if right <= left:
        right = left + default_width
    # In EA, bottom should be below top (which in negative coordinate space means bottom < top)
    if top > 0 and bottom > 0:
        # If user passed positive top and bottom where bottom > top (standard screen coords),
        # convert to EA convention (negative Y)
        h = abs(bottom - top)
        if h == 0:
            h = default_height
        top = -abs(top)
        bottom = top - h
    elif bottom >= top:
        bottom = top - default_height

    return int(left), int(top), int(right), int(bottom)
