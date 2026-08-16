"""
Orquestador — versión con observabilidad integrada
======================================================
Mismo flujo de siempre (Tools + RAG + Reranking + Juez), pero ahora
cada consulta:
1. Se cronometra (tiempo total, y tiempo de RAG por separado)
2. Cuenta tokens de entrada/salida de cada llamada a Gemini
3. Calcula un costo estimado
4. Guarda todo como un registro estructurado en la tabla 'logs'

Esto alimenta los 8 KPIs del dashboard de observabilidad.
"""

import os
from google import genai
from google.genai import types

from tools.calculadora_metricas import TOOL_SCHEMA as SCHEMA_CALCULADORA, calcular_metrica
from tools.consulta_ventas import TOOL_SCHEMA as SCHEMA_VENTAS, consultar_ventas
from tools.generador_reportes import TOOL_SCHEMA as SCHEMA_REPORTE, generar_reporte_ventas
from rag.reranking import buscar_con_reranking
from judge.main import evaluar_respuesta
from observability.logger import nuevo_request_id, calcular_costo, guardar_log, Cronometro

PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "my-first-project-123456-505714")
LOCATION = "us-central1"
MODEL = "gemini-2.5-flash"
MAX_INTENTOS_REFINAMIENTO = 1

client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)


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
            "consulta": {"type": "string", "description": "La pregunta o tema a buscar en los documentos."}
        },
        "required": ["consulta"],
    },
}

_ULTIMO_LATENCIA_RAG_MS = {"valor": None}
_ULTIMO_MEJOR_SCORE_RAG = {"valor": None}


def _ejecutar_busqueda_docs(args: dict) -> dict:
    crono_rag = Cronometro()
    resultados = buscar_con_reranking(args["consulta"], k_candidatos=10, k_final=3)
    _ULTIMO_LATENCIA_RAG_MS["valor"] = crono_rag.transcurrido_ms()
    _ULTIMO_MEJOR_SCORE_RAG["valor"] = max((r["score"] for r in resultados), default=0)
    return {"chunks_encontrados": [{"texto": r["texto"], "fuente": r["fuente"]} for r in resultados]}


def _schema_a_function_declaration(schema: dict) -> types.FunctionDeclaration:
    return types.FunctionDeclaration(
        name=schema["name"], description=schema["description"], parameters=schema["input_schema"],
    )


TOOLS = types.Tool(function_declarations=[
    _schema_a_function_declaration(SCHEMA_CALCULADORA),
    _schema_a_function_declaration(SCHEMA_VENTAS),
    _schema_a_function_declaration(SCHEMA_REPORTE),
    _schema_a_function_declaration(SCHEMA_BUSQUEDA_DOCS),
])

EJECUTORES = {
    "calcular_metrica_negocio": lambda args: calcular_metrica(**args),
    "consultar_ventas": lambda args: consultar_ventas(**args),
    "generar_reporte_ventas": lambda args: generar_reporte_ventas(**args),
    "buscar_en_documentos": _ejecutar_busqueda_docs,
}


def _contar_tokens(response) -> tuple[int, int]:
    """Extrae tokens de entrada/salida de la respuesta de Gemini."""
    try:
        uso = response.usage_metadata
        return uso.prompt_token_count or 0, uso.candidates_token_count or 0
    except AttributeError:
        return 0, 0


