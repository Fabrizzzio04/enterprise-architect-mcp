"""
Enterprise Architect Model Context Protocol (MCP) Server.
Compatible with Sparx Systems Enterprise Architect 13.5 (Build 1351) and above.
"""

import json
from typing import Any, Dict, List, Optional

from mcp.server.mcpserver import MCPServer
from ea_controller import EAController
from ea_coords import calculate_grid_positions

# Initialize MCP Server
mcp = MCPServer(
    name="enterprise-architect",
    instructions="Enterprise Architect v13.5 Automation Server. Allows creating, editing, and managing UML diagrams, elements, and relationships."
)

controller = EAController.get_instance()


# ------------------------------------------------------------------------------
# Connection & Repository Status
# ------------------------------------------------------------------------------

@mcp.tool()
def ea_connect(file_path: Optional[str] = None) -> str:
    """
    Connect to Enterprise Architect.
    If EA is already running, attaches to the active session.
    If file_path is provided, opens the specified .eap, .eapx or .feap model file.
    """
    try:
        status = controller.connect(file_path)
        return json.dumps({
            "status": "success",
            "message": "Connected to Enterprise Architect successfully.",
            "data": status
        }, indent=2)
    except Exception as e:
        return json.dumps({
            "status": "error",
            "message": f"Connection error: {str(e)}"
        }, indent=2)


@mcp.tool()
def ea_get_status() -> str:
    """
    Get current status of Enterprise Architect connection, active model, and currently open diagram.
    """
    try:
        status = controller.get_status()
        return json.dumps({"status": "success", "data": status}, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)


# ------------------------------------------------------------------------------
# Packages & Navigation
# ------------------------------------------------------------------------------

@mcp.tool()
def ea_list_packages(parent_package_id: Optional[int] = None) -> str:
    """
    List packages in the model.
    If parent_package_id is None, lists top-level root models.
    Otherwise, lists subpackages of the specified parent package.
    """
    try:
        packages = controller.list_packages(parent_package_id)
        return json.dumps({"status": "success", "packages": packages}, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)


@mcp.tool()
def ea_create_package(name: str, parent_package_id: Optional[int] = None) -> str:
    """
    Create a new package in the model.
    If parent_package_id is omitted, creates under the first root model.
    """
    try:
        res = controller.create_package(name, parent_package_id)
        return json.dumps({"status": "success", "package": res}, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)


# ------------------------------------------------------------------------------
# Diagrams (Create, Read, Edit)
# ------------------------------------------------------------------------------

@mcp.tool()
def ea_list_diagrams(package_id: Optional[int] = None) -> str:
    """
    List diagrams in the model.
    If package_id is provided, lists diagrams inside that package.
    Otherwise, queries all diagrams across the repository.
    """
    try:
        diagrams = controller.list_diagrams(package_id)
        return json.dumps({"status": "success", "diagrams": diagrams}, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)


@mcp.tool()
def ea_create_diagram(
    package_id: int,
    name: str,
    diagram_type: str = "Logical",
    notes: str = ""
) -> str:
    """
    Create a new diagram in the specified package.
    Common diagram_types:
    - 'Logical' or 'Class' (UML Class Diagram)
    - 'Use Case' (UML Use Case Diagram)
    - 'Sequence' (UML Sequence Diagram)
    - 'Component' (UML Component Diagram)
    - 'Activity' (UML Activity Diagram)
    - 'Statechart' (UML State Machine Diagram)
    - 'Deployment' (UML Deployment Diagram)
    """
    try:
        diagram = controller.create_diagram(package_id, name, diagram_type, notes)
        return json.dumps({
            "status": "success",
            "message": f"Diagram '{name}' created successfully.",
            "diagram": diagram
        }, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)


@mcp.tool()
def ea_get_diagram(diagram_id: int) -> str:
    """
    Retrieve full diagram information, including placed elements, bounding box coordinates, and connector links.
    """
    try:
        diag = controller.get_diagram(diagram_id)
        return json.dumps({"status": "success", "diagram": diag}, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)


@mcp.tool()
def ea_add_element_to_diagram(
    diagram_id: int,
    element_id: int,
    left: int = 100,
    top: int = -100,
    right: int = 240,
    bottom: int = -180
) -> str:
    """
    Place an existing model element onto a diagram with specific coordinates.
    In EA coordinate convention:
    - left: X coordinate (positive, e.g. 100)
    - right: X coordinate (right = left + width, e.g. 240)
    - top: Y coordinate (usually negative, e.g. -100)
    - bottom: Y coordinate (usually negative, e.g. -180, bottom < top)
    """
    try:
        res = controller.add_element_to_diagram(diagram_id, element_id, left, top, right, bottom)
        return json.dumps({"status": "success", "placed_element": res}, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)


