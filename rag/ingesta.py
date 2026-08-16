"""
RAG — Ingesta de documentos
=============================
Lee todos los documentos de rag/corpus/ (PDFs y Markdown), los divide
en chunks, genera un embedding para cada chunk con Vertex AI, y guarda
todo en un archivo local (vector_store_local.json).

Por qué guardamos local por ahora:
Todavía no tienes Cloud SQL con pgvector configurado. Este archivo
JSON cumple la misma función mientras tanto: es una lista de chunks,
cada uno con su vector de embedding. Cuando tengas pgvector listo,
solo cambiamos la función guardar_chunks() para que haga INSERT en
la base de datos en vez de escribir un JSON — el resto (ingesta,
chunking, embeddings) no cambia.
"""

import json
import os
from pathlib import Path

from pypdf import PdfReader
from google import genai

PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "my-first-project-123456-505714")
LOCATION = "us-central1"
MODELO_EMBEDDINGS = "text-embedding-004"

CARPETA_CORPUS = Path(__file__).parent / "corpus"
ARCHIVO_SALIDA = Path(__file__).parent / "vector_store_local.json"

TAMANO_CHUNK = 800   # caracteres
OVERLAP = 100         # caracteres de traslape entre chunks

client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)


def _leer_pdf(ruta: Path) -> str:
    """Extrae todo el texto de un PDF, página por página."""
    lector = PdfReader(ruta)
    return "\n".join(pagina.extract_text() or "" for pagina in lector.pages)


def _leer_documento(ruta: Path) -> str:
    """Lee un documento según su extensión (hoy: .pdf y .md)."""
    if ruta.suffix.lower() == ".pdf":
        return _leer_pdf(ruta)
    return ruta.read_text(encoding="utf-8")


def _trocear_texto(texto: str, tamano: int = TAMANO_CHUNK, overlap: int = OVERLAP) -> list[str]:
    """
    Divide un texto largo en pedazos de 'tamano' caracteres, con
    'overlap' caracteres repetidos entre pedazos consecutivos.
    """
    chunks = []
    inicio = 0
    while inicio < len(texto):
        fin = inicio + tamano
        chunk = texto[inicio:fin].strip()
        if chunk:
            chunks.append(chunk)
        inicio += tamano - overlap
    return chunks


def _generar_embedding(texto: str) -> list[float]:
    """Genera el vector de embedding de un texto usando Vertex AI."""
    respuesta = client.models.embed_content(
        model=MODELO_EMBEDDINGS,
        contents=texto,
    )
    return respuesta.embeddings[0].values


def ingerir_corpus():
    """Punto de entrada: procesa todos los documentos y guarda el resultado."""
    if not CARPETA_CORPUS.exists():
        print(f"No existe la carpeta {CARPETA_CORPUS}. Crea rag/corpus/ primero.")
        return

    documentos = [
        f for f in CARPETA_CORPUS.iterdir()
        if f.suffix.lower() in (".pdf", ".md")
    ]

    if not documentos:
        print(f"No hay documentos en {CARPETA_CORPUS}. Agrega tus PDFs/README ahí.")
        return

    print(f"Encontrados {len(documentos)} documentos: {[d.name for d in documentos]}")

    todos_los_chunks = []
    for doc in documentos:
        print(f"\nProcesando: {doc.name}")
        texto = _leer_documento(doc)
        chunks = _trocear_texto(texto)
        print(f"  -> {len(chunks)} chunks generados")

        for i, chunk in enumerate(chunks):
            embedding = _generar_embedding(chunk)
            todos_los_chunks.append({
                "id": f"{doc.stem}_{i}",
                "fuente": doc.name,
                "texto": chunk,
                "embedding": embedding,
            })
            print(f"  -> chunk {i+1}/{len(chunks)} embebido")

    with open(ARCHIVO_SALIDA, "w", encoding="utf-8") as f:
        json.dump(todos_los_chunks, f, ensure_ascii=False)

    print(f"\nListo. {len(todos_los_chunks)} chunks guardados en {ARCHIVO_SALIDA}")


if __name__ == "__main__":
    ingerir_corpus()
