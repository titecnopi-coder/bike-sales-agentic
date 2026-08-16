"""
RAG — Búsqueda semántica (retrieval) -- versión Cloud SQL / pgvector
========================================================================
Misma función que la versión anterior (buscar_chunks_relevantes), pero
ahora consulta la base de datos real en la nube en vez del archivo
JSON local. pgvector calcula la similitud directamente en SQL con el
operador '<=>' (distancia coseno), así que ya no necesitamos calcular
la similitud a mano en Python.
"""

import os

from google import genai
from google.cloud.sql.connector import Connector
import sqlalchemy

PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "my-first-project-123456-505714")
LOCATION = "us-central1"
MODELO_EMBEDDINGS = "text-embedding-004"

REGION = "us-central1"
INSTANCIA = "bike-sales-db"
BASE_DE_DATOS = "bike_sales"
USUARIO = "postgres"
CONTRASENA = os.environ.get("DB_PASSWORD")

client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)
connector = Connector()


def _conectar():
    conexion_string = f"{PROJECT_ID}:{REGION}:{INSTANCIA}"
    return connector.connect(
        conexion_string, "pg8000",
        user=USUARIO, password=CONTRASENA, db=BASE_DE_DATOS,
    )


def _generar_embedding(texto: str) -> list[float]:
    respuesta = client.models.embed_content(model=MODELO_EMBEDDINGS, contents=texto)
    return respuesta.embeddings[0].values


def buscar_chunks_relevantes(pregunta: str, k: int = 3) -> list[dict]:
    """
    Igual firma y comportamiento que antes (para no romper nada de lo
    que ya usa esta función, como rag/reranking.py), pero ahora
    consulta pgvector en Cloud SQL en vez del JSON local.

    El operador '<=>' de pgvector calcula distancia coseno (0 = idénticos).
    Como queremos SIMILITUD (más alto = más parecido, igual que antes),
    convertimos: similitud = 1 - distancia.
    """
    if not CONTRASENA:
        raise RuntimeError("Falta DB_PASSWORD. Corre: set DB_PASSWORD=tu_contrasena")

    embedding_pregunta = _generar_embedding(pregunta)

    engine = sqlalchemy.create_engine("postgresql+pg8000://", creator=_conectar)
    with engine.connect() as conn:
        resultado = conn.execute(
            sqlalchemy.text("""
                SELECT texto, fuente, 1 - (embedding <=> :query_vector) AS score
                FROM chunks
                ORDER BY embedding <=> :query_vector
                LIMIT :k;
            """),
            {"query_vector": str(embedding_pregunta), "k": k},
        )
        filas = resultado.fetchall()

    connector.close()

    return [
        {"texto": fila.texto, "fuente": fila.fuente, "score": round(fila.score, 4)}
        for fila in filas
    ]


if __name__ == "__main__":
    pregunta = "¿Cómo se revisan los frenos antes de cada paseo?"
    print(f"Pregunta: {pregunta}\n")

    top_chunks = buscar_chunks_relevantes(pregunta, k=3)
    for i, chunk in enumerate(top_chunks, start=1):
        print(f"--- Resultado {i} (score={chunk['score']}, fuente={chunk['fuente']}) ---")
        print(chunk["texto"][:200] + "...")
        print()
