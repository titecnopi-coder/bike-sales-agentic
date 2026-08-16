"""
Observabilidad — Crear tabla de logs
=======================================
Crea la tabla 'logs' en Cloud SQL, donde cada consulta al sistema
deja un registro estructurado. A partir de esta tabla se calculan
los 8 KPIs que exige el enunciado (ver observability/kpis.py).

Correr UNA SOLA VEZ.
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


def crear_tabla():
    if not CONTRASENA:
        print("Falta DB_PASSWORD. Corre: set DB_PASSWORD=tu_contrasena")
        return

    engine = sqlalchemy.create_engine("postgresql+pg8000://", creator=_conectar)
    with engine.connect() as conn:
        conn.execute(sqlalchemy.text("""
            CREATE TABLE IF NOT EXISTS logs (
                id SERIAL PRIMARY KEY,
                request_id TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT NOW(),
                pregunta TEXT,
                modelo TEXT,
                tool_usada TEXT,
                tool_exitosa BOOLEAN,
                tokens_entrada INTEGER,
                tokens_salida INTEGER,
                latencia_total_ms INTEGER,
                latencia_rag_ms INTEGER,
                score_juez FLOAT,
                score_sin_alucinaciones FLOAT,
                mejor_score_rag FLOAT,
                aprobado BOOLEAN,
                costo_estimado_usd FLOAT
            );
        """))
        conn.commit()
        print("Tabla 'logs' creada (o ya existía).")

    connector.close()


if __name__ == "__main__":
    crear_tabla()
