"""
RAG — Búsqueda semántica (retrieval)
=======================================
Dado una pregunta del usuario, encuentra los 'k' chunks más parecidos
en significado, usando similitud coseno entre embeddings.

Esta es la mitad de RAG que faltaba: ingesta.py guarda los chunks,
este archivo los busca.
"""

import json
import os
from pathlib import Path

from google import genai

PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "my-first-project-123456-505714")
LOCATION = "us-central1"
MODELO_EMBEDDINGS = "text-embedding-004"

ARCHIVO_VECTOR_STORE = Path(__file__).parent / "vector_store_local.json"

client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)


def _generar_embedding(texto: str) -> list[float]:
    """Igual que en ingesta.py: convierte texto en su vector de embedding."""
    respuesta = client.models.embed_content(
        model=MODELO_EMBEDDINGS,
        contents=texto,
    )
    return respuesta.embeddings[0].values


def _similitud_coseno(vector_a: list[float], vector_b: list[float]) -> float:
    """
    Calcula qué tan parecidos son dos vectores (entre -1 y 1).
    Cuanto más cerca de 1, más parecidos en significado.
    No usamos ninguna librería externa aquí a propósito, para que
    veas la fórmula matemática real detrás del concepto.
    """
    producto_punto = sum(a * b for a, b in zip(vector_a, vector_b))
    magnitud_a = sum(a * a for a in vector_a) ** 0.5
    magnitud_b = sum(b * b for b in vector_b) ** 0.5
    if magnitud_a == 0 or magnitud_b == 0:
        return 0.0
    return producto_punto / (magnitud_a * magnitud_b)


def _cargar_chunks() -> list[dict]:
    with open(ARCHIVO_VECTOR_STORE, encoding="utf-8") as f:
        return json.load(f)


def buscar_chunks_relevantes(pregunta: str, k: int = 3) -> list[dict]:
    """
    Punto de entrada. Devuelve los 'k' chunks más relevantes para la
    pregunta, ordenados de más a menos relevante. Cada resultado
    incluye su score de similitud (útil también para el KPI de
    'Cobertura del Corpus RAG' que exige el dashboard).
    """
    chunks = _cargar_chunks()
    embedding_pregunta = _generar_embedding(pregunta)

    resultados = []
    for chunk in chunks:
        score = _similitud_coseno(embedding_pregunta, chunk["embedding"])
        resultados.append({
            "texto": chunk["texto"],
            "fuente": chunk["fuente"],
            "score": round(score, 4),
        })

    resultados.sort(key=lambda r: r["score"], reverse=True)
    return resultados[:k]


if __name__ == "__main__":
    pregunta = "¿Cómo se revisan los frenos antes de cada paseo?"
    print(f"Pregunta: {pregunta}\n")

    top_chunks = buscar_chunks_relevantes(pregunta, k=3)
    for i, chunk in enumerate(top_chunks, start=1):
        print(f"--- Resultado {i} (score={chunk['score']}, fuente={chunk['fuente']}) ---")
        print(chunk["texto"][:200] + "...")
        print()
