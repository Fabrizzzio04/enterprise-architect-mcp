"""
Enterprise Architect Automation Controller via COM (EA.App / EA.Repository).
Compatible with Sparx Systems Enterprise Architect 13.5 and above.
"""

import os
import re
import threading
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Tuple

import pythoncom
import win32com.client

from ea_coords import (
    calculate_decision_waypoints,
    calculate_grid_positions,
    layout_vertical_workflow,
    sanitize_bounds,
)
from ea_visual_rules import (
    CLASSIC_EA_PALETTE,
    CONTAINER_TYPES,
    ELEMENT_CANONICAL_DIMENSIONS,
    build_style_string,
    get_element_dimensions,
)


class EAController:
    """Singleton controller to interact with Enterprise Architect via COM."""

    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self._app = None
        self._repo = None
        self._current_file: Optional[str] = None

    @classmethod
    def get_instance(cls) -> "EAController":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def _ensure_com(self):
        """Initializes COM for the calling thread."""
        try:
            pythoncom.CoInitialize()
        except Exception:
            pass

    def connect(self, file_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Connects to a running instance of Enterprise Architect or launches it.
        If file_path is specified and not loaded, opens it.
        """
        self._ensure_com()

        app = None
        repo = None

        # 1. Try to attach to an already running instance
        try:
            app = win32com.client.GetObject(Class="EA.App")
            if app:
                repo = app.Repository
        except Exception:
            app = None
            repo = None

        # 2. If no running instance, dispatch a new EA.App or EA.Repository
        if repo is None:
            try:
                app = win32com.client.Dispatch("EA.App")
                repo = app.Repository
            except Exception as e:
                # Fallback to direct EA.Repository
                try:
                    repo = win32com.client.Dispatch("EA.Repository")
                except Exception as inner_e:
                    raise RuntimeError(
                        f"Failed to connect to Enterprise Architect COM: {e} / {inner_e}"
                    )

        self._app = app
        self._repo = repo

        # Check if project file is open or needs opening
        opened_file = ""
        try:
            opened_file = repo.ConnectionString
        except Exception:
            pass

        if file_path:
            norm_file = os.path.abspath(file_path)
            if not os.path.exists(norm_file):
                raise FileNotFoundError(f"File not found: {norm_file}")

            # Open file if different or if no file opened
            if not opened_file or os.path.normcase(opened_file) != os.path.normcase(norm_file):
                repo.OpenFile(norm_file)
                self._current_file = norm_file
            else:
                self._current_file = opened_file
        else:
            self._current_file = opened_file

        return self.get_status()

    def get_repository(self):
        """Returns the active repository, connecting if necessary."""
        self._ensure_com()
        if self._repo is None:
            self.connect()
        return self._repo

    def get_status(self) -> Dict[str, Any]:
        """Returns the current state of Enterprise Architect connection and active model."""
        repo = self.get_repository()
        conn_str = ""
        try:
            conn_str = repo.ConnectionString
        except Exception:
            pass

        models = []
        try:
            for i in range(repo.Models.Count):
                m = repo.Models.GetAt(i)
                models.append({
                    "id": m.PackageID,
                    "guid": m.PackageGUID,
                    "name": m.Name
                })
        except Exception:
            pass

        current_diagram = None
        try:
            cd = repo.GetCurrentDiagram()
            if cd:
                current_diagram = {
                    "id": cd.DiagramID,
                    "guid": cd.DiagramGUID,
                    "name": cd.Name,
                    "type": cd.Type
                }
        except Exception:
            pass

        return {
            "connected": True,
            "connection_string": conn_str,
            "models_count": len(models),
            "root_models": models,
            "active_diagram": current_diagram
        }

    # --------------------------------------------------------------------------
    # Packages and Navigation
    # --------------------------------------------------------------------------

    def list_packages(self, parent_package_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Lists root models or subpackages of a given package."""
        repo = self.get_repository()
        results = []

        if parent_package_id is None:
            for i in range(repo.Models.Count):
                pkg = repo.Models.GetAt(i)
                results.append({
                    "id": pkg.PackageID,
                    "guid": pkg.PackageGUID,
                    "name": pkg.Name,
                    "subpackages_count": pkg.Packages.Count,
                    "elements_count": pkg.Elements.Count,
                    "diagrams_count": pkg.Diagrams.Count,
                })
        else:
            parent = repo.GetPackageByID(int(parent_package_id))
            if not parent:
                raise ValueError(f"Package ID {parent_package_id} not found.")
            for i in range(parent.Packages.Count):
                pkg = parent.Packages.GetAt(i)
                results.append({
                    "id": pkg.PackageID,
                    "guid": pkg.PackageGUID,
                    "name": pkg.Name,
                    "subpackages_count": pkg.Packages.Count,
                    "elements_count": pkg.Elements.Count,
                    "diagrams_count": pkg.Diagrams.Count,
                })

        return results

    def create_package(self, name: str, parent_package_id: Optional[int] = None) -> Dict[str, Any]:
        """Creates a new package under the specified parent (or under the first root model)."""
        repo = self.get_repository()
        if parent_package_id is None:
            if repo.Models.Count == 0:
                raise RuntimeError("No root models in repository to create package in.")
            parent = repo.Models.GetAt(0)
        else:
            parent = repo.GetPackageByID(int(parent_package_id))

        if not parent:
            raise ValueError(f"Parent package {parent_package_id} not found.")

        new_pkg = parent.Packages.AddNew(name, "")
        if not new_pkg.Update():
            raise RuntimeError(f"Failed to create package: {new_pkg.GetLastError()}")
        parent.Packages.Refresh()

        return {
            "id": new_pkg.PackageID,
            "guid": new_pkg.PackageGUID,
            "name": new_pkg.Name,
            "parent_id": parent.PackageID
        }

    # --------------------------------------------------------------------------
    # Diagrams
    # --------------------------------------------------------------------------

    def list_diagrams(self, package_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Lists diagrams in a specific package or across the whole repository."""
        repo = self.get_repository()
        results = []

        if package_id is not None:
            pkg = repo.GetPackageByID(int(package_id))
            if not pkg:
                raise ValueError(f"Package {package_id} not found.")
            for i in range(pkg.Diagrams.Count):
                diag = pkg.Diagrams.GetAt(i)
                results.append({
                    "id": diag.DiagramID,
                    "guid": diag.DiagramGUID,
                    "name": diag.Name,
                    "type": diag.Type,
                    "package_id": pkg.PackageID,
                    "notes": diag.Notes
                })
        else:
            # Query all diagrams via fast SQL
            sql = "SELECT Diagram_ID, ea_guid, Name, Diagram_Type, Package_ID, Notes FROM t_diagram"
            raw_xml = repo.SQLQuery(sql)
            results = self._parse_ea_xml(raw_xml)

        return results

    def create_diagram(
        self,
        package_id: int,
        name: str,
        diagram_type: str = "Logical",
        notes: str = ""
    ) -> Dict[str, Any]:
        """
        Creates a new diagram under a package.
        Common types: 'Logical' (Class diagram), 'Use Case', 'Sequence', 'Component',
        'Activity', 'Statechart', 'Deployment', 'Custom'.
        """
        repo = self.get_repository()
        pkg = repo.GetPackageByID(int(package_id))
        if not pkg:
            raise ValueError(f"Package ID {package_id} not found.")

        # Map common names to EA Diagram types if necessary
        type_mapping = {
            "class": "Logical",
            "logical": "Logical",
            "use case": "Use Case",
            "usecase": "Use Case",
            "sequence": "Sequence",
            "component": "Component",
            "activity": "Activity",
            "statechart": "Statechart",
            "state": "Statechart",
            "deployment": "Deployment",
            "composite": "CompositeStructure",
        }
        mapped_type = type_mapping.get(diagram_type.lower(), diagram_type)

        diag = pkg.Diagrams.AddNew(name, mapped_type)
        diag.Notes = notes
        if not diag.Update():
            raise RuntimeError(f"Failed to create diagram: {diag.GetLastError()}")

        pkg.Diagrams.Refresh()

        return {
            "id": diag.DiagramID,
            "guid": diag.DiagramGUID,
            "name": diag.Name,
            "type": diag.Type,
            "package_id": pkg.PackageID,
            "notes": diag.Notes
        }

    def get_diagram(self, diagram_id: int) -> Dict[str, Any]:
        """Gets full diagram details, including all placed elements and links."""
        repo = self.get_repository()
        diag = repo.GetDiagramByID(int(diagram_id))
        if not diag:
            raise ValueError(f"Diagram {diagram_id} not found.")

        elements = []
        for i in range(diag.DiagramObjects.Count):
            d_obj = diag.DiagramObjects.GetAt(i)
            el = None
            try:
                el = repo.GetElementByID(d_obj.ElementID)
            except Exception:
                pass

            elements.append({
                "diagram_object_id": d_obj.InstanceID,
                "element_id": d_obj.ElementID,
                "name": el.Name if el else "",
                "type": el.Type if el else "",
                "stereotype": el.Stereotype if el else "",
                "left": d_obj.left,
                "top": d_obj.top,
                "right": d_obj.right,
                "bottom": d_obj.bottom,
                "sequence": d_obj.Sequence
            })

        links = []
        for i in range(diag.DiagramLinks.Count):
            d_link = diag.DiagramLinks.GetAt(i)
            connector = None
            try:
                connector = repo.GetConnectorByID(d_link.ConnectorID)
            except Exception:
                pass

            links.append({
                "diagram_link_id": d_link.InstanceID,
                "connector_id": d_link.ConnectorID,
                "name": connector.Name if connector else "",
                "type": connector.Type if connector else "",
                "source_id": connector.ClientID if connector else None,
                "target_id": connector.SupplierID if connector else None,
            })

        return {
            "id": diag.DiagramID,
            "guid": diag.DiagramGUID,
            "name": diag.Name,
            "type": diag.Type,
            "package_id": diag.PackageID,
            "notes": diag.Notes,
            "elements_count": len(elements),
            "elements": elements,
            "links_count": len(links),
            "links": links
        }

    def add_element_to_diagram(
        self,
        diagram_id: int,
        element_id: int,
        left: int = 100,
        top: int = -100,
        right: int = 240,
        bottom: int = -180
    ) -> Dict[str, Any]:
        """Places an existing element onto a diagram with specific coordinates."""
        repo = self.get_repository()
        diag = repo.GetDiagramByID(int(diagram_id))
        if not diag:
            raise ValueError(f"Diagram {diagram_id} not found.")

        el = repo.GetElementByID(int(element_id))
        if not el:
            raise ValueError(f"Element {element_id} not found.")

        left, top, right, bottom = sanitize_bounds(left, top, right, bottom)

        # Check if already in diagram
        existing_obj = None
        for i in range(diag.DiagramObjects.Count):
            d_obj = diag.DiagramObjects.GetAt(i)
            if d_obj.ElementID == el.ElementID:
                existing_obj = d_obj
                break

        if existing_obj:
            existing_obj.left = left
            existing_obj.top = top
            existing_obj.right = right
            existing_obj.bottom = bottom
            existing_obj.Update()
            d_obj = existing_obj
        else:
            d_obj = diag.DiagramObjects.AddNew("", "")
            d_obj.ElementID = el.ElementID
            d_obj.left = left
            d_obj.top = top
            d_obj.right = right
            d_obj.bottom = bottom
            if not d_obj.Update():
                raise RuntimeError(f"Failed to place element on diagram: {d_obj.GetLastError()}")

        diag.DiagramObjects.Refresh()
        diag.Update()
        try:
            repo.ReloadDiagram(diag.DiagramID)
        except Exception:
            pass

        return {
            "diagram_id": diag.DiagramID,
            "element_id": el.ElementID,
            "element_name": el.Name,
            "left": d_obj.left,
            "top": d_obj.top,
            "right": d_obj.right,
            "bottom": d_obj.bottom
        }

    def update_diagram_object(
        self,
        diagram_id: int,
        element_id: int,
        left: Optional[int] = None,
        top: Optional[int] = None,
        right: Optional[int] = None,
        bottom: Optional[int] = None,
        sequence: Optional[int] = None
    ) -> Dict[str, Any]:
        """Updates coordinates or z-order of an element in a diagram."""
        repo = self.get_repository()
        diag = repo.GetDiagramByID(int(diagram_id))
        if not diag:
            raise ValueError(f"Diagram {diagram_id} not found.")

        target_obj = None
        for i in range(diag.DiagramObjects.Count):
            d_obj = diag.DiagramObjects.GetAt(i)
            if d_obj.ElementID == int(element_id):
                target_obj = d_obj
                break

        if not target_obj:
            raise ValueError(f"Element {element_id} is not present in diagram {diagram_id}.")

        cur_l = target_obj.left if left is None else left
        cur_t = target_obj.top if top is None else top
        cur_r = target_obj.right if right is None else right
        cur_b = target_obj.bottom if bottom is None else bottom

        new_l, new_t, new_r, new_b = sanitize_bounds(cur_l, cur_t, cur_r, cur_b)

        target_obj.left = new_l
        target_obj.top = new_t
        target_obj.right = new_r
        target_obj.bottom = new_b

        if sequence is not None:
            target_obj.Sequence = int(sequence)

        target_obj.Update()
        diag.DiagramObjects.Refresh()
        diag.Update()
        try:
            repo.ReloadDiagram(diag.DiagramID)
        except Exception:
            pass

        return {
            "diagram_id": diag.DiagramID,
            "element_id": element_id,
            "left": target_obj.left,
            "top": target_obj.top,
            "right": target_obj.right,
            "bottom": target_obj.bottom
        }

    def remove_element_from_diagram(self, diagram_id: int, element_id: int) -> bool:
        """Removes an element from a diagram without deleting it from the repository."""
        repo = self.get_repository()
        diag = repo.GetDiagramByID(int(diagram_id))
        if not diag:
            raise ValueError(f"Diagram {diagram_id} not found.")

        for i in range(diag.DiagramObjects.Count):
            d_obj = diag.DiagramObjects.GetAt(i)
            if d_obj.ElementID == int(element_id):
                diag.DiagramObjects.Delete(i)
                diag.DiagramObjects.Refresh()
                diag.Update()
                try:
                    repo.ReloadDiagram(diag.DiagramID)
                except Exception:
                    pass
                return True

        return False

    def export_diagram_image(
        self,
        diagram_id: int,
        output_path: Optional[str] = None
    ) -> str:
        """Exports diagram to a PNG image file."""
        repo = self.get_repository()
        diag = repo.GetDiagramByID(int(diagram_id))
        if not diag:
            raise ValueError(f"Diagram {diagram_id} not found.")

        if not output_path:
            # Default to scratch/output dir
            base_dir = os.path.dirname(os.path.abspath(__file__))
            out_dir = os.path.join(base_dir, "exports")
            os.makedirs(out_dir, exist_ok=True)
            safe_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', diag.Name)
            output_path = os.path.join(out_dir, f"{safe_name}_{diag.DiagramID}.png")

        norm_path = os.path.abspath(output_path)
        os.makedirs(os.path.dirname(norm_path), exist_ok=True)

        project = repo.GetProjectInterface()
        # 1 = PNG format
        success = project.PutDiagramImageToFile(diag.DiagramGUID, norm_path, 1)
        if not success:
            raise RuntimeError("Enterprise Architect failed to export diagram image.")

        return norm_path

    def set_element_appearance(
        self,
        element_id: int,
        diagram_id: int,
        bg_color: Optional[int] = None,
        border_color: Optional[int] = None,
        border_width: Optional[int] = None
    ) -> Dict[str, Any]:
        """Sets visual styling (BCol, LCol, LWth) for an element on a diagram."""
        repo = self.get_repository()
        diag = repo.GetDiagramByID(int(diagram_id))
        if not diag:
            raise ValueError(f"Diagram {diagram_id} not found.")

        target_obj = None
        for i in range(diag.DiagramObjects.Count):
            obj = diag.DiagramObjects.GetAt(i)
            if obj.ElementID == int(element_id):
                target_obj = obj
                break

        if not target_obj:
            raise ValueError(f"Element {element_id} not found on diagram {diagram_id}.")

        cur_style = target_obj.Style or ""
        new_style = build_style_string(cur_style, bg_color, border_color, border_width)
        target_obj.Style = new_style
        target_obj.Update()
        diag.DiagramObjects.Refresh()
        diag.Update()
        try:
            repo.ReloadDiagram(diag.DiagramID)
        except Exception:
            pass

        return {
            "diagram_id": diag.DiagramID,
            "element_id": element_id,
            "style": new_style
        }

    def polish_diagram(
        self,
        diagram_id: int,
        theme: str = "classic"
    ) -> Dict[str, Any]:
        """
        Master normalization and beautification tool:
        1. Resets element dimensions to standard canonical proportions.
        2. Applies Enterprise Architect corporate color palette.
        3. Enforces Orthogonal Square routing (90-degree angles) on all links.
        4. Calculates clean symmetric waypoints for all decision nodes.
        5. Reloads and refreshes diagram.
        """
        repo = self.get_repository()
        diag = repo.GetDiagramByID(int(diagram_id))
        if not diag:
            raise ValueError(f"Diagram {diagram_id} not found.")

        palette = CLASSIC_EA_PALETTE

        # 1. Elements styling and canonical bounds
        styled_elements = 0
        for i in range(diag.DiagramObjects.Count):
            d_obj = diag.DiagramObjects.GetAt(i)
            try:
                elem = repo.GetElementByID(d_obj.ElementID)
                elem_type = elem.Type

                # CRITICAL: Never shrink containers, partitions, boundaries, or swimlanes
                if elem_type in CONTAINER_TYPES:
                    continue

                # Apply palette if defined
                if elem_type in palette:
                    pal = palette[elem_type]
                    d_obj.Style = build_style_string(
                        d_obj.Style or "",
                        bg_color=pal.get("bg_color"),
                        border_color=pal.get("border_color"),
                        border_width=pal.get("border_width")
                    )
                # Normalize width / height to standard if weirdly shaped
                std_w, std_h = get_element_dimensions(elem_type, len(elem.Name))
                if std_w > 0 and std_h > 0:
                    cur_w = abs(d_obj.right - d_obj.left)
                    cur_h = abs(d_obj.top - d_obj.bottom)
                    if abs(cur_w - std_w) > 40 or abs(cur_h - std_h) > 20:
                        center_x = (d_obj.left + d_obj.right) // 2
                        d_obj.left = center_x - std_w // 2
                        d_obj.right = d_obj.left + std_w
                        d_obj.bottom = d_obj.top - std_h
                d_obj.Update()
                styled_elements += 1
            except Exception:
                pass

        diag.DiagramObjects.Refresh()

        # 2. Enforce 90-degree orthogonal line style on all links
        for i in range(diag.DiagramLinks.Count):
            link = diag.DiagramLinks.GetAt(i)
            if link.LineStyle != 3:  # Keep custom waypoints if already set
                link.LineStyle = 8   # Orthogonal Square
                link.Update()

        diag.DiagramLinks.Refresh()

        # 3. Format all decision nodes
        decisions_formatted = 0
        for i in range(diag.DiagramObjects.Count):
            d_obj = diag.DiagramObjects.GetAt(i)
            try:
                elem = repo.GetElementByID(d_obj.ElementID)
                if elem.Type in ["Decision", "MergeNode"]:
                    self.format_decision_branches(diag.DiagramID, elem.ElementID)
                    decisions_formatted += 1
            except Exception:
                pass

        # 4. Automatically fix and stretch any swimlanes / ActivityPartitions
        partitions_fixed = self.fix_swimlanes_and_partitions(diag.DiagramID)

        diag.Update()
        try:
            repo.ReloadDiagram(diag.DiagramID)
        except Exception:
            pass

        return {
            "diagram_id": diag.DiagramID,
            "status": "success",
            "styled_elements": styled_elements,
            "decisions_formatted": decisions_formatted,
            "partitions_fixed": partitions_fixed,
            "theme": theme
        }

    def fix_swimlanes_and_partitions(self, diagram_id: int) -> int:
        """
        Detects all ActivityPartition / Swimlane elements on a diagram,
        stretches them from the top down to past the lowest element,
        arranges their widths so they form seamless vertical columns,
        and ensures they are in the background (Z-order) behind actions.
        """
        repo = self.get_repository()
        diag = repo.GetDiagramByID(int(diagram_id))
        if not diag:
            raise ValueError(f"Diagram {diagram_id} not found.")

        partitions = []
        min_bottom = -200
        max_top = 0

        for i in range(diag.DiagramObjects.Count):
            d_obj = diag.DiagramObjects.GetAt(i)
            try:
                elem = repo.GetElementByID(d_obj.ElementID)
                if elem.Type in ["ActivityPartition", "Partition"]:
                    partitions.append((d_obj, elem))
                else:
                    if d_obj.bottom < min_bottom:
                        min_bottom = d_obj.bottom
                    if d_obj.top > max_top:
                        max_top = d_obj.top
            except Exception:
                pass

        if not partitions:
            return 0

        # Sort partitions left to right
        partitions.sort(key=lambda item: item[0].left)

        target_top = 0 if max_top <= 0 else max_top + 40
        target_bottom = min_bottom - 70

        # If partitions already had custom left/right, maintain or distribute them
        # Measure total span or distribute evenly
        count = len(partitions)
        for idx, (d_obj, elem) in enumerate(partitions):
            # Ensure proper top and bottom
            d_obj.top = target_top
            d_obj.bottom = target_bottom
            # Set to background Z-order
            d_obj.Sequence = 1
            # If partition width was squished (< 220), restore reasonable column width
            cur_width = abs(d_obj.right - d_obj.left)
            if cur_width < 250:
                center_x = (d_obj.left + d_obj.right) // 2
                col_w = 400
                d_obj.left = center_x - col_w // 2
                d_obj.right = d_obj.left + col_w
            d_obj.Update()

        diag.DiagramObjects.Refresh()
        diag.Update()
        try:
            repo.ReloadDiagram(diag.DiagramID)
        except Exception:
            pass

        return len(partitions)

    def respread_vertical_workflow(self, diagram_id: int, vertical_gap: int = 48) -> Dict[str, Any]:
        """
        Respreads elements vertically with a clean, generous gap (default 48px)
        so arrows between actions in the same lane have plenty of visible length,
        stretches all swimlane partitions to cover the entire flow down to the bottom,
        and enforces clean 90-degree orthogonal lines and formatted decision branches.
        """
        repo = self.get_repository()
        diag = repo.GetDiagramByID(int(diagram_id))
        if not diag:
            raise ValueError(f"Diagram {diagram_id} not found.")

        partitions = []
        elements = []

        for i in range(diag.DiagramObjects.Count):
            d_obj = diag.DiagramObjects.GetAt(i)
            try:
                el = repo.GetElementByID(d_obj.ElementID)
                if el.Type in ["ActivityPartition", "Partition"]:
                    partitions.append((d_obj, el))
                else:
                    elements.append((d_obj, el))
            except Exception:
                pass

        if not elements:
            return {"diagram_id": diagram_id, "status": "no_elements"}

        # Sort elements by current top descending (flow order)
        elements.sort(key=lambda item: item[0].top, reverse=True)

        curr_y = -40
        for d_obj, el in elements:
            if el.Type == "StateNode":
                w, h = 24, 24
            elif el.Type in ["Decision", "MergeNode"]:
                w, h = 50, 40
            else:
                w = 180
                h = 52 if len(el.Name) <= 50 else 62

            center_x = (d_obj.left + d_obj.right) // 2
            d_obj.left = center_x - w // 2
            d_obj.right = d_obj.left + w
            d_obj.top = curr_y
            d_obj.bottom = curr_y - h
            d_obj.Update()

            curr_y = d_obj.bottom - vertical_gap

        target_bottom = curr_y - 40

        # Stretch partitions to target_bottom
        partitions.sort(key=lambda item: item[0].left)
        for d_obj, el in partitions:
            d_obj.top = 0
            d_obj.bottom = target_bottom
            d_obj.Sequence = 1
            cur_w = abs(d_obj.right - d_obj.left)
            if cur_w < 260:
                center_x = (d_obj.left + d_obj.right) // 2
                col_w = 400
                d_obj.left = center_x - col_w // 2
                d_obj.right = center_x + col_w
            d_obj.Update()

        # Enforce 90-degree orthogonal line style on all links
        for i in range(diag.DiagramLinks.Count):
            link = diag.DiagramLinks.GetAt(i)
            link.LineStyle = 8
            link.Path = ""
            link.Update()

        # Format decision branches
        for d_obj, el in elements:
            if el.Type in ["Decision", "MergeNode"]:
                try:
                    self.format_decision_branches(diag.DiagramID, el.ElementID)
                except Exception:
                    pass

        diag.DiagramObjects.Refresh()
        diag.DiagramLinks.Refresh()
        diag.Update()
        try:
            repo.ReloadDiagram(diag.DiagramID)
        except Exception:
            pass

        return {
            "diagram_id": diag.DiagramID,
            "status": "success",
            "elements_respread": len(elements),
            "partitions_stretched": len(partitions),
            "bottom": target_bottom
        }

    def create_workflow_diagram(
        self,
        package_id: int,
        diagram_name: str,
        lanes: List[str],
        steps: List[Dict[str, Any]],
        notes: str = ""
    ) -> Dict[str, Any]:
        """
        Creates a complete, professionally formatted Activity/Workflow diagram in ONE step.
        Automatically arranges vertical lanes, places standard elements,
        applies corporate colors, and connects steps with clean 90-degree orthogonal flows.
        """
        repo = self.get_repository()
        pkg = repo.GetPackageByID(int(package_id))
        if not pkg:
            raise ValueError(f"Package {package_id} not found.")

        # 1. Create Activity Diagram
        diag_res = self.create_diagram(
            package_id=package_id,
            name=diagram_name,
            diagram_type="Activity",
            notes=notes
        )
        diag_id = diag_res["id"]
        diag = repo.GetDiagramByID(diag_id)

        # 2. Compute layout using automated vertical workflow engine
        layout_plan = layout_vertical_workflow(lanes=lanes, steps=steps)

        created_elements = {}
        # 3. Create elements and place on diagram
        for step_id, info in layout_plan["elements"].items():
            elem_type = info["type"]
            elem = pkg.Elements.AddNew(info["name"], elem_type)
            elem.Update()
            pkg.Elements.Refresh()

            # Place on diagram with computed coordinates
            d_obj = diag.DiagramObjects.AddNew("", "")
            d_obj.ElementID = elem.ElementID
            d_obj.left = info["left"]
            d_obj.top = info["top"]
            d_obj.right = info["right"]
            d_obj.bottom = info["bottom"]

            # Apply corporate color styling
            if elem_type in CLASSIC_EA_PALETTE:
                pal = CLASSIC_EA_PALETTE[elem_type]
                d_obj.Style = build_style_string(
                    "",
                    bg_color=pal["bg_color"],
                    border_color=pal["border_color"],
                    border_width=pal["border_width"]
                )

            d_obj.Update()
            created_elements[step_id] = {
                "element_id": elem.ElementID,
                "name": elem.Name,
                "type": elem.Type
            }

        diag.DiagramObjects.Refresh()
        diag.Update()
        repo.ReloadDiagram(diag_id)
        diag = repo.GetDiagramByID(diag_id)

        # 4. Create connections with waypoints
        created_conns = []
        for conn_info in layout_plan["connections"]:
            src_step = created_elements.get(conn_info["source_id"])
            tgt_step = created_elements.get(conn_info["target_id"])
            if src_step and tgt_step:
                src_elem = repo.GetElementByID(src_step["element_id"])
                c = src_elem.Connectors.AddNew(conn_info["guard"], "ControlFlow")
                c.SupplierID = tgt_step["element_id"]
                c.Direction = "Source -> Destination"
                if conn_info["guard"]:
                    c.TransitionGuard = conn_info["guard"]
                c.Update()
                src_elem.Connectors.Refresh()
                created_conns.append({
                    "id": c.ConnectorID,
                    "guard": conn_info["guard"],
                    "waypoint": conn_info.get("waypoint", "")
                })

        repo.ReloadDiagram(diag_id)
        diag = repo.GetDiagramByID(diag_id)

        # Map connectorID -> link to set waypoints and line style
        link_map = {}
        for i in range(diag.DiagramLinks.Count):
            l = diag.DiagramLinks.GetAt(i)
            link_map[l.ConnectorID] = l

        for conn_data in created_conns:
            c_id = conn_data["id"]
            if c_id in link_map:
                link = link_map[c_id]
                wp = conn_data.get("waypoint")
                if wp:
                    link.LineStyle = 3  # Custom with waypoints
                    link.Path = wp
                else:
                    link.LineStyle = 8  # Orthogonal Square
                link.Update()

        diag.DiagramLinks.Refresh()
        diag.Update()
        repo.ReloadDiagram(diag_id)

        # Export preview image
        img_path = self.export_diagram_image(diag_id)

        return {
            "diagram_id": diag_id,
            "name": diagram_name,
            "elements_count": len(created_elements),
            "connections_count": len(created_conns),
            "preview_image": img_path
        }

    # --------------------------------------------------------------------------
    # Elements and Features
    # --------------------------------------------------------------------------

    def create_element(
        self,
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
    ) -> Dict[str, Any]:
        """
        Creates a new model element (Class, Interface, Component, Actor, UseCase, etc.)
        under package_id, and optionally places it on a diagram.
        """
        repo = self.get_repository()
        pkg = repo.GetPackageByID(int(package_id))
        if not pkg:
            raise ValueError(f"Package {package_id} not found.")

        el = pkg.Elements.AddNew(name, element_type)
        if stereotype:
            el.Stereotype = stereotype
        if notes:
            el.Notes = notes

        if not el.Update():
            raise RuntimeError(f"Failed to create element: {el.GetLastError()}")

        pkg.Elements.Refresh()

        diagram_info = None
        if add_to_diagram_id is not None:
            diagram_info = self.add_element_to_diagram(
                diagram_id=add_to_diagram_id,
                element_id=el.ElementID,
                left=left,
                top=top,
                right=right,
                bottom=bottom
            )

        return {
            "id": el.ElementID,
            "guid": el.ElementGUID,
            "name": el.Name,
            "type": el.Type,
            "stereotype": el.Stereotype,
            "package_id": pkg.PackageID,
            "notes": el.Notes,
            "placed_on_diagram": diagram_info
        }

    def get_element(self, element_id: int) -> Dict[str, Any]:
        """Gets element details, including attributes, methods and connectors."""
        repo = self.get_repository()
        el = repo.GetElementByID(int(element_id))
        if not el:
            raise ValueError(f"Element {element_id} not found.")

        attributes = []
        for i in range(el.Attributes.Count):
            attr = el.Attributes.GetAt(i)
            attributes.append({
                "id": attr.AttributeID,
                "name": attr.Name,
                "type": attr.Type,
                "visibility": attr.Visibility,
                "default": attr.Default,
                "notes": attr.Notes
            })

        methods = []
        for i in range(el.Methods.Count):
            m = el.Methods.GetAt(i)
            parameters = []
            for j in range(m.Parameters.Count):
                p = m.Parameters.GetAt(j)
                parameters.append({
                    "name": p.Name,
                    "type": p.Type,
                    "kind": p.Kind,
                    "default": p.Default
                })
            methods.append({
                "id": m.MethodID,
                "name": m.Name,
                "return_type": m.ReturnType,
                "visibility": m.Visibility,
                "parameters": parameters,
                "notes": m.Notes
            })

        connectors = []
        for i in range(el.Connectors.Count):
            c = el.Connectors.GetAt(i)
            connectors.append({
                "id": c.ConnectorID,
                "name": c.Name,
                "type": c.Type,
                "source_id": c.ClientID,
                "target_id": c.SupplierID,
                "direction": c.Direction,
                "notes": c.Notes
            })

        return {
            "id": el.ElementID,
            "guid": el.ElementGUID,
            "name": el.Name,
            "type": el.Type,
            "stereotype": el.Stereotype,
            "package_id": el.PackageID,
            "notes": el.Notes,
            "attributes": attributes,
            "methods": methods,
            "connectors": connectors
        }

    def update_element(
        self,
        element_id: int,
        name: Optional[str] = None,
        notes: Optional[str] = None,
        stereotype: Optional[str] = None
    ) -> Dict[str, Any]:
        """Updates element properties."""
        repo = self.get_repository()
        el = repo.GetElementByID(int(element_id))
        if not el:
            raise ValueError(f"Element {element_id} not found.")

        if name is not None:
            el.Name = name
        if notes is not None:
            el.Notes = notes
        if stereotype is not None:
            el.Stereotype = stereotype

        el.Update()
        return {
            "id": el.ElementID,
            "name": el.Name,
            "type": el.Type,
            "stereotype": el.Stereotype,
            "notes": el.Notes
        }

    def delete_element(self, element_id: int) -> bool:
        """Deletes an element from its parent package."""
        repo = self.get_repository()
        el = repo.GetElementByID(int(element_id))
        if not el:
            raise ValueError(f"Element {element_id} not found.")

        pkg = repo.GetPackageByID(el.PackageID)
        for i in range(pkg.Elements.Count):
            e = pkg.Elements.GetAt(i)
            if e.ElementID == el.ElementID:
                pkg.Elements.Delete(i)
                pkg.Elements.Refresh()
                return True
        return False

    def add_attribute(
        self,
        element_id: int,
        name: str,
        attr_type: str = "String",
        visibility: str = "Public",
        default_value: str = "",
        notes: str = ""
    ) -> Dict[str, Any]:
        """Adds an attribute/property to a class or element."""
        repo = self.get_repository()
        el = repo.GetElementByID(int(element_id))
        if not el:
            raise ValueError(f"Element {element_id} not found.")

        attr = el.Attributes.AddNew(name, attr_type)
        attr.Visibility = visibility
        if default_value:
            attr.Default = default_value
        if notes:
            attr.Notes = notes

        if not attr.Update():
            raise RuntimeError(f"Failed to add attribute: {attr.GetLastError()}")

        el.Attributes.Refresh()
        el.Update()

        return {
            "id": attr.AttributeID,
            "element_id": el.ElementID,
            "name": attr.Name,
            "type": attr.Type,
            "visibility": attr.Visibility,
            "default": attr.Default
        }

    def add_operation(
        self,
        element_id: int,
        name: str,
        return_type: str = "void",
        visibility: str = "Public",
        parameters: Optional[List[Dict[str, str]]] = None,
        notes: str = ""
    ) -> Dict[str, Any]:
        """Adds a method/operation to a class or element."""
        repo = self.get_repository()
        el = repo.GetElementByID(int(element_id))
        if not el:
            raise ValueError(f"Element {element_id} not found.")

        op = el.Methods.AddNew(name, return_type)
        op.Visibility = visibility
        if notes:
            op.Notes = notes

        if not op.Update():
            raise RuntimeError(f"Failed to add operation: {op.GetLastError()}")

        if parameters:
            for p in parameters:
                p_name = p.get("name", "param")
                p_type = p.get("type", "String")
                param_obj = op.Parameters.AddNew(p_name, p_type)
                param_obj.Kind = p.get("kind", "in")
                param_obj.Update()
            op.Parameters.Refresh()

        el.Methods.Refresh()
        el.Update()

        return {
            "id": op.MethodID,
            "element_id": el.ElementID,
            "name": op.Name,
            "return_type": op.ReturnType,
            "visibility": op.Visibility
        }

    def format_decision_branches(
        self,
        diagram_id: int,
        decision_element_id: int
    ) -> Dict[str, Any]:
        """
        Formats all outgoing connectors from a decision element on a diagram
        so that branches exit horizontally at 90 degrees and drop down cleanly
        into target actions, matching professional BPMN/Activity diagram styling.
        """
        repo = self.get_repository()
        diag = repo.GetDiagramByID(int(diagram_id))
        if not diag:
            raise ValueError(f"Diagram {diagram_id} not found.")

        # Find decision DiagramObject
        d_obj = None
        for i in range(diag.DiagramObjects.Count):
            obj = diag.DiagramObjects.GetAt(i)
            if obj.ElementID == int(decision_element_id):
                d_obj = obj
                break

        if not d_obj:
            raise ValueError(f"Decision element {decision_element_id} not found on diagram {diagram_id}.")

        d_box = {
            "left": d_obj.left,
            "top": d_obj.top,
            "right": d_obj.right,
            "bottom": d_obj.bottom
        }

        # Map element_id -> diagram_object
        diag_objs = {}
        for i in range(diag.DiagramObjects.Count):
            obj = diag.DiagramObjects.GetAt(i)
            diag_objs[obj.ElementID] = obj

        # Map connector_id -> link
        diag_links = {}
        for i in range(diag.DiagramLinks.Count):
            link = diag.DiagramLinks.GetAt(i)
            diag_links[link.ConnectorID] = link

        dec_elem = repo.GetElementByID(int(decision_element_id))
        formatted_branches = []

        for i in range(dec_elem.Connectors.Count):
            conn = dec_elem.Connectors.GetAt(i)
            # Check if this connector originates from the decision node
            if conn.ClientID == dec_elem.ElementID:
                target_id = conn.SupplierID
                target_obj = diag_objs.get(target_id)
                link = diag_links.get(conn.ConnectorID)
                if target_obj and link:
                    t_box = {
                        "left": target_obj.left,
                        "top": target_obj.top,
                        "right": target_obj.right,
                        "bottom": target_obj.bottom
                    }
                    waypoint = calculate_decision_waypoints(d_box, t_box)
                    if waypoint:
                        link.LineStyle = 3  # Custom with exact waypoints
                        link.Path = waypoint
                    else:
                        link.LineStyle = 8  # Straight orthogonal
                    link.Update()
                    formatted_branches.append({
                        "connector_id": conn.ConnectorID,
                        "guard": getattr(conn, "TransitionGuard", "") or conn.Name,
                        "target_element_id": target_id,
                        "waypoint": waypoint
                    })

        diag.DiagramLinks.Refresh()
        diag.Update()
        try:
            repo.ReloadDiagram(diag.DiagramID)
        except Exception:
            pass

        return {
            "diagram_id": diag.DiagramID,
            "decision_id": decision_element_id,
            "formatted_branches": formatted_branches
        }

    def create_decision_node(
        self,
        package_id: int,
        name: str,
        diagram_id: int,
        left: int = 200,
        top: int = -80,
        right: int = 260,
        bottom: int = -130,
        incoming_element_id: Optional[int] = None,
        branches: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Creates a Decision Node diamond element and attaches it to the diagram,
        automatically configuring clean 90-degree orthogonal branches.
        branches format: [{'target_element_id': int, 'guard': 'Crear / Editar'}]
        """
        repo = self.get_repository()
        pkg = repo.GetPackageByID(int(package_id))
        if not pkg:
            raise ValueError(f"Package {package_id} not found.")

        # Create decision element
        dec = pkg.Elements.AddNew(name, "Decision")
        if not dec.Update():
            raise RuntimeError(f"Failed to create decision node: {dec.GetLastError()}")
        pkg.Elements.Refresh()

        # Add to diagram
        self.add_element_to_diagram(
            diagram_id=diagram_id,
            element_id=dec.ElementID,
            left=left,
            top=top,
            right=right,
            bottom=bottom
        )

        # Connect incoming element if provided
        if incoming_element_id is not None:
            self.create_connector(
                source_element_id=incoming_element_id,
                target_element_id=dec.ElementID,
                connector_type="ControlFlow",
                line_style="orthogonal_square",
                diagram_id=diagram_id
            )

        # Create branches
        created_branches = []
        if branches:
            for b in branches:
                tgt_id = b.get("target_element_id")
                guard = b.get("guard", "")
                if tgt_id:
                    conn_res = self.create_connector(
                        source_element_id=dec.ElementID,
                        target_element_id=tgt_id,
                        connector_type="ControlFlow",
                        name=guard,
                        guard=guard,
                        diagram_id=diagram_id
                    )
                    created_branches.append(conn_res)

            # Auto format the decision branches with clean 90-degree waypoints
            self.format_decision_branches(diagram_id, dec.ElementID)

        return {
            "decision_id": dec.ElementID,
            "name": dec.Name,
            "diagram_id": diagram_id,
            "branches": created_branches
        }

    # --------------------------------------------------------------------------
    # Connectors & Relationships
    # --------------------------------------------------------------------------

    # Line style mappings for DiagramLink.LineStyle
    LINE_STYLES = {
        "direct": 1,
        "auto": 2,
        "custom": 3,
        "tree_vertical": 4,
        "tree_horizontal": 5,
        "lateral_horizontal": 6,
        "lateral_vertical": 7,
        "orthogonal": 8,
        "orthogonal_square": 8,
        "orthogonal_rounded": 9,
    }

    def set_diagram_link_style(
        self,
        diagram_id: int,
        connector_id: Optional[int] = None,
        line_style: str = "orthogonal_square"
    ) -> Dict[str, Any]:
        """
        Sets the visual routing line style for connectors in a diagram.
        Styles: 'orthogonal_square' (90-degree right angles, recommended for clean diagrams),
        'orthogonal_rounded', 'direct', 'auto', 'tree_vertical', 'tree_horizontal'.
        If connector_id is None, applies to ALL connectors in the diagram.
        """
        repo = self.get_repository()
        diag = repo.GetDiagramByID(int(diagram_id))
        if not diag:
            raise ValueError(f"Diagram {diagram_id} not found.")

        style_val = self.LINE_STYLES.get(line_style.lower(), 8)
        updated_count = 0

        for i in range(diag.DiagramLinks.Count):
            link = diag.DiagramLinks.GetAt(i)
            if connector_id is None or link.ConnectorID == int(connector_id):
                link.LineStyle = style_val
                link.Update()
                updated_count += 1

        diag.DiagramLinks.Refresh()
        diag.Update()
        try:
            repo.ReloadDiagram(diag.DiagramID)
        except Exception:
            pass

        return {
            "diagram_id": diag.DiagramID,
            "line_style": line_style,
            "style_code": style_val,
            "updated_links_count": updated_count
        }

    def create_connector(
        self,
        source_element_id: int,
        target_element_id: int,
        connector_type: str = "Association",
        name: str = "",
        stereotype: str = "",
        direction: str = "Source -> Destination",
        guard: str = "",
        line_style: Optional[str] = "orthogonal_square",
        diagram_id: Optional[int] = None,
        notes: str = ""
    ) -> Dict[str, Any]:
        """
        Creates a connector between two elements.
        Types: 'Association', 'ControlFlow', 'Aggregation', 'Composition', 'Generalization',
        'Realization', 'Dependency', 'NoteLink', 'Usage', etc.
        guard: Transition guard condition (e.g. '[Crear / Editar]').
        line_style: Visual routing style ('orthogonal_square', 'orthogonal_rounded', 'direct', etc.).
        """
        repo = self.get_repository()
        src = repo.GetElementByID(int(source_element_id))
        if not src:
            raise ValueError(f"Source element {source_element_id} not found.")

        tgt = repo.GetElementByID(int(target_element_id))
        if not tgt:
            raise ValueError(f"Target element {target_element_id} not found.")

        conn = src.Connectors.AddNew(name, connector_type)
        conn.SupplierID = tgt.ElementID
        conn.Direction = direction
        if stereotype:
            conn.Stereotype = stereotype
        if guard:
            conn.TransitionGuard = guard
        if notes:
            conn.Notes = notes

        if not conn.Update():
            raise RuntimeError(f"Failed to create connector: {conn.GetLastError()}")

        src.Connectors.Refresh()
        src.Update()

        # If a diagram_id is provided and line_style is requested, apply the line style
        applied_style = None
        if diagram_id is not None and line_style:
            try:
                repo.ReloadDiagram(int(diagram_id))
                applied_style = self.set_diagram_link_style(
                    diagram_id=int(diagram_id),
                    connector_id=conn.ConnectorID,
                    line_style=line_style
                )
            except Exception:
                pass

        return {
            "id": conn.ConnectorID,
            "name": conn.Name,
            "type": conn.Type,
            "source_id": src.ElementID,
            "source_name": src.Name,
            "target_id": tgt.ElementID,
            "target_name": tgt.Name,
            "direction": conn.Direction,
            "guard": getattr(conn, "TransitionGuard", ""),
            "applied_style": applied_style,
            "notes": conn.Notes
        }

    def delete_connector(self, connector_id: int) -> bool:
        """Deletes a connector by ID."""
        repo = self.get_repository()
        conn = repo.GetConnectorByID(int(connector_id))
        if not conn:
            raise ValueError(f"Connector {connector_id} not found.")

        src = repo.GetElementByID(conn.ClientID)
        for i in range(src.Connectors.Count):
            c = src.Connectors.GetAt(i)
            if c.ConnectorID == conn.ConnectorID:
                src.Connectors.Delete(i)
                src.Connectors.Refresh()
                src.Update()
                return True
        return False

    # --------------------------------------------------------------------------
    # SQL Query & XML Parsing
    # --------------------------------------------------------------------------

    def sql_query(self, query: str) -> List[Dict[str, Any]]:
        """Executes a SQL SELECT query against EA's underlying model repository."""
        repo = self.get_repository()
        xml_result = repo.SQLQuery(query)
        return self._parse_ea_xml(xml_result)

    def _parse_ea_xml(self, xml_string: str) -> List[Dict[str, Any]]:
        """Parses Enterprise Architect XML query response into a list of dicts."""
        if not xml_string:
            return []
        try:
            root = ET.fromstring(xml_string)
            rows = []
            # Typical EA XML format:
            # <EADATA><Dataset_0><Data><Row><Field1>Val1</Field1>...</Row></Data></Dataset_0></EADATA>
            for row in root.findall(".//Row"):
                row_dict = {}
                for child in row:
                    row_dict[child.tag] = child.text or ""
                rows.append(row_dict)
            return rows
        except Exception:
            return [{"raw_xml": xml_string}]