@mcp.tool()
def ea_update_diagram_object(
    diagram_id: int,
    element_id: int,
    left: Optional[int] = None,
    top: Optional[int] = None,
    right: Optional[int] = None,
    bottom: Optional[int] = None,
    sequence: Optional[int] = None
) -> str:
    """
    Move or resize an element on a diagram by updating its coordinates.
    """
    try:
        res = controller.update_diagram_object(
            diagram_id, element_id, left, top, right, bottom, sequence
        )
        return json.dumps({"status": "success", "updated_object": res}, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)


@mcp.tool()
def ea_remove_from_diagram(diagram_id: int, element_id: int) -> str:
    """
    Remove an element from a diagram without deleting it from the repository.
    """
    try:
        removed = controller.remove_element_from_diagram(diagram_id, element_id)
        return json.dumps({
            "status": "success" if removed else "warning",
            "removed": removed,
            "message": "Element removed from diagram." if removed else "Element was not on diagram."
        }, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)


@mcp.tool()
def ea_respread_and_fix_workflow(
    diagram_id: int,
    vertical_gap: int = 48
) -> str:
    """
    Respreads elements in an activity/use case workflow with a clean, generous vertical gap (default 48px).
    Fixes squished/short arrows between actions in the same lane, stretches all swimlane partitions
    down to the bottom of the diagram, and enforces clean 90-degree orthogonal line routing and decision forks.
    """
    try:
        res = controller.respread_vertical_workflow(diagram_id, vertical_gap)
        return json.dumps({"status": "success", "result": res}, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)


@mcp.tool()
def ea_fix_swimlanes(diagram_id: int) -> str:
    """
    Restore and fix ActivityPartitions / Swimlanes on an activity diagram.
    Stretches all vertical lane columns from top to bottom past the lowest action,
    ensures proper column width and alignment, and sets them in the background (Z-order).
    """
    try:
        fixed_count = controller.fix_swimlanes_and_partitions(diagram_id)
        return json.dumps({
            "status": "success",
            "diagram_id": diagram_id,
            "partitions_fixed": fixed_count,
            "message": f"Successfully restored {fixed_count} swimlanes/partitions."
        }, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)


@mcp.tool()
def ea_polish_diagram(
    diagram_id: int,
    theme: str = "classic"
) -> str:
    """
    Master cleanup and beautification tool.
    Normalizes a whole diagram in ONE shot:
    - Resets elements to standard canonical dimensions.
    - Applies Enterprise Architect corporate color palette (soft cream actions, soft green decisions, etc.).
    - Enforces 90-degree orthogonal line routing on all connectors.
    - Symmetrically formats all decision branches so they exit horizontally and drop 90 degrees cleanly.
    """
    try:
        res = controller.polish_diagram(diagram_id, theme)
        return json.dumps({"status": "success", "result": res}, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)


@mcp.tool()
def ea_create_workflow_diagram(
    package_id: int,
    diagram_name: str,
    lanes: List[str],
    steps: List[Dict[str, Any]],
    notes: str = ""
) -> str:
    """
    Create a complete, professionally formatted vertical workflow diagram in ONE step.
    Places elements centered in their actor/system lanes, applies corporate colors,
    and routes all flows and decision branches with clean 90-degree orthogonal lines.

    Parameters:
    - lanes: List of lane names, e.g. ["Operador", "Sistema Central", "Base de Datos"]
    - steps: Ordered list of steps. Each step can have:
      - 'id': unique identifier (e.g. 'step1')
      - 'name': display text
      - 'type': 'Action' | 'Decision' | 'ActivityInitial' | 'ActivityFinal'
      - 'lane': lane name or index
      - 'next': id of next step (for linear flow)
      - 'branches': list of {'target_id': 'stepX', 'guard': 'Texto condición'} (for decisions)
    """
    try:
        res = controller.create_workflow_diagram(package_id, diagram_name, lanes, steps, notes)
        return json.dumps({"status": "success", "workflow": res}, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)


@mcp.tool()
def ea_set_element_appearance(
    element_id: int,
    diagram_id: int,
    bg_color: Optional[int] = None,
    border_color: Optional[int] = None,
    border_width: Optional[int] = None
) -> str:
    """
    Customize the color styling of an element on a diagram.
    bg_color / border_color are Windows COLORREF integers (R + G*256 + B*65536).
    """
    try:
        res = controller.set_element_appearance(
            element_id, diagram_id, bg_color, border_color, border_width
        )
        return json.dumps({"status": "success", "appearance": res}, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)


