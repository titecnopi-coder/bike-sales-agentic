"""
Observabilidad — Logger estructurado
========================================
Guarda un registro de cada consulta en la tabla 'logs' de Cloud SQL.
Este archivo se usa desde el Orquestador -- no se corre solo.

Precios de referencia (Gemini 2.5 Flash, USD por 1M tokens, ago 2026):
Estos son precios PÚBLICOS aproximados -- se documentan como tal en
el Documento de Arquitectura, no son un compromiso exacto de facturación.
"""

import os
import time
import uuid

from google.cloud.sql.connector import Connector
import sqlalchemy

PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "my-first-project-123456-505714")
REGION = "us-central1"
INSTANCIA = "bike-sales-db"
BASE_DE_DATOS = "bike_sales"
USUARIO = "postgres"
CONTRASENA = os.environ.get("DB_PASSWORD")

# Precios de referencia (USD por millón de tokens) -- ajustar si Google
# actualiza su tabla de precios oficial.
PRECIO_INPUT_POR_MILLON = 0.075
PRECIO_OUTPUT_POR_MILLON = 0.30

connector = Connector()


def _conectar():
    conexion_string = f"{PROJECT_ID}:{REGION}:{INSTANCIA}"
    return connector.connect(
        conexion_string, "pg8000",
        user=USUARIO, password=CONTRASENA, db=BASE_DE_DATOS,
    )


def nuevo_request_id() -> str:
    return str(uuid.uuid4())


def calcular_costo(tokens_entrada: int, tokens_salida: int) -> float:
    costo = (
        (tokens_entrada / 1_000_000) * PRECIO_INPUT_POR_MILLON
        + (tokens_salida / 1_000_000) * PRECIO_OUTPUT_POR_MILLON
    )
    return round(costo, 6)


def guardar_log(registro: dict):
    """
    Inserta un registro en la tabla 'logs'. Nunca lanza una excepción
    hacia arriba -- si falla el logging, no debe tumbar la respuesta
    al usuario (el logging es una capa secundaria, no crítica).
    """
    if not CONTRASENA:
        print("[Logger] Falta DB_PASSWORD, no se guardó el log.")
        return

    try:
        engine = sqlalchemy.create_engine("postgresql+pg8000://", creator=_conectar)
        with engine.connect() as conn:
            conn.execute(
                sqlalchemy.text("""
                    INSERT INTO logs (
                        request_id, pregunta, modelo, tool_usada, tool_exitosa,
                        tokens_entrada, tokens_salida, latencia_total_ms,
                        latencia_rag_ms, score_juez, score_sin_alucinaciones,
                        mejor_score_rag, aprobado, costo_estimado_usd
                    ) VALUES (
                        :request_id, :pregunta, :modelo, :tool_usada, :tool_exitosa,
                        :tokens_entrada, :tokens_salida, :latencia_total_ms,
                        :latencia_rag_ms, :score_juez, :score_sin_alucinaciones,
                        :mejor_score_rag, :aprobado, :costo_estimado_usd
                    );
                """),
                registro,
            )
            conn.commit()
        # NOTA: no cerramos 'connector' aquí -- la API queda corriendo de
        # forma continua en Cloud Run, y closer un connector compartido
        # tumba las siguientes consultas en el mismo proceso. Se abre
        # una vez al importar este módulo y vive mientras la API viva.
    except Exception as e:
        # Log secundario -- no debe romper la respuesta al usuario.
        print(f"[Logger] No se pudo guardar el log: {e}")


class Cronometro:
    """Pequeño helper para medir milisegundos transcurridos."""
    def __init__(self):
        self._inicio = time.perf_counter()

    def transcurrido_ms(self) -> int:
        return int((time.perf_counter() - self._inicio) * 1000)
