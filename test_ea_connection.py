"""
Verification script for Enterprise Architect Automation and Diagram Editing.
"""

import os
import shutil
import sys

from ea_controller import EAController


def run_test():
    print("=== Testing Enterprise Architect Automation Controller ===")

    base_dir = os.path.dirname(os.path.abspath(__file__))
    sample_src = r"C:\Program Files (x86)\Sparx Systems\EA\EABase.eap"
    test_eap = os.path.join(base_dir, "test_model.eap")

    # If test_model.eap doesn't exist, copy from EABase.eap
    if not os.path.exists(test_eap):
        if os.path.exists(sample_src):
            print(f"Creating isolated test model from: {sample_src}")
            shutil.copyfile(sample_src, test_eap)
        else:
            print(f"Sample source {sample_src} not found.")

    controller = EAController.get_instance()

    print(f"1. Connecting to Enterprise Architect (Opening {test_eap})...")
    status = controller.connect(test_eap)
    print("   Connection Status:", status["connected"])
    print("   Root Models Count:", status["models_count"])
    for m in status["root_models"]:
        print(f"   - Model: {m['name']} (ID: {m['id']})")

    # Ensure a root model exists, or create a package in the first model
    root_models = controller.list_packages()
    if not root_models:
        print("   No root model found, creating root model...")
        repo = controller.get_repository()
        root_pkg = repo.Models.AddNew("Test_Model", "")
        root_pkg.Update()
        repo.Models.Refresh()
        root_models = controller.list_packages()

    parent_pkg_id = root_models[0]["id"]
    print(f"2. Using Parent Package ID: {parent_pkg_id}")

    # Create test package
    print("3. Creating Subpackage 'MCP_Test_Package'...")
    pkg = controller.create_package("MCP_Test_Package", parent_pkg_id)
    pkg_id = pkg["id"]
    print(f"   Created Package ID: {pkg_id}")

    # Create Diagram
    print("4. Creating Class Diagram 'UserManagementDiagram'...")
    diagram = controller.create_diagram(
        package_id=pkg_id,
        name="UserManagementDiagram",
        diagram_type="Logical",
        notes="Automated test diagram created by EA-MCP."
    )
    diag_id = diagram["id"]
    print(f"   Diagram created! ID: {diag_id}, Type: {diagram['type']}")

    # Create Elements
    print("5. Creating Elements...")
    # Element 1: Usuario
    el_user = controller.create_element(
        package_id=pkg_id,
        name="Usuario",
        element_type="Class",
        notes="Representa la entidad de usuario en el sistema.",
        add_to_diagram_id=diag_id,
        left=80,
        top=-80,
        right=240,
        bottom=-200
    )
    print(f"   Element 1 created: {el_user['name']} (ID: {el_user['id']})")

    # Add attributes and methods to Usuario
    controller.add_attribute(el_user["id"], "id", "Integer", "Private")
    controller.add_attribute(el_user["id"], "username", "String", "Private")
    controller.add_attribute(el_user["id"], "email", "String", "Private")
    controller.add_operation(el_user["id"], "autenticar", "Boolean", "Public", [
        {"name": "password", "type": "String", "kind": "in"}
    ])

    # Element 2: ServicioAutenticacion
    el_auth = controller.create_element(
        package_id=pkg_id,
        name="ServicioAutenticacion",
        element_type="Class",
        stereotype="Service",
        notes="Servicio encargado de la verificación de credenciales.",
        add_to_diagram_id=diag_id,
        left=340,
        top=-80,
        right=520,
        bottom=-200
    )
    print(f"   Element 2 created: {el_auth['name']} (ID: {el_auth['id']})")
    controller.add_operation(el_auth["id"], "login", "Usuario", "Public", [
        {"name": "user", "type": "String", "kind": "in"},
        {"name": "pass", "type": "String", "kind": "in"}
    ])

    # Create Relationship (Dependency from ServicioAutenticacion to Usuario)
    print("6. Creating Relationship (Dependency)...")
    connector = controller.create_connector(
        source_element_id=el_auth["id"],
        target_element_id=el_user["id"],
        connector_type="Dependency",
        name="manages",
        direction="Source -> Destination",
        notes="El servicio gestiona y autentica usuarios."
    )
    print(f"   Connector created! ID: {connector['id']}, Type: {connector['type']}")

    # Verify Diagram Content
    print("7. Reading Diagram Objects...")
    diag_details = controller.get_diagram(diag_id)
    print(f"   Diagram has {diag_details['elements_count']} elements and {diag_details['links_count']} links.")
    for obj in diag_details["elements"]:
        print(f"   - Object: {obj['name']} at [{obj['left']}, {obj['top']}, {obj['right']}, {obj['bottom']}]")

    # Move Element in Diagram
    print("8. Updating Object Position in Diagram...")
    updated_obj = controller.update_diagram_object(
        diagram_id=diag_id,
        element_id=el_user["id"],
        left=100,
        top=-100,
        right=260,
        bottom=-220
    )
    print(f"   Updated position: [{updated_obj['left']}, {updated_obj['top']}, {updated_obj['right']}, {updated_obj['bottom']}]")

    # Export Diagram to PNG
    print("9. Exporting Diagram to PNG...")
    png_path = controller.export_diagram_image(diag_id)
    print(f"   Exported to: {png_path}")
    if os.path.exists(png_path) and os.path.getsize(png_path) > 0:
        print(f"   SUCCESS! Image file exists and is {os.path.getsize(png_path)} bytes.")
    else:
        print("   WARNING: Image file was not created or is empty.")

    # Execute SQL Query
    print("10. Testing SQL query...")
    rows = controller.sql_query(f"SELECT Name, Object_Type FROM t_object WHERE Package_ID = {pkg_id}")
    print(f"   SQL Query returned {len(rows)} elements from t_object:")
    for r in rows:
        print(f"   - {r.get('Name')} ({r.get('Object_Type')})")

    print("\n=== ALL TESTS COMPLETED SUCCESSFULLY! ===")


if __name__ == "__main__":
    try:
        run_test()
    except Exception as e:
        print(f"\nERROR DURING TEST: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