def _generar_respuesta(pregunta: str, feedback_refinamiento: str = "") -> dict:
    """
    Ejecuta el flujo de tool calling. Devuelve un dict con todo lo
    necesario para el log, no solo el texto de la respuesta.
    """
    prompt = pregunta
    if feedback_refinamiento:
        prompt = f"{pregunta}\n\n[Tu respuesta anterior fue rechazada: {feedback_refinamiento}. Corrígela.]"

    contents = [types.Content(role="user", parts=[types.Part(text=prompt)])]
    tokens_entrada_total = 0
    tokens_salida_total = 0

    response = client.models.generate_content(
        model=MODEL, contents=contents, config=types.GenerateContentConfig(tools=[TOOLS]),
    )
    te, ts = _contar_tokens(response)
    tokens_entrada_total += te
    tokens_salida_total += ts

    parte = response.candidates[0].content.parts[0]
    contexto_usado = ""
    tool_usada = None
    tool_exitosa = None

    if parte.function_call:
        tool_usada = parte.function_call.name
        argumentos = dict(parte.function_call.args)
        print(f"[Orquestador] Usando tool: {tool_usada}({argumentos})")

        try:
            resultado = EJECUTORES[tool_usada](argumentos)
            tool_exitosa = "error" not in resultado if isinstance(resultado, dict) else True
        except Exception as e:
            resultado = {"error": str(e)}
            tool_exitosa = False

        contexto_usado = str(resultado)

        contents.append(response.candidates[0].content)
        contents.append(types.Content(
            role="user",
            parts=[types.Part.from_function_response(name=tool_usada, response={"resultado": resultado})],
        ))
        respuesta_final = client.models.generate_content(
            model=MODEL, contents=contents, config=types.GenerateContentConfig(tools=[TOOLS]),
        )
        te2, ts2 = _contar_tokens(respuesta_final)
        tokens_entrada_total += te2
        tokens_salida_total += ts2

        return {
            "texto": respuesta_final.text,
            "contexto": contexto_usado,
            "tool_usada": tool_usada,
            "tool_exitosa": tool_exitosa,
            "tokens_entrada": tokens_entrada_total,
            "tokens_salida": tokens_salida_total,
        }

    return {
        "texto": parte.text,
        "contexto": contexto_usado,
        "tool_usada": None,
        "tool_exitosa": None,
        "tokens_entrada": tokens_entrada_total,
        "tokens_salida": tokens_salida_total,
    }


def procesar_pregunta(pregunta: str) -> dict:
    """Punto de entrada público, con logging estructurado completo."""
    request_id = nuevo_request_id()
    crono_total = Cronometro()
    _ULTIMO_LATENCIA_RAG_MS["valor"] = None
    _ULTIMO_MEJOR_SCORE_RAG["valor"] = None

    resultado = _generar_respuesta(pregunta)
    evaluacion = evaluar_respuesta(pregunta, resultado["contexto"], resultado["texto"])

    intentos = 0
    while not evaluacion["aprobado"] and intentos < MAX_INTENTOS_REFINAMIENTO:
        intentos += 1
        comentario = evaluacion.get("detalle", {}).get("comentario", "calidad insuficiente")
        resultado_previo = resultado
        resultado = _generar_respuesta(pregunta, feedback_refinamiento=comentario)
        resultado["tokens_entrada"] += resultado_previo["tokens_entrada"]
        resultado["tokens_salida"] += resultado_previo["tokens_salida"]
        evaluacion = evaluar_respuesta(pregunta, resultado["contexto"], resultado["texto"])

    latencia_total_ms = crono_total.transcurrido_ms()
    costo = calcular_costo(resultado["tokens_entrada"], resultado["tokens_salida"])
    score_sin_alucinaciones = evaluacion.get("detalle", {}).get("sin_alucinaciones")

    guardar_log({
        "request_id": request_id,
        "pregunta": pregunta,
        "modelo": MODEL,
        "tool_usada": resultado["tool_usada"],
        "tool_exitosa": resultado["tool_exitosa"],
        "tokens_entrada": resultado["tokens_entrada"],
        "tokens_salida": resultado["tokens_salida"],
        "latencia_total_ms": latencia_total_ms,
        "latencia_rag_ms": _ULTIMO_LATENCIA_RAG_MS["valor"],
        "score_juez": evaluacion["score_final"],
        "score_sin_alucinaciones": score_sin_alucinaciones,
        "mejor_score_rag": _ULTIMO_MEJOR_SCORE_RAG["valor"],
        "aprobado": evaluacion["aprobado"],
        "costo_estimado_usd": costo,
    })

    return {
        "respuesta": resultado["texto"],
        "score_juez": evaluacion["score_final"],
        "aprobado": evaluacion["aprobado"],
        "intentos_refinamiento": intentos,
        "tool_usada": resultado["tool_usada"],
    }


if __name__ == "__main__":
    print(procesar_pregunta("¿Cuántas bicicletas de montaña vendimos en total?"))
