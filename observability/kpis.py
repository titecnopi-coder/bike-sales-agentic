"""
Observabilidad — Cálculo de los 8 KPIs
==========================================
Consulta la tabla 'logs' y calcula los 8 KPIs que exige el enunciado
(Sección 4). Se usa desde el endpoint /metricas de la API.
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


def calcular_kpis() -> dict:
    """
    Calcula los 8 KPIs a partir de todos los registros históricos.
    Cada KPI trae su valor y su umbral (para que el frontend pueda
    pintar en verde/rojo según si se cumple o no).
    """
    engine = sqlalchemy.create_engine("postgresql+pg8000://", creator=_conectar)

    with engine.connect() as conn:
        fila = conn.execute(sqlalchemy.text("""
            SELECT
                COUNT(*) AS total_consultas,
                COUNT(*) FILTER (WHERE tool_usada IS NOT NULL) AS total_con_tool,
                COUNT(*) FILTER (WHERE tool_exitosa = true) AS tools_exitosas,
                AVG(score_juez) AS score_juez_promedio,
                PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latencia_total_ms) AS ttl_p95_ms,
                AVG(costo_estimado_usd) AS costo_promedio,
                COUNT(*) FILTER (WHERE score_sin_alucinaciones < 7) AS con_alucinacion,
                COUNT(*) FILTER (WHERE score_sin_alucinaciones IS NOT NULL) AS total_evaluados,
                PERCENTILE_CONT(0.95) WITHIN GROUP (
                    ORDER BY latencia_rag_ms
                ) FILTER (WHERE latencia_rag_ms IS NOT NULL) AS rag_p95_ms,
                COUNT(*) FILTER (WHERE mejor_score_rag >= 0.75) AS rag_con_buena_cobertura,
                COUNT(*) FILTER (WHERE mejor_score_rag IS NOT NULL) AS total_rag,
                AVG(tokens_entrada + tokens_salida) AS tokens_promedio
            FROM logs;
        """)).mappings().first()

    # NOTA: no cerramos 'connector' -- ver comentario en logger.py.
    total = fila["total_consultas"] or 0
    total_con_tool = fila["total_con_tool"] or 0
    total_rag = fila["total_rag"] or 0
    total_evaluados = fila["total_evaluados"] or 0

    def pct(numerador, denominador):
        return round((numerador / denominador) * 100, 1) if denominador else None

    tasa_exito = pct(fila["tools_exitosas"] or 0, total_con_tool)
    score_juez = round(fila["score_juez_promedio"], 2) if fila["score_juez_promedio"] else None
    ttl_p95 = round(fila["ttl_p95_ms"] / 1000, 2) if fila["ttl_p95_ms"] else None
    costo_prom = round(fila["costo_promedio"], 5) if fila["costo_promedio"] else None
    tasa_alucinacion = pct(fila["con_alucinacion"] or 0, total_evaluados)
    rag_latencia = round(fila["rag_p95_ms"] / 1000, 2) if fila["rag_p95_ms"] else None
    cobertura_rag = pct(fila["rag_con_buena_cobertura"] or 0, total_rag)
    tokens_prom = round(fila["tokens_promedio"]) if fila["tokens_promedio"] else None

    return {
        "1_tasa_exito_tools": {
            "valor": tasa_exito, "unidad": "%", "umbral": ">= 95%",
            "cumple": None if tasa_exito is None else tasa_exito >= 95,
        },
        "2_score_juez_promedio": {
            "valor": score_juez, "unidad": "/10", "umbral": ">= 7.5",
            "cumple": None if score_juez is None else score_juez >= 7.5,
        },
        "3_time_to_last_token_p95": {
            "valor": ttl_p95, "unidad": "s", "umbral": "< 10s (p95)",
            "cumple": None if ttl_p95 is None else ttl_p95 < 10,
        },
        "4_costo_promedio_por_consulta": {
            "valor": costo_prom, "unidad": "USD", "umbral": "< $0.05",
            "cumple": None if costo_prom is None else costo_prom < 0.05,
        },
        "5_tasa_alucinacion": {
            "valor": tasa_alucinacion, "unidad": "%", "umbral": "< 5%",
            "cumple": None if tasa_alucinacion is None else tasa_alucinacion < 5,
        },
        "6_latencia_rag_p95": {
            "valor": rag_latencia, "unidad": "s", "umbral": "< 2s (p95)",
            "cumple": None if rag_latencia is None else rag_latencia < 2,
        },
        "7_cobertura_corpus_rag": {
            "valor": cobertura_rag, "unidad": "%", "umbral": ">= 80%",
            "cumple": None if cobertura_rag is None else cobertura_rag >= 80,
        },
        "8_tokens_promedio": {
            "valor": tokens_prom, "unidad": "tokens", "umbral": "baseline",
            "cumple": None,
        },
        "total_consultas_registradas": total,
    }
