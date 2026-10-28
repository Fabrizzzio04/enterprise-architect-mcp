# Enterprise Architect MCP Server (v13.5+)

Servidor MCP (**Model Context Protocol**) para automatizar y controlar **Sparx Systems Enterprise Architect v13.5 (Build 1351)** y versiones superiores mediante su API de Automatización COM en Windows.

Permite a los asistentes de IA crear, consultar, modificar y organizar diagramas UML, modelar elementos (clases, casos de uso, componentes, actores), crear conectores y relaciones, y exportar diagramas a imágenes PNG de alta resolución.

---

## Estructura del Proyecto

- `server.py`: Servidor MCP principal con las herramientas expuestas (Tools) sobre transporte `stdio`.
- `ea_controller.py`: Capa de integración COM con `EA.App` y `EA.Repository` de Enterprise Architect.
- `ea_coords.py`: Utilidades de cálculo de coordenadas y auto-posicionamiento en cuadrícula (grid) para diagramas.
- `test_ea_connection.py`: Suite de verificación automatizada.
- `requirements.txt`: Dependencias de Python (`pywin32`, `mcp`).

---

## Herramientas Expuestas (MCP Tools)

### Conexión y Navegación
- `ea_connect(file_path=None)`: Conecta a la sesión activa de EA o abre un archivo `.eap`/`.eapx`/`.feap`.
- `ea_get_status()`: Consulta el estado de la conexión, modelo activo y diagrama abierto.
- `ea_list_packages(parent_package_id=None)`: Lista los paquetes raíz o subpaquetes.
- `ea_create_package(name, parent_package_id=None)`: Crea un nuevo paquete en el modelo.

### Diagramas (Creación y Edición)
- `ea_create_workflow_diagram(package_id, diagram_name, lanes, steps, notes)`: Genera un diagrama de flujo/actividad vertical completo en **1 solo paso**, organizando carriles, aplicando dimensiones estándar, colores corporativos de EA y conexiones ortogonales a 90° con waypoints automáticos.
- `ea_polish_diagram(diagram_id, theme="classic")`: **Comando maestro de normalización**. Corrige y pule cualquier diagrama existente de golpe (resetea dimensiones a estándar, preserva y extiende carriles/swimlanes, aplica colores corporativos de EA, fuerza líneas a 90° y bifurca simétricamente todas las decisiones).
- `ea_respread_and_fix_workflow(diagram_id, vertical_gap=48)`: Reorganiza y respacia verticalmente los elementos de un flujo con una separación limpia y holgada (48px por defecto). **Soluciona las flechas cortas/pegadas entre objetos del mismo carril**, estira todos los carriles/swimlanes hasta el fondo y alinea las decisiones a 90°.
- `ea_fix_swimlanes(diagram_id)`: Restaura y extiende los carriles verticales (`ActivityPartition`) de un diagrama para que cubran desde el encabezado hasta más allá de la última acción con su orden Z en el fondo.
- `ea_set_element_appearance(element_id, diagram_id, bg_color, border_color, border_width)`: Personaliza la apariencia visual y paleta de un elemento en el diagrama.
- `ea_create_diagram(package_id, name, diagram_type, notes)`: Crea un nuevo diagrama (ej. `Class`, `Logical`, `Sequence`, `Use Case`, `Component`, `Activity`, `Statechart`).
- `ea_get_diagram(diagram_id)`: Obtiene los elementos colocados, sus coordenadas rectangulares (`left`, `top`, `right`, `bottom`) y los enlaces/conectores visibles.
- `ea_add_element_to_diagram(diagram_id, element_id, left, top, right, bottom)`: Agrega un elemento existente al lienzo de un diagrama.
- `ea_update_diagram_object(diagram_id, element_id, left, top, right, bottom, sequence)`: Mueve o redimensiona un elemento en el diagrama.
- `ea_remove_from_diagram(diagram_id, element_id)`: Quita un elemento de la vista del diagrama sin borrarlo del modelo.
- `ea_set_connector_style(diagram_id, connector_id=None, line_style="orthogonal_square")`: Modifica el enrutamiento visual de líneas (ej. `orthogonal_square` a 90°, `orthogonal_rounded`, `direct`, etc.).
- `ea_create_decision_node(package_id, name, diagram_id, left, top, right, bottom, incoming_element_id, branches)`: Crea un rombo de decisión simétrico y bifurca ramas limpiamente a 90° con etiquetas de guarda (`[Crear / Editar]`, `[Dar de Baja]`).
- `ea_format_decision_branches(diagram_id, decision_element_id)`: Corrige y alinea automáticamente las ramas de un rombo de decisión existente para que salgan en ángulo recto horizontal y bajen a 90° hacia las acciones destino.
- `ea_export_diagram_image(diagram_id, output_path=None)`: Exporta una captura renderizada en PNG del diagrama.
- `ea_calculate_grid_layout(element_count, columns, ...)`: Calcula una distribución espacial uniforme para múltiples elementos.

### Elementos y Relaciones
- `ea_create_element(package_id, name, element_type, stereotype, notes, add_to_diagram_id, ...)`: Crea un elemento (`Class`, `Interface`, `Actor`, `UseCase`, etc.) y opcionalmente lo dibuja directamente en un diagrama.
- `ea_get_element(element_id)`: Obtiene información detallada de un elemento, incluyendo sus atributos, métodos y conectores.
- `ea_update_element(element_id, name, notes, stereotype)`: Edita las propiedades de un elemento.
- `ea_delete_element(element_id)`: Elimina un elemento del modelo.
- `ea_add_attribute(element_id, name, attr_type, visibility, default_value)`: Añade un atributo/campo a una clase.
- `ea_add_operation(element_id, name, return_type, visibility, parameters)`: Añade un método a una clase.
- `ea_create_connector(source_element_id, target_element_id, connector_type, name, direction)`: Conecta dos elementos (`Association`, `Dependency`, `Generalization`, `Realization`, `Composition`, `Aggregation`, etc.).
- `ea_delete_connector(connector_id)`: Elimina un conector.
- `ea_sql_query(query)`: Ejecuta una consulta SQL directa sobre la base de datos subyacente del modelo.

---

## Configuración en Antigravity / Claude Desktop / Cursor

En tu archivo de configuración de servidores MCP (por ejemplo `C:\Users\Master\.gemini\config\mcp_config.json`):

```json
{
  "mcpServers": {
    "enterprise-architect": {
      "command": "C:\\Users\\Master\\.gemini\\antigravity\\scratch\\ea-mcp\\.venv\\Scripts\\python.exe",
      "args": [
        "C:\\Users\\Master\\.gemini\\antigravity\\scratch\\ea-mcp\\server.py"
      ]
    }
  }
}
```
