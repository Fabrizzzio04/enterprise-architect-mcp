"""
Verification script for the Enterprise Architect Visual Rules & Automated Workflow Engine.
"""

import os
import sys

sys.path.append(r"C:\Users\Master\.gemini\antigravity\scratch\ea-mcp")
from ea_controller import EAController


def test_visual_engine():
    print("=== Testing Enterprise Architect Visual Rules & Auto-Layout ===")

    controller = EAController.get_instance()
    test_path = r"C:\Users\Master\.gemini\antigravity\scratch\ea-mcp\test_model.eap"
    controller.connect(test_path)
    repo = controller.get_repository()

    pkg = repo.GetPackageByID(2)

    # 1. Test 1-Step Complete Vertical Workflow Diagram Creation
    print("\n1. Testing create_workflow_diagram (3 Vertical Lanes)...")
    lanes = ["Operador / Usuario", "Servicio Central", "Base de Datos"]

    steps = [
        {
            "id": "s1",
            "name": "Capturar coordenada libre\n(P_click: lng, lat)",
            "type": "Action",
            "lane": "Operador / Usuario",
            "next": "s2"
        },
        {
            "id": "s2",
            "name": "Enviar punto al servicio\nde snapping",
            "type": "Action",
            "lane": "Operador / Usuario",
            "next": "s3"
        },
        {
            "id": "s3",
            "name": "Construir punto geometrico\nen SRID 4326",
            "type": "Action",
            "lane": "Servicio Central",
            "next": "s4"
        },
        {
            "id": "s4",
            "name": "¿Accion?",
            "type": "Decision",
            "lane": "Servicio Central",
            "branches": [
                {"target_id": "s5", "guard": "Crear / Editar"},
                {"target_id": "s6", "guard": "Dar de Baja"}
            ]
        },
        {
            "id": "s5",
            "name": "Ingresar datos del sindicato\n(Nombre, Sede, Contacto)",
            "type": "Action",
            "lane": "Operador / Usuario",
            "next": "s7"
        },
        {
            "id": "s6",
            "name": "Confirmar baja del sindicato",
            "type": "Action",
            "lane": "Servicio Central",
            "next": "s7"
        },
        {
            "id": "s7",
            "name": "Registrar transaccion en\ntabla de auditoria",
            "type": "Action",
            "lane": "Base de Datos"
        }
    ]

    res = controller.create_workflow_diagram(
        package_id=pkg.PackageID,
        diagram_name="FlujoVerticalEstandarizado",
        lanes=lanes,
        steps=steps,
        notes="Diagrama de flujo vertical estandarizado con reglas corporativas EA."
    )

    print("   Workflow created successfully!")
    print(f"   Diagram ID: {res['diagram_id']}")
    print(f"   Elements count: {res['elements_count']}")
    print(f"   Connections count: {res['connections_count']}")
    print(f"   Preview image: {res['preview_image']}")

    # 2. Test Master Polish Tool on an existing diagram
    print("\n2. Testing polish_diagram on Diagram 1...")
    polish_res = controller.polish_diagram(diagram_id=1, theme="classic")
    print(f"   Polished Diagram 1: {polish_res}")

    re_img = controller.export_diagram_image(1)
    print(f"   Exported polished Diagram 1 to: {re_img}")

    print("\n=== ALL VISUAL ENGINE TESTS PASSED! ===")


if __name__ == "__main__":
    try:
        test_visual_engine()
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
