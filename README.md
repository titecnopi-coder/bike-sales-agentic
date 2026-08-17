# City Bike — Sistema Agéntico de Analítica de Ventas

Sistema agéntico completo (LLM + RAG + Tools) desarrollado como prueba técnica para el rol de Ingeniera de Sistemas — Data, AI & Automation en la Universidad EAN.

Asistente conversacional de analítica de ventas para **City Bike** (tienda real de bicicletas, Bogotá — bicicletas, taller y accesorios), que integra un modelo de lenguaje (Gemini 2.5 Flash), una canalización RAG sobre documentación real del dominio, herramientas de negocio con datos reales en PostgreSQL, un paso de reranking, y un agente evaluador (Juez) que valida cada respuesta antes de entregarla.

## 🔗 Enlaces en vivo

- **Frontend (chat + dashboard):** https://bike-sales-frontend-575202457786.us-central1.run.app
- **API (documentación interactiva):** https://bike-sales-api-575202457786.us-central1.run.app/docs

## 📄 Documentación

- [Documento de Arquitectura](docs/arquitectura.md) — componentes, agentes, flujo de datos, selección de LLM, chunking, schemas, despliegue, costos y decisiones de diseño
- [Documento de Administrador](docs/administrador.md) — despliegue, permisos IAM, gestión de secretos, rollback
- [Guía de Usuario](docs/guia_usuario.md) — cómo usar el sistema, con capturas de pantalla reales
- [Video demostrativo](#) *(pendiente de enlace)*

## 🏗️ Los 5 patrones agénticos implementados

1. **Orchestrator & Sub-Workers** — `orchestrator/main.py`
2. **MCP / Tools** (3 herramientas, una con datos reales en PostgreSQL) — `tools/`
3. **RAG** (ingesta, chunking, embeddings, pgvector en Cloud SQL) — `rag/`
4. **Reranking** (LLM-based) — `rag/reranking.py`
5. **Agente Juez** (score 0-10 + loop de refinamiento) — `judge/`

## 🧱 Estructura del repositorio

```
├── orchestrator/     # Orquestador principal (tool calling, coordinación)
├── tools/            # Las 3 herramientas de negocio
├── rag/               # Ingesta, búsqueda semántica, reranking, migraciones a Cloud SQL
├── judge/             # Agente evaluador
├── api/               # API REST con FastAPI
├── frontend/          # Interfaz de chat + dashboard en React
├── observability/     # Logging estructurado y cálculo de los 8 KPIs
├── tests/             # Tests unitarios (pytest)
├── docs/               # Los 3 documentos técnicos + capturas de pantalla
├── .github/workflows/ # CI/CD (GitHub Actions)
├── Dockerfile          # Imagen de la API
└── frontend/Dockerfile # Imagen del frontend
```

## 🛠️ Stack tecnológico

- **Lenguaje backend:** Python 3.12+
- **Backend:** FastAPI
- **Frontend:** React + Vite *(ver justificación de esta decisión en el Documento de Arquitectura, Sección 9 — el enunciado sugiere Streamlit/Gradio en Python)*
- **LLM:** Gemini 2.5 Flash vía Vertex AI
- **Embeddings:** `text-embedding-004`
- **Base de datos vectorial:** Cloud SQL (PostgreSQL 15) + extensión `pgvector`
- **Base de datos de negocio:** Cloud SQL (PostgreSQL 15)
- **Despliegue:** Cloud Run (contenedores Docker independientes para API y frontend)
- **Gestión de secretos:** Secret Manager
- **CI/CD:** GitHub Actions (lint con `ruff`, tests con `pytest`, deploy automático vía Workload Identity Federation)

## 🚀 Cómo correr el proyecto localmente

Ver instrucciones completas en el [Documento de Administrador](docs/administrador.md), Sección 2.

Resumen rápido:
```bash
pip install -r requirements.txt
set DB_PASSWORD=<tu contraseña>
set GCP_PROJECT_ID=<tu project id>
uvicorn api.main:app --reload
```

```bash
cd frontend
npm install
npm run dev
```

## 📊 Observabilidad

Dashboard propio con los 8 KPIs exigidos, accesible desde el botón "Ver dashboard" en el frontend, con auto-actualización cada 60 segundos. Cada consulta genera un log estructurado (JSON) guardado en la tabla `logs` de Cloud SQL, con: `request_id`, `timestamp`, modelo, tokens de entrada/salida, latencia, tool usada, score del Juez, y costo estimado.

## 🧪 Tests y CI/CD

```bash
pytest tests/ -v
```

Cada `git push` a `main` dispara automáticamente: lint (`ruff`) → tests (`pytest`) → despliegue a Cloud Run. Ver `.github/workflows/ci-cd.yml`.

## 👤 Autora

Angie Stefany Vera Medina — Ingeniera de Sistemas, especialización en Data, AI & Automation.
