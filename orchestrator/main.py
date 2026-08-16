"""
Orquestador — versión integrada (los 5 patrones trabajando juntos)
======================================================================
Flujo completo:
1. Gemini recibe la pregunta + 3 tools disponibles (calculadora,
   consulta de ventas, búsqueda en documentos con RAG+reranking)
2. Gemini decide cuál (o ninguna) necesita
3. Se ejecuta la tool real, el resultado vuelve a Gemini
4. Gemini arma la respuesta final
5. El Agente Juez evalúa esa respuesta contra el contexto usado
6. Si el Juez la rechaza (score < 7.5), se le pide a Gemini que la
   refine usando el comentario del Juez -- loop de refinamiento
7. Se devuelve la respuesta final (aprobada o la mejor tras refinar)
"""

import os
from google import genai
from google.genai import types

from tools.calculadora_metricas import TOOL_SCHEMA as SCHEMA_CALCULADORA, calcular_metrica
from tools.consulta_ventas import TOOL_SCHEMA as SCHEMA_VENTAS, consultar_ventas
from rag.reranking import buscar_con_reranking
from judge.main import evaluar_respuesta

PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "my-first-project-123456-505714")
LOCATION = "us-central1"
MODEL = "gemini-2.5-flash"
MAX_INTENTOS_REFINAMIENTO = 1  # cuántas veces se le pide a Gemini que mejore la respuesta

client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)


# --- Tool nueva: búsqueda en documentos (envuelve RAG + Reranking) -----
SCHEMA_BUSQUEDA_DOCS = {
    "name": "buscar_en_documentos",
    "description": (
        "Busca información en los documentos del corpus (manuales de "
        "bicicletas, reportes de mercado, documentación de proyectos). "
        "Úsala para preguntas sobre mantenimiento, seguridad, uso de "
        "bicicletas, o tendencias del mercado -- no para cifras de "
        "ventas propias (para eso usa consultar_ventas)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "consulta": {
                "type": "string",
                "description": "La pregunta o tema a buscar en los documentos.",
            }
        },
        "required": ["consulta"],
    },
}


def _ejecutar_busqueda_docs(args: dict) -> dict:
    resultados = buscar_con_reranking(args["consulta"], k_candidatos=10, k_final=3)
    return {
        "chunks_encontrados": [
            {"texto": r["texto"], "fuente": r["fuente"]} for r in resultados
        ]
    }


def _schema_a_function_declaration(schema: dict) -> types.FunctionDeclaration:
    return types.FunctionDeclaration(
        name=schema["name"],
        description=schema["description"],
        parameters=schema["input_schema"],
    )


TOOLS = types.Tool(function_declarations=[
    _schema_a_function_declaration(SCHEMA_CALCULADORA),
    _schema_a_function_declaration(SCHEMA_VENTAS),
    _schema_a_function_declaration(SCHEMA_BUSQUEDA_DOCS),
])

EJECUTORES = {
    "calcular_metrica_negocio": lambda args: calcular_metrica(**args),
    "consultar_ventas": lambda args: consultar_ventas(**args),
    "buscar_en_documentos": _ejecutar_busqueda_docs,
}


def _generar_respuesta(pregunta: str, feedback_refinamiento: str = "") -> tuple[str, str]:
    """
    Ejecuta el flujo de tool calling (pasos 1-4 del docstring).
    Devuelve (respuesta_final_texto, contexto_usado_para_el_juez).
    Si feedback_refinamiento no está vacío, se lo agrega a la pregunta
    para pedirle a Gemini que corrija su intento anterior.
    """
    prompt = pregunta
    if feedback_refinamiento:
        prompt = (
            f"{pregunta}\n\n"
            f"[Tu respuesta anterior fue evaluada y rechazada por este motivo: "
            f"{feedback_refinamiento}. Genera una respuesta mejor, corrigiendo eso.]"
        )

    contents = [types.Content(role="user", parts=[types.Part(text=prompt)])]

    response = client.models.generate_content(
        model=MODEL, contents=contents,
        config=types.GenerateContentConfig(tools=[TOOLS]),
    )
    parte = response.candidates[0].content.parts[0]

    contexto_usado = ""

    if parte.function_call:
        nombre_tool = parte.function_call.name
        argumentos = dict(parte.function_call.args)
        print(f"[Orquestador] Usando tool: {nombre_tool}({argumentos})")

        resultado = EJECUTORES[nombre_tool](argumentos)
        contexto_usado = str(resultado)

        contents.append(response.candidates[0].content)
        contents.append(types.Content(
            role="user",
            parts=[types.Part.from_function_response(
                name=nombre_tool, response={"resultado": resultado},
            )],
        ))
        respuesta_final = client.models.generate_content(
            model=MODEL, contents=contents,
            config=types.GenerateContentConfig(tools=[TOOLS]),
        )
        return respuesta_final.text, contexto_usado

    return parte.text, contexto_usado


def procesar_pregunta(pregunta: str) -> dict:
    """
    Punto de entrada público. Devuelve un dict con la respuesta final
    y la información del Juez, para que quede trazabilidad completa
    (útil también para el logging estructurado que exige el enunciado).
    """
    respuesta, contexto = _generar_respuesta(pregunta)
    evaluacion = evaluar_respuesta(pregunta, contexto, respuesta)

    intentos = 0
    while not evaluacion["aprobado"] and intentos < MAX_INTENTOS_REFINAMIENTO:
        intentos += 1
        comentario = evaluacion.get("detalle", {}).get("comentario", "calidad insuficiente")
        print(f"[Juez] Respuesta rechazada (score={evaluacion['score_final']}). Refinando... intento {intentos}")

        respuesta, contexto = _generar_respuesta(pregunta, feedback_refinamiento=comentario)
        evaluacion = evaluar_respuesta(pregunta, contexto, respuesta)

    return {
        "respuesta": respuesta,
        "score_juez": evaluacion["score_final"],
        "aprobado": evaluacion["aprobado"],
        "intentos_refinamiento": intentos,
    }


if __name__ == "__main__":
    preguntas = [
        "¿Cuál es el margen bruto si tuve 1000000 en ingresos y 650000 en costos?",
        "¿Cuántas bicicletas de montaña vendimos en total?",
        "¿Cómo se revisan los frenos antes de cada paseo?",
    ]
    for p in preguntas:
        print(f"\n{'='*60}\nPregunta: {p}\n{'='*60}")
        resultado = procesar_pregunta(p)
        print(f"\nRespuesta final: {resultado['respuesta']}")
        print(f"Score del Juez: {resultado['score_juez']}/10 | Aprobado: {resultado['aprobado']} | Refinamientos: {resultado['intentos_refinamiento']}")
