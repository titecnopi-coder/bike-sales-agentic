"""
Tool: Consulta de Datos de Ventas -- versión Cloud SQL (PostgreSQL real)
============================================================================
Antes leía un CSV local. Ahora consulta la tabla 'ventas' en Cloud SQL
con SQL real -- esto es lo que exige el enunciado: al menos una tool
debe consultar datos reales (BigQuery, PostgreSQL, o API REST).
"""

import os
from google.cloud.sql.connector import Connector
import sqlalchemy

PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "my-first-project-123456-505714")
REGION = "us-central1"
INSTANCIA = "bike-sales-db"
BASE_DE_DATOS = "bike_sales"
USUARIO = "postgres"
CONTRASENA = os.environ.get("DB_PASSWORD")

connector = Connector()


def _conectar():
    conexion_string = f"{PROJECT_ID}:{REGION}:{INSTANCIA}"
    return connector.connect(
        conexion_string, "pg8000",
        user=USUARIO, password=CONTRASENA, db=BASE_DE_DATOS,
    )


TOOL_SCHEMA = {
    "name": "consultar_ventas",
    "description": (
        "Consulta datos reales de ventas de bicicletas (desde PostgreSQL en "
        "Cloud SQL): unidades vendidas e ingresos totales, con la opción de "
        "filtrar por categoría de producto (Montaña, Urbana, Ruta). Úsala "
        "siempre que el usuario pregunte por cifras de ventas."
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


def consultar_ventas(categoria: str) -> dict:
    """
    Ejecuta una consulta SQL real contra la tabla 'ventas' en Cloud SQL.
    Nunca lanza una excepción sin controlar (mismo criterio de siempre,
    por el KPI de éxito de tools).
    """
    try:
        engine = sqlalchemy.create_engine("postgresql+pg8000://", creator=_conectar)
        with engine.connect() as conn:
            if categoria == "todas":
                query = sqlalchemy.text("""
                    SELECT COALESCE(SUM(unidades_vendidas), 0) AS unidades,
                           COALESCE(SUM(ingresos), 0) AS ingresos,
                           COUNT(*) AS registros
                    FROM ventas;
                """)
                fila = conn.execute(query).mappings().first()
            else:
                query = sqlalchemy.text("""
                    SELECT COALESCE(SUM(unidades_vendidas), 0) AS unidades,
                           COALESCE(SUM(ingresos), 0) AS ingresos,
                           COUNT(*) AS registros
                    FROM ventas
                    WHERE categoria = :categoria;
                """)
                fila = conn.execute(query, {"categoria": categoria}).mappings().first()

        if fila["registros"] == 0:
            return {
                "categoria": categoria,
                "unidades_totales": 0,
                "ingresos_totales": 0,
                "advertencia": "No se encontraron datos para esa categoría.",
            }

        # Convertimos explícitamente a int -- PostgreSQL puede devolver
        # SUM() de una columna BIGINT como tipo Decimal, que no es
        # compatible con JSON al mandarlo de vuelta a Gemini.
        return {
            "categoria": categoria,
            "unidades_totales": int(fila["unidades"]),
            "ingresos_totales": int(fila["ingresos"]),
            "registros_encontrados": int(fila["registros"]),
        }

    except Exception as e:
        return {"categoria": categoria, "error": f"No se pudo consultar los datos: {e}"}


if __name__ == "__main__":
    print("Ventas de Montaña:", consultar_ventas("Montaña"))
    print("Ventas totales:", consultar_ventas("todas"))
