"""
Agente Juez (Judge LLM)
=========================
Evalúa la respuesta del Orquestador ANTES de que llegue al usuario.
No genera contenido nuevo — evalúa lo que ya se generó, como un
revisor independiente.

Criterios (los 4 que exige el enunciado, Sección 2.1):
1. Relevancia con el contexto RAG
2. Ausencia de alucinaciones (información inventada, no respaldada
   por el contexto)
3. Completitud (¿responde la pregunta completa, o falta algo?)
4. Claridad (¿se entiende bien?)

Umbral: 7.5/10 (mismo número del KPI #2 del dashboard de
observabilidad -- no es casualidad, es el mismo criterio de calidad
medido en dos lugares distintos: aquí como gate antes de responder,
y en el dashboard como métrica agregada en el tiempo).
"""

import json
import os

from google import genai

PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "my-first-project-123456-505714")
LOCATION = "us-central1"
MODELO_JUEZ = "gemini-2.5-flash"
UMBRAL_APROBACION = 7.5

client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)


def evaluar_respuesta(pregunta: str, contexto_rag: str, respuesta: str) -> dict:
    """
    Le pide a Gemini que actúe como evaluador independiente.
    Le pedimos JSON estructurado para poder leer el score
    automáticamente (no texto libre que haya que interpretar).
    """
    prompt = f"""Eres un evaluador de calidad independiente y estricto. NO generas
respuestas, solo evalúas una respuesta ya generada por otro sistema.

PREGUNTA DEL USUARIO:
{pregunta}

CONTEXTO QUE SE LE DIO AL SISTEMA (de documentos reales o datos de ventas):
{contexto_rag}

RESPUESTA QUE GENERÓ EL SISTEMA:
{respuesta}

Evalúa la respuesta en estos 4 criterios, cada uno de 0 a 10:
- relevancia: ¿la respuesta se relaciona con el contexto y la pregunta?
- sin_alucinaciones: ¿toda la información viene del contexto, sin inventar datos? (10 = nada inventado)
- completitud: ¿responde la pregunta completa?
- claridad: ¿es fácil de entender?

Responde ÚNICAMENTE con un JSON válido, sin texto adicional, con este formato exacto:
{{"relevancia": <numero>, "sin_alucinaciones": <numero>, "completitud": <numero>, "claridad": <numero>, "comentario": "<breve explicación de la nota>"}}
"""

    respuesta_gemini = client.models.generate_content(
        model=MODELO_JUEZ,
        contents=prompt,
    )

    try:
        texto_limpio = respuesta_gemini.text.strip().removeprefix("```json").removesuffix("```").strip()
        evaluacion = json.loads(texto_limpio)
    except (json.JSONDecodeError, AttributeError):
        # Si el Juez no devuelve JSON válido, es un fallo del propio
        # Juez -- no debe tumbar el sistema. Devolvemos una nota
        # conservadora y lo marcamos explícitamente como error.
        return {
            "score_final": 0,
            "aprobado": False,
            "error": "El Juez no devolvió un JSON válido",
        }

    criterios = ["relevancia", "sin_alucinaciones", "completitud", "claridad"]
    score_final = round(sum(evaluacion[c] for c in criterios) / len(criterios), 2)

    return {
        "score_final": score_final,
        "aprobado": score_final >= UMBRAL_APROBACION,
        "detalle": evaluacion,
    }


if __name__ == "__main__":
    # Ejemplo con una respuesta BUENA (fiel al contexto)
    resultado_bueno = evaluar_respuesta(
        pregunta="¿Cómo se revisan los frenos antes de cada paseo?",
        contexto_rag="Para frenos de contrapedal: aplicar presión hacia abajo en el pedal trasero cuando esté ligeramente más alto que la posición horizontal.",
        respuesta="Para revisar los frenos de contrapedal antes de cada paseo, coloca el pedal trasero ligeramente más alto que la posición horizontal y aplica presión hacia abajo; el freno debe activarse.",
    )
    print("--- Respuesta fiel al contexto ---")
    print(json.dumps(resultado_bueno, ensure_ascii=False, indent=2))

    # Ejemplo con una respuesta con ALUCINACIÓN (inventa un dato que no está en el contexto)
    resultado_malo = evaluar_respuesta(
        pregunta="¿Cómo se revisan los frenos antes de cada paseo?",
        contexto_rag="Para frenos de contrapedal: aplicar presión hacia abajo en el pedal trasero cuando esté ligeramente más alto que la posición horizontal.",
        respuesta="Debes revisar los frenos cada 500 kilómetros y cambiar las pastillas cada 6 meses según el fabricante.",
    )
    print("\n--- Respuesta con datos inventados ---")
    print(json.dumps(resultado_malo, ensure_ascii=False, indent=2))
