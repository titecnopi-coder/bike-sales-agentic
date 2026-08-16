"""
RAG — Migración a Cloud SQL (pgvector)
==========================================
Toma los chunks ya generados (rag/vector_store_local.json) y los
inserta en una tabla real de PostgreSQL en Cloud SQL, usando la
extensión pgvector para poder buscar por similitud con SQL directo.

Esto reemplaza el archivo JSON local por la base de datos vectorial
en la nube que exige el enunciado. Correr UNA SOLA VEZ (o cada vez
que se regenere el corpus).
"""

import json
import os
from pathlib import Path

from google.cloud.sql.connector import Connector
import sqlalchemy

PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "my-first-project-123456-505714")
REGION = "us-central1"
INSTANCIA = "bike-sales-db"
BASE_DE_DATOS = "bike_sales"
USUARIO = "postgres"
# Por seguridad, la contraseña se lee de una variable de entorno,
# nunca se escribe directo en el código (esto también va documentado
# como buena práctica en tu Documento de Arquitectura).
CONTRASENA = os.environ.get("DB_PASSWORD")

ARCHIVO_JSON = Path(__file__).parent / "vector_store_local.json"
DIMENSION_EMBEDDING = 768  # text-embedding-004 genera vectores de 768 dimensiones

connector = Connector()


def _conectar():
    """Abre una conexión a Cloud SQL usando el Connector oficial de Google."""
    conexion_string = f"{PROJECT_ID}:{REGION}:{INSTANCIA}"
    conn = connector.connect(
        conexion_string,
        "pg8000",
        user=USUARIO,
        password=CONTRASENA,
        db=BASE_DE_DATOS,
    )
    return conn


def migrar():
    if not CONTRASENA:
        print("Falta la contraseña. Corre esto antes, con tu contraseña real:")
        print('  set DB_PASSWORD=tu_contrasena_aqui   (Windows, cmd)')
        return

    engine = sqlalchemy.create_engine("postgresql+pg8000://", creator=_conectar)

    with engine.connect() as conn:
        # 1. Activar la extensión pgvector (una sola vez por base de datos)
        print("Activando extensión pgvector...")
        conn.execute(sqlalchemy.text("CREATE EXTENSION IF NOT EXISTS vector;"))

        # 2. Crear la tabla si no existe
        print("Creando tabla 'chunks' (si no existe)...")
        conn.execute(sqlalchemy.text(f"""
            CREATE TABLE IF NOT EXISTS chunks (
                id TEXT PRIMARY KEY,
                fuente TEXT NOT NULL,
                texto TEXT NOT NULL,
                embedding vector({DIMENSION_EMBEDDING})
            );
        """))
        conn.commit()

        # 3. Cargar los chunks del JSON local
        with open(ARCHIVO_JSON, encoding="utf-8") as f:
            chunks = json.load(f)
        print(f"Migrando {len(chunks)} chunks...")

        # 4. Insertar cada chunk (ON CONFLICT evita duplicados si se
        #    vuelve a correr el script con los mismos IDs)
        for i, chunk in enumerate(chunks):
            conn.execute(
                sqlalchemy.text("""
                    INSERT INTO chunks (id, fuente, texto, embedding)
                    VALUES (:id, :fuente, :texto, :embedding)
                    ON CONFLICT (id) DO UPDATE SET
                        fuente = EXCLUDED.fuente,
                        texto = EXCLUDED.texto,
                        embedding = EXCLUDED.embedding;
                """),
                {
                    "id": chunk["id"],
                    "fuente": chunk["fuente"],
                    "texto": chunk["texto"],
                    "embedding": str(chunk["embedding"]),  # pgvector acepta el formato '[0.1, 0.2, ...]'
                },
            )
            if (i + 1) % 20 == 0:
                print(f"  -> {i + 1}/{len(chunks)} migrados")

        conn.commit()
        print(f"\nListo. {len(chunks)} chunks migrados a Cloud SQL (tabla 'chunks').")

    connector.close()


if __name__ == "__main__":
    migrar()