@mcp.tool()
def ea_export_diagram_image(
    diagram_id: int,
    output_path: Optional[str] = None
) -> str:
    """
    Export a diagram to a PNG image file for inspection or rendering.
    Returns the absolute path to the generated image file.
    """
    try:
        img_path = controller.export_diagram_image(diagram_id, output_path)
        return json.dumps({
            "status": "success",
            "image_path": img_path
        }, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)


# ------------------------------------------------------------------------------
# Elements & Features
# ------------------------------------------------------------------------------

@mcp.tool()
def ea_create_element(
    package_id: int,
    name: str,
    element_type: str = "Class",
    stereotype: str = "",
    notes: str = "",
    add_to_diagram_id: Optional[int] = None,
    left: int = 100,
    top: int = -100,
    right: int = 240,
    bottom: int = -180
) -> str:
    """
    Create a new model element (Class, Interface, Component, Actor, UseCase, Activity, etc.).
    Optionally places the newly created element directly onto a diagram.
    """
    try:
        el = controller.create_element(
            package_id=package_id,
            name=name,
            element_type=element_type,
            stereotype=stereotype,
            notes=notes,
            add_to_diagram_id=add_to_diagram_id,
            left=left,
            top=top,
            right=right,
            bottom=bottom
        )
        return json.dumps({"status": "success", "element": el}, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)


@mcp.tool()
def ea_get_element(element_id: int) -> str:
    """
    Get full element details: name, type, stereotype, attributes (fields), methods, and connectors.
    """
    try:
        el = controller.get_element(element_id)
        return json.dumps({"status": "success", "element": el}, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)


@mcp.tool()
def ea_update_element(
    element_id: int,
    name: Optional[str] = None,
    notes: Optional[str] = None,
    stereotype: Optional[str] = None
) -> str:
    """
    Update element name, notes, or stereotype.
    """
    try:
        res = controller.update_element(element_id, name, notes, stereotype)
        return json.dumps({"status": "success", "element": res}, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)


@mcp.tool()
def ea_delete_element(element_id: int) -> str:
    """
    Delete an element permanently from its parent package in the repository.
    """
    try:
        deleted = controller.delete_element(element_id)
        return json.dumps({
            "status": "success" if deleted else "warning",
            "deleted": deleted
        }, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)


@mcp.tool()
def ea_add_attribute(
    element_id: int,
    name: str,
    attr_type: str = "String",
    visibility: str = "Public",
    default_value: str = "",
    notes: str = ""
) -> str:
    """
    Add an attribute/field/property to an element (e.g. a UML Class attribute).
    """
    try:
        attr = controller.add_attribute(
            element_id=element_id,
            name=name,
            attr_type=attr_type,
            visibility=visibility,
            default_value=default_value,
            notes=notes
        )
        return json.dumps({"status": "success", "attribute": attr}, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)


@mcp.tool()
def ea_add_operation(
    element_id: int,
    name: str,
    return_type: str = "void",
    visibility: str = "Public",
    parameters: Optional[List[Dict[str, str]]] = None,
    notes: str = ""
) -> str:
    """
    Add an operation/method to an element (e.g. a UML Class method).
    parameters format: [{'name': 'paramName', 'type': 'String', 'kind': 'in'}]
    """
    try:
        op = controller.add_operation(
            element_id=element_id,
            name=name,
            return_type=return_type,
            visibility=visibility,
            parameters=parameters,
            notes=notes
        )
        return json.dumps({"status": "success", "operation": op}, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)


# ------------------------------------------------------------------------------
# Decision Nodes & Advanced Flow Branching
# ------------------------------------------------------------------------------

@mcp.tool()
def ea_create_decision_node(
    package_id: int,
    name: str,
    diagram_id: int,
    left: int = 200,
    top: int = -80,
    right: int = 260,
    bottom: int = -130,
    incoming_element_id: Optional[int] = None,
    branches: Optional[List[Dict[str, Any]]] = None
) -> str:
    """
    Create a clean Decision diamond node with symmetric 90-degree orthogonal branching.
    Incoming arrows enter directly into the top vertex.
    Branches exit horizontally from the left/right diamond vertices and drop vertically into target actions.

    branches format:
    [
      {"target_element_id": 123, "guard": "Crear / Editar"},
      {"target_element_id": 124, "guard": "Dar de Baja"}
    ]
    """
    try:
        res = controller.create_decision_node(
            package_id=package_id,
            name=name,
            diagram_id=diagram_id,
            left=left,
            top=top,
            right=right,
            bottom=bottom,
            incoming_element_id=incoming_element_id,
            branches=branches
        )
        return json.dumps({"status": "success", "decision_node": res}, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)


