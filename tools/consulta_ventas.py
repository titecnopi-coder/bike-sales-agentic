"""
Tool: Consulta de Datos de Ventas
===================================

Qué hace
--------
Responde preguntas sobre ventas: total de unidades e ingresos, filtrando
opcionalmente por categoría de producto.

Por qué existe
---------------
El enunciado exige que al menos una Tool consulte "datos reales"
(BigQuery, PostgreSQL o API REST). HOY la construimos leyendo un CSV
local, para tener el patrón completo funcionando sin depender de que
tu cuenta de GCP ya esté lista. Cuando la tengas, solo cambiamos la
función `_cargar_datos()` para que en vez de leer el CSV, haga una
consulta SQL a BigQuery. El resto (el schema, la función pública
`consultar_ventas`) no cambia — por eso separamos "cómo se obtienen
los datos" de "qué se hace con ellos".
"""

import csv
from pathlib import Path

RUTA_CSV = Path(__file__).parent / "datos_ventas_ejemplo.csv"


# ---------------------------------------------------------------------------
# 1. Schema JSON de la tool
# ---------------------------------------------------------------------------
TOOL_SCHEMA = {
    "name": "consultar_ventas",
    "description": (
        "Consulta datos reales de ventas de bicicletas: unidades vendidas "
        "e ingresos totales, con la opción de filtrar por categoría de "
        "producto (Montaña, Urbana, Ruta). Úsala siempre que el usuario "
        "pregunte por cifras de ventas, no inventes números."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "categoria": {
                "type": "string",
                "enum": ["Montaña", "Urbana", "Ruta", "todas"],
                "description": "Categoría de producto a consultar, o 'todas' para el total general.",
            }
        },
        "required": ["categoria"],
    },
}


# ---------------------------------------------------------------------------
# 2. Implementación real
# ---------------------------------------------------------------------------
def _cargar_datos() -> list[dict]:
    """
    HOY: lee el CSV local.
    DESPUÉS (con GCP listo): esta función se reemplaza por una consulta
    SQL real a BigQuery, por ejemplo:
        SELECT fecha, producto, categoria, unidades_vendidas, ingresos
        FROM `proyecto.dataset.ventas`
    El resto del archivo no se toca.
    """
    with open(RUTA_CSV, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def consultar_ventas(categoria: str) -> dict:
    """
    Devuelve unidades totales e ingresos totales, filtrando por categoría
    si se pide. Nunca lanza una excepción sin controlar (mismo criterio
    que la tool anterior, por el KPI de éxito de tools).
    """
    try:
        filas = _cargar_datos()

        if categoria != "todas":
            filas = [f for f in filas if f["categoria"] == categoria]

        if not filas:
            return {
                "categoria": categoria,
                "unidades_totales": 0,
                "ingresos_totales": 0,
                "advertencia": "No se encontraron datos para esa categoría.",
            }

        unidades_totales = sum(int(f["unidades_vendidas"]) for f in filas)
        ingresos_totales = sum(int(f["ingresos"]) for f in filas)

        return {
            "categoria": categoria,
            "unidades_totales": unidades_totales,
            "ingresos_totales": ingresos_totales,
            "registros_encontrados": len(filas),
        }

    except (FileNotFoundError, KeyError, ValueError) as e:
        return {
            "categoria": categoria,
            "error": f"No se pudo consultar los datos: {e}",
        }


# ---------------------------------------------------------------------------
# 3. Prueba manual rápida
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("Ventas de Montaña:", consultar_ventas("Montaña"))
    print("Ventas totales:", consultar_ventas("todas"))
