"""
API — FastAPI
================
Expone el Orquestador (con RAG+Reranking+Juez ya integrados) como
un servicio web. El frontend (React) le va a hacer peticiones HTTP
a esta API, en vez de importar directamente el código Python
(el frontend en React no puede ejecutar Python).

Cómo correr esto localmente (para probar antes de desplegar):
    uvicorn api.main:app --reload
Luego abre en el navegador: http://localhost:8000/docs
Esa página /docs la genera FastAPI automáticamente -- es una
interfaz donde puedes probar la API sin necesitar el frontend
todavía.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from orchestrator.main import procesar_pregunta
from observability.kpis import calcular_kpis

app = FastAPI(
    title="Bike Sales Agentic API",
    description="API del sistema agéntico de analítica de ventas de bicicletas",
    version="1.0.0",
)

# CORS: por defecto, un navegador bloquea que una página en un dominio
# (tu frontend React, ej. localhost:3000) le hable a una API en otro
# dominio (esta API, ej. localhost:8000) -- es una protección de
# seguridad del navegador. Este middleware le dice explícitamente
# "está bien, permite que el frontend le hable a esta API".
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # en producción real esto se restringe al dominio exacto del frontend
    allow_methods=["*"],
    allow_headers=["*"],
)


class PreguntaRequest(BaseModel):
    """
    Define la 'forma' que debe tener cada petición que llegue a /preguntar.
    FastAPI usa esto para validar automáticamente -- si alguien manda
    una petición sin el campo 'pregunta', FastAPI rechaza la petición
    sola, antes de que nuestro código siquiera se ejecute.
    """
    pregunta: str


class PreguntaResponse(BaseModel):
    respuesta: str
    score_juez: float
    aprobado: bool
    intentos_refinamiento: int
    tool_usada: str | None = None


@app.get("/")
def raiz():
    """Endpoint simple para confirmar que la API está viva."""
    return {"mensaje": "Bike Sales Agentic API funcionando. Ve a /docs para probarla."}


@app.get("/metricas")
def metricas():
    """
    Calcula y devuelve los 8 KPIs del dashboard de observabilidad,
    a partir de todos los registros históricos en la tabla 'logs'.
    """
    try:
        return calcular_kpis()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculando métricas: {e}")


@app.post("/preguntar", response_model=PreguntaResponse)
def preguntar(request: PreguntaRequest):
    """
    Endpoint principal: recibe una pregunta, la procesa con el
    Orquestador completo (Tools + RAG + Reranking + Juez), y
    devuelve la respuesta final.
    """
    if not request.pregunta.strip():
        raise HTTPException(status_code=400, detail="La pregunta no puede estar vacía")

    try:
        resultado = procesar_pregunta(request.pregunta)
        return resultado
    except Exception as e:
        # Nunca dejamos que un error interno tumbe la API sin explicación
        # -- esto también alimenta el KPI de tasa de éxito del sistema.
        raise HTTPException(status_code=500, detail=f"Error procesando la pregunta: {e}")
