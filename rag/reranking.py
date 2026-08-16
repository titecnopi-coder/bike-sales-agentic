"""
RAG — Reranking (LLM-based)
==============================
Toma un grupo grande de chunks candidatos (traídos por similitud
coseno) y le pide a Gemini que evalúe la relevancia REAL de cada uno
frente a la pregunta, en una escala de 0 a 10. Reordena según esa
nota y devuelve solo los mejores.

Por qué "LLM-based" y no "cross-encoder":
Un cross-encoder es un modelo especializado más rápido para esto,
pero requiere descargar e instalar un modelo aparte (más peso,
más configuración). Usar el mismo Gemini que ya tenemos configurado
es más simple para el tiempo que tenemos, y el enunciado acepta
explícitamente esta alternativa ("cross-encoder o LLM-based").
Esto es una decisión de diseño real -- va documentada en el
Documento de Arquitectura, sección Reranking.
"""

import os

from google import genai

from rag.busqueda import buscar_chunks_relevantes

PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "my-first-project-123456-505714")
LOCATION = "us-central1"
MODELO_RERANKING = "gemini-2.5-flash"

client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)


def _evaluar_relevancia(pregunta: str, chunk_texto: str) -> int:
    """
    Le pide a Gemini una nota de 0 a 10 de qué tan relevante es
    este chunk específico para responder la pregunta.
    Pedimos SOLO el número para poder convertirlo directo a entero,
    sin tener que interpretar una respuesta larga.
    """
    prompt = (
        f"Pregunta del usuario: {pregunta}\n\n"
        f"Fragmento de texto:\n{chunk_texto}\n\n"
        "En una escala de 0 a 10, ¿qué tan relevante es este fragmento "
        "para responder la pregunta? Responde ÚNICAMENTE con el número, "
        "sin texto adicional."
    )

    respuesta = client.models.generate_content(
        model=MODELO_RERANKING,
        contents=prompt,
    )

    try:
        return int(respuesta.text.strip())
    except (ValueError, AttributeError):
        # Si Gemini no responde un número limpio, asumimos relevancia media
        # en vez de tumbar todo el pipeline (mismo criterio de las tools:
        # nunca dejar que un fallo pequeño rompa el flujo completo).
        return 5


def buscar_con_reranking(pregunta: str, k_candidatos: int = 10, k_final: int = 3) -> list[dict]:
    """
    Punto de entrada del patrón completo:
    1. Trae k_candidatos por similitud coseno (búsqueda rápida, amplia)
    2. Le pide a Gemini una nota de relevancia real a cada uno
    3. Reordena y devuelve solo los k_final mejores
    """
    candidatos = buscar_chunks_relevantes(pregunta, k=k_candidatos)

    for candidato in candidatos:
        candidato["score_reranking"] = _evaluar_relevancia(pregunta, candidato["texto"])

    candidatos.sort(key=lambda c: c["score_reranking"], reverse=True)
    return candidatos[:k_final]


if __name__ == "__main__":
    pregunta = "¿Cómo se revisan los frenos antes de cada paseo?"
    print(f"Pregunta: {pregunta}\n")

    resultados = buscar_con_reranking(pregunta, k_candidatos=10, k_final=3)
    for i, r in enumerate(resultados, start=1):
        print(f"--- #{i} | score_coseno={r['score']} | score_reranking={r['score_reranking']}/10 | fuente={r['fuente']} ---")
        print(r["texto"][:200] + "...")
        print()