@mcp.tool()
def ea_format_decision_branches(
    diagram_id: int,
    decision_element_id: int
) -> str:
    """
    Reformat all outgoing connectors from an existing decision node on a diagram.
    Forces horizontal exit from left/right vertices with 90-degree drop into target actions
    (turns awkward Z-shaped lines into clean, symmetrical T-forks / Y-forks).
    """
    try:
        res = controller.format_decision_branches(diagram_id, decision_element_id)
        return json.dumps({"status": "success", "result": res}, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)


# ------------------------------------------------------------------------------
# Connectors & Relationships
# ------------------------------------------------------------------------------

@mcp.tool()
def ea_set_connector_style(
    diagram_id: int,
    connector_id: Optional[int] = None,
    line_style: str = "orthogonal_square"
) -> str:
    """
    Set visual line routing style for connectors on a diagram.
    - 'orthogonal_square' (default): 90-degree clean angles (recommended for clean workflows / BPMN / Activities).
    - 'orthogonal_rounded': 90-degree angles with rounded corners.
    - 'direct': Direct straight diagonal line between elements.
    - 'tree_vertical' / 'tree_horizontal': Hierarchical tree routing.
    - 'auto': Automatic routing.

    If connector_id is omitted or null, sets ALL connectors on the diagram to this style at once.
    """
    try:
        res = controller.set_diagram_link_style(diagram_id, connector_id, line_style)
        return json.dumps({"status": "success", "result": res}, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)


@mcp.tool()
def ea_create_connector(
    source_element_id: int,
    target_element_id: int,
    connector_type: str = "Association",
    name: str = "",
    stereotype: str = "",
    direction: str = "Source -> Destination",
    guard: str = "",
    line_style: str = "orthogonal_square",
    diagram_id: Optional[int] = None,
    notes: str = ""
) -> str:
    """
    Create a connector / relationship between two elements.
    Common types:
    - 'ControlFlow' (Activity / BPMN diagrams)
    - 'Association'
    - 'Generalization' (Inheritance)
    - 'Realization' (Interface implementation)
    - 'Dependency'
    - 'Aggregation'
    - 'Composition'

    Parameters:
    - guard: Condition guard text displayed on the arrow, e.g. '[Crear / Editar]' or '[Dar de Baja]'.
    - line_style: 'orthogonal_square' (90-degree right angles), 'orthogonal_rounded', 'direct', etc.
    - diagram_id: Optional diagram ID to immediately apply the line_style visually.
    """
    try:
        conn = controller.create_connector(
            source_element_id=source_element_id,
            target_element_id=target_element_id,
            connector_type=connector_type,
            name=name,
            stereotype=stereotype,
            direction=direction,
            guard=guard,
            line_style=line_style,
            diagram_id=diagram_id,
            notes=notes
        )
        return json.dumps({"status": "success", "connector": conn}, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)


@mcp.tool()
def ea_delete_connector(connector_id: int) -> str:
    """
    Delete a connector relationship by ID.
    """
    try:
        deleted = controller.delete_connector(connector_id)
        return json.dumps({"status": "success", "deleted": deleted}, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)


# ------------------------------------------------------------------------------
# Queries & Layout Helpers
# ------------------------------------------------------------------------------

@mcp.tool()
def ea_sql_query(query: str) -> str:
    """
    Execute a raw read-only SQL query against Enterprise Architect's repository database.
    Useful for custom inspection of t_object, t_diagram, t_connector, etc.
    """
    try:
        rows = controller.sql_query(query)
        return json.dumps({"status": "success", "count": len(rows), "rows": rows}, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)


@mcp.tool()
def ea_calculate_grid_layout(
    element_count: int,
    columns: int = 3,
    start_left: int = 80,
    start_top: int = -80,
    width: int = 150,
    height: int = 90,
    spacing_x: int = 60,
    spacing_y: int = 60
) -> str:
    """
    Helper to calculate clean (left, top, right, bottom) grid coordinates for placing multiple elements on a diagram.
    """
    try:
        coords = calculate_grid_positions(
            item_count=element_count,
            cols=columns,
            start_left=start_left,
            start_top=start_top,
            item_width=width,
            item_height=height,
            spacing_x=spacing_x,
            spacing_y=spacing_y
        )
        return json.dumps({"status": "success", "coordinates": coords}, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, indent=2)


if __name__ == "__main__":
    mcp.run("stdio")
