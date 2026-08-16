"""
Migración de datos de ventas a Cloud SQL
============================================
Crea la tabla 'ventas' en la misma base de datos Cloud SQL que ya
usamos para el RAG, y carga ahí los datos que antes vivían en un CSV
local. Esto convierte 'consultar_ventas' en una tool que consulta
datos reales en PostgreSQL, tal como exige el enunciado (Sección 2.1).

Correr UNA SOLA VEZ.
"""

import csv
import os
from pathlib import Path

from google.cloud.sql.connector import Connector
import sqlalchemy

PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "my-first-project-123456-505714")
REGION = "us-central1"
INSTANCIA = "bike-sales-db"
BASE_DE_DATOS = "bike_sales"
USUARIO = "postgres"
CONTRASENA = os.environ.get("DB_PASSWORD")

RUTA_CSV = Path(__file__).parent.parent / "tools" / "datos_ventas_ejemplo.csv"

connector = Connector()


def _conectar():
    conexion_string = f"{PROJECT_ID}:{REGION}:{INSTANCIA}"
    return connector.connect(
        conexion_string, "pg8000",
        user=USUARIO, password=CONTRASENA, db=BASE_DE_DATOS,
    )


def migrar():
    if not CONTRASENA:
        print("Falta DB_PASSWORD. Corre: set DB_PASSWORD=tu_contrasena")
        return

    engine = sqlalchemy.create_engine("postgresql+pg8000://", creator=_conectar)

    with engine.connect() as conn:
        conn.execute(sqlalchemy.text("""
            CREATE TABLE IF NOT EXISTS ventas (
                id SERIAL PRIMARY KEY,
                fecha DATE,
                producto TEXT,
                categoria TEXT,
                unidades_vendidas INTEGER,
                ingresos BIGINT
            );
        """))
        conn.commit()

        with open(RUTA_CSV, encoding="utf-8") as f:
            filas = list(csv.DictReader(f))

        conn.execute(sqlalchemy.text("DELETE FROM ventas;"))
        for fila in filas:
            conn.execute(
                sqlalchemy.text("""
                    INSERT INTO ventas (fecha, producto, categoria, unidades_vendidas, ingresos)
                    VALUES (:fecha, :producto, :categoria, :unidades, :ingresos);
                """),
                {
                    "fecha": fila["fecha"],
                    "producto": fila["producto"],
                    "categoria": fila["categoria"],
                    "unidades": int(fila["unidades_vendidas"]),
                    "ingresos": int(fila["ingresos"]),
                },
            )
        conn.commit()
        print(f"Migradas {len(filas)} filas a la tabla 'ventas' en Cloud SQL.")


if __name__ == "__main__":
    migrar()
