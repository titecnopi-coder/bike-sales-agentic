"""
Tool: Calculadora de Métricas de Negocio
==========================================

Qué hace
--------
Calcula métricas de negocio estándar (margen, crecimiento, ticket promedio)
a partir de cifras que el Orchestrator o un sub-worker le pasan.

Por qué existe
---------------
El enunciado (Sección 2.1) pide al menos 3 Tools, una de las cuales debe
consultar datos reales (esa la construimos aparte, en bigquery_ventas.py).
Esta es una tool "de cómputo puro": no llama a ninguna API externa, solo
aplica fórmulas de negocio. Sirve para que el LLM delegue cálculos exactos
en vez de intentar hacer aritmética "a ojo" dentro del texto generado
(fuente común de alucinaciones numéricas).

Cómo se conecta con el LLM (tool calling)
------------------------------------------
1. TOOL_SCHEMA es lo que se le envía al LLM (Gemini vía Vertex AI) en cada
   llamada. Es el "contrato": nombre, descripción y parámetros esperados.
2. El LLM, si decide que necesita esta tool, responde con un tool_call que
   incluye los argumentos según ese schema.
3. Nuestro código (el Orchestrator) toma esos argumentos y ejecuta
   calcular_metrica() de verdad.
4. El resultado se devuelve al LLM como "tool result" para que lo use en
   su respuesta final.
"""

from typing import Literal

# ---------------------------------------------------------------------------
# 1. Schema JSON de la tool (esto es lo que exige documentar el enunciado)
# ---------------------------------------------------------------------------
TOOL_SCHEMA = {
    "name": "calcular_metrica_negocio",
    "description": (
        "Calcula una métrica de negocio estándar (margen bruto, crecimiento "
        "porcentual o ticket promedio) a partir de cifras numéricas. "
        "Úsala siempre que el usuario pida un cálculo exacto sobre ventas, "
        "costos o ingresos, en vez de estimarlo en el texto."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "metrica": {
                "type": "string",
                "enum": ["margen_bruto", "crecimiento_porcentual", "ticket_promedio"],
                "description": "Qué métrica calcular.",
            },
            "valores": {
                "type": "object",
                "description": (
                    "Valores de entrada requeridos según la métrica:\n"
                    "- margen_bruto: {ingresos, costos}\n"
                    "- crecimiento_porcentual: {valor_actual, valor_anterior}\n"
                    "- ticket_promedio: {ingresos_totales, numero_transacciones}"
                ),
            },
        },
        "required": ["metrica", "valores"],
    },
}


# ---------------------------------------------------------------------------
# 2. Implementación real (lo que se ejecuta cuando el LLM llama la tool)
# ---------------------------------------------------------------------------
class MetricaInvalidaError(ValueError):
    """Se lanza cuando faltan valores o la métrica no existe."""


def calcular_metrica(
    metrica: Literal["margen_bruto", "crecimiento_porcentual", "ticket_promedio"],
    valores: dict,
) -> dict:
    """
    Ejecuta el cálculo real. Siempre devuelve un dict con 'resultado' y
    'detalle', nunca lanza excepciones sin controlar (importante para el
    KPI de "Tasa de Éxito de Tools" del dashboard: un error no controlado
    aquí cuenta como falla de la tool).
    """
    try:
        if metrica == "margen_bruto":
            ingresos = valores["ingresos"]
            costos = valores["costos"]
            if ingresos <= 0:
                raise MetricaInvalidaError(
                    "Los ingresos deben ser un valor positivo mayor que cero "
                    "(no tiene sentido de negocio calcular margen con ingresos "
                    "negativos o en cero)."
                )
            resultado = round((ingresos - costos) / ingresos * 100, 2)
            return {
                "resultado": resultado,
                "unidad": "%",
                "detalle": f"Margen bruto = ({ingresos} - {costos}) / {ingresos} * 100",
            }

        if metrica == "crecimiento_porcentual":
            actual = valores["valor_actual"]
            anterior = valores["valor_anterior"]
            if anterior == 0:
                raise MetricaInvalidaError("valor_anterior no puede ser 0")
            resultado = round((actual - anterior) / anterior * 100, 2)
            return {
                "resultado": resultado,
                "unidad": "%",
                "detalle": f"Crecimiento = ({actual} - {anterior}) / {anterior} * 100",
            }

        if metrica == "ticket_promedio":
            ingresos_totales = valores["ingresos_totales"]
            n_transacciones = valores["numero_transacciones"]
            if n_transacciones == 0:
                raise MetricaInvalidaError("numero_transacciones no puede ser 0")
            resultado = round(ingresos_totales / n_transacciones, 2)
            return {
                "resultado": resultado,
                "unidad": "moneda",
                "detalle": f"Ticket promedio = {ingresos_totales} / {n_transacciones}",
            }

        raise MetricaInvalidaError(f"Métrica no soportada: {metrica}")

    except KeyError as e:
        raise MetricaInvalidaError(f"Falta el valor requerido: {e}") from e


# ---------------------------------------------------------------------------
# 3. Prueba manual rápida (esto luego se formaliza en tests/test_tools.py)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    ejemplo = calcular_metrica(
        "margen_bruto", {"ingresos": 1_000_000, "costos": 650_000}
    )
    print(ejemplo)
