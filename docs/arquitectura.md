# Documento de Arquitectura
## Sistema Agéntico City Bike — Asistente de Analítica de Ventas de Bicicletas

**Candidata:** Angie Stefany Vera Medina
**Rol:** Ingeniera de Sistemas — Data, AI & Automation
**Nube asignada:** Google Cloud Platform (GCP)
**Fecha:** Agosto 2026

---

## 1. Descripción general del sistema

City Bike es un asistente conversacional de analítica de ventas para una tienda real de bicicletas (City Bike, Bogotá — bicicletas, taller y accesorios). El sistema combina un modelo de lenguaje grande (Gemini 2.5 Flash), una canalización RAG sobre documentación real del dominio, herramientas de negocio con datos reales en PostgreSQL, un paso de reranking, y un agente evaluador (Juez) que valida cada respuesta antes de entregarla al usuario.

El dominio se construyó extendiendo dos proyectos reales previos de la candidata (`Bike Sales Analytics Platform` y `AI Bike Sales Assistant`), cuya documentación forma parte del corpus RAG, cumpliendo con el dominio sugerido en el enunciado.

### 1.1 Componentes principales

| Componente | Tecnología | Función |
|---|---|---|
| Orquestador | Python + `google-genai` (Vertex AI) | Recibe la pregunta, decide qué herramienta usar, coordina el flujo |
| Tools | Python puro + SQL | 3 herramientas: calculadora de métricas, consulta de ventas (PostgreSQL real), generador de reportes |
| RAG | pgvector sobre Cloud SQL | Ingesta, chunking, embeddings y búsqueda semántica sobre 4 documentos reales |
| Reranking | Gemini 2.5 Flash (LLM-based) | Reordena candidatos RAG por relevancia real antes de responder |
| Agente Juez | Gemini 2.5 Flash | Evalúa cada respuesta (relevancia, alucinaciones, completitud, claridad) y activa un loop de refinamiento si no aprueba |
| API | FastAPI (Python) | Expone el Orquestador como servicio HTTP |
| Frontend | React + Vite | Interfaz de chat con identidad de marca real (City Bike), muestra visualmente qué patrones se activaron por respuesta |
| Base de datos vectorial | Cloud SQL (PostgreSQL 15) + extensión `pgvector` | Almacena los 173 chunks del corpus con sus embeddings |
| Base de datos de negocio | Cloud SQL (PostgreSQL 15) | Tabla `ventas`, consultada en tiempo real por la tool de ventas |
| Observabilidad | Tabla `logs` en Cloud SQL + endpoint `/metricas` | Logging estructurado por consulta; cálculo de los 8 KPIs exigidos |
| Despliegue | Cloud Run (API y Frontend, contenedores Docker separados) | Ambos servicios corren en contenedores independientes en la nube |
| Gestión de secretos | Secret Manager | La contraseña de la base de datos nunca se escribe en código ni en variables de entorno planas |

---

## 2. Descripción de los agentes

### 2.1 Orquestador

**Responsabilidad:** recibir la pregunta del usuario, decidir mediante *tool calling* nativo de Gemini cuál de las 3 tools (o ninguna) necesita, ejecutar la tool localmente, devolver el resultado a Gemini para que arme la respuesta final, y coordinar el ciclo de evaluación/refinamiento con el Juez.

**Entrada:** pregunta en lenguaje natural (string).
**Salida:** `{respuesta, score_juez, aprobado, intentos_refinamiento, tool_usada}`.

El Orquestador no decide con reglas fijas (`if/else`) qué herramienta usar — esa decisión la toma el propio modelo Gemini, en base a la descripción semántica de cada tool (su `TOOL_SCHEMA`). Esto se verificó empíricamente: ante la misma arquitectura de prompt, Gemini seleccionó correctamente `consultar_ventas` para preguntas de cifras, `calcular_metrica_negocio` para cálculos aritméticos, y `buscar_en_documentos` para preguntas sobre mantenimiento y uso de bicicletas, sin ambigüedad observada en las pruebas realizadas.

### 2.2 Sub-Workers (Tools)

No se implementaron como agentes separados con su propio LLM (decisión de diseño, ver Sección 9), sino como funciones Python puras invocadas por el Orquestador vía tool calling. Cada una:

1. **`calcular_metrica_negocio`** — cálculo puro (margen bruto, crecimiento porcentual, ticket promedio). No consulta ninguna fuente externa; existe para que el LLM delegue aritmética exacta en vez de "inventar" números en el texto generado (mitigación de alucinaciones numéricas).

2. **`consultar_ventas`** — consulta SQL real contra la tabla `ventas` en Cloud SQL (PostgreSQL). Es la tool que cumple el requisito de "al menos una herramienta con datos reales" del enunciado. Migrada desde un CSV local a PostgreSQL real durante el desarrollo (ver Sección 9, decisión documentada).

3. **`generar_reporte_ventas`** — compone las dos tools anteriores (consulta ventas + calcula margen) en un reporte de texto formateado. Ejemplifica composición de tools, un patrón común en sistemas agénticos de producción.

### 2.3 Agente Juez (Judge LLM)

**Responsabilidad:** evaluar, de forma independiente, la respuesta que el Orquestador está a punto de enviar al usuario — nunca genera contenido nuevo, solo audita lo ya generado.

**Entrada:** `{pregunta, contexto_usado, respuesta_generada}`.
**Salida:** `{score_final (0-10), aprobado (bool), detalle: {relevancia, sin_alucinaciones, completitud, claridad, comentario}}`.

**Umbral de aprobación:** 7.5/10 (mismo número usado como KPI #2 del dashboard — es intencional: el mismo criterio de calidad se mide como *gate* antes de responder y como métrica agregada en el tiempo).

**Loop de refinamiento:** si `aprobado = false`, el comentario del Juez se inyecta de vuelta al Orquestador como retroalimentación explícita ("tu respuesta anterior fue rechazada por: X, corrígela"), y se genera un segundo intento. Límite de 1 reintento por consulta, para acotar costo y latencia.

Evidencia real de funcionamiento (capturada durante desarrollo): ante una respuesta con datos inventados (frecuencia de mantenimiento no presente en el contexto), el Juez asignó un score de 2.0/10 con el sub-criterio `sin_alucinaciones = 0`, y rechazó la respuesta correctamente.

---

## 3. Flujo de datos completo

```
Usuario (React) 
    │  HTTP POST /preguntar {"pregunta": "..."}
    ▼
API FastAPI (Cloud Run)
    │
    ▼
Orquestador
    │  1. Envía pregunta + 3 tool schemas a Gemini 2.5 Flash
    │  2. Gemini decide: ¿necesita una tool? ¿cuál?
    │
    ├──[si decide "buscar_en_documentos"]──▶ RAG + Reranking
    │       │ a. Embedding de la pregunta (text-embedding-004)
    │       │ b. Búsqueda pgvector (similitud coseno) → top 10 candidatos
    │       │ c. Reranking LLM-based → nota de relevancia real 0-10 por candidato
    │       │ d. Top 3 reordenados devueltos al Orquestador
    │       ▼
    ├──[si decide "consultar_ventas" o "calcular_metrica_negocio"
    │   o "generar_reporte_ventas"]──▶ ejecución directa de la tool (SQL o cómputo puro)
    │
    ▼
    3. Resultado de la tool se devuelve a Gemini como function_response
    4. Gemini arma la respuesta final en lenguaje natural
    ▼
Agente Juez
    │  Evalúa {pregunta, contexto, respuesta} → score 0-10
    │
    ├──[score < 7.5]──▶ Loop de refinamiento (máx. 1 vez) ──▶ vuelve a "Orquestador"
    │
    ▼ [score >= 7.5, o refinamiento agotado]
Logging estructurado
    │  INSERT en tabla 'logs': tokens, latencia, costo, tool usada, score, etc.
    ▼
## 4. Selección y justificación del modelo LLM

### 4.1 Tabla comparativa

| Criterio | Gemini 2.5 Flash | Gemini 2.5 Pro |
|---|---|---|
| Capacidad de razonamiento | Alta para tareas estructuradas (tool calling, extracción, clasificación) | Superior en razonamiento multi-paso complejo |
| Ventana de contexto | 1M tokens | 2M tokens |
| Soporte de tool calling | Sí, nativo | Sí, nativo |
| Latencia observada (este proyecto) | ~2-12s por consulta (medido en producción, ver KPI #3) | Mayor (no medido en este proyecto, estimado 1.5-2x Flash) |
| Costo de referencia (por 1M tokens, input/output) | $0.075 / $0.30 (aprox., ago 2026) | Sensiblemente mayor |

### 4.2 Criterios de decisión aplicados al dominio

Para un asistente de analítica de ventas, las capacidades más críticas son: (1) tool calling confiable para delegar cálculos y consultas exactas, (2) latencia baja (el usuario espera una respuesta conversacional, no un reporte de investigación), y (3) costo predecible para escalar a mayor volumen. Gemini 2.5 Flash cubre las tres sin comprometer calidad observable en las pruebas de este proyecto — todas las respuestas evaluadas por el Juez obtuvieron scores entre 8.75 y 10/10 usando únicamente Flash.

### 4.3 Configuración de parámetros

- **Temperatura:** valor por defecto del SDK (no se sobreescribió). Para un asistente de negocio donde la precisión factual importa más que la creatividad, no se justificó bajar la temperatura por debajo del default, ya que el control principal de fidelidad se delega al Agente Juez, no a la temperatura del generador.
- **Tool calling:** habilitado en todas las llamadas del Orquestador vía `types.GenerateContentConfig(tools=[TOOLS])`.

### 4.4 Estrategia de gestión de costos

- Un solo modelo (Flash) se usa en todas las etapas (generación, reranking, evaluación) — se evaluó usar un modelo más pequeño para *routing* y Flash solo para la respuesta final, pero dado que Flash ya es el modelo económico de la familia, la complejidad adicional no se justificó para el volumen de este proyecto.
- Costo real observado y expuesto como KPI (#4 del dashboard): calculado por consulta a partir de tokens de entrada/salida reales devueltos por la API de Gemini (`usage_metadata`), no estimado.

### 4.5 Estrategia de fallback

No implementada en esta versión (limitación conocida, documentada en la Guía de Usuario). Extensión futura: capturar excepciones de cuota/timeout de Vertex AI y reintentar con backoff exponencial, o degradar a una respuesta basada solo en RAG sin generación si Gemini no está disponible.

### 4.6 Privacidad

El corpus RAG y los datos de ventas nunca salen del proyecto de GCP: Cloud SQL usa el conector oficial de Google (autenticación por IAM, sin exponer IP pública en texto plano en el código), y la contraseña de base de datos se gestiona vía Secret Manager, nunca en texto plano en el repositorio (ver `.gitignore`).

---

## 5. Estrategia de chunking

- **Tamaño de chunk:** 800 caracteres.
- **Overlap:** 100 caracteres.
- **Justificación:** 800 caracteres corresponde aproximadamente a un párrafo largo — suficiente para mantener una idea completa (ej. una sección de seguridad del manual de Trek) sin mezclar temas distintos. El overlap de 100 caracteres evita que una idea quede cortada exactamente en el límite entre dos chunks.
- **Evidencia real:** con estos parámetros, el manual de Trek (PDF de ~40 páginas) generó 130 chunks; el reporte de mercado generó 36; los 2 README generaron 4 y 3 respectivamente. Total: **173 chunks** indexados.
- **Embeddings:** `text-embedding-004` (Vertex AI), 768 dimensiones, multilenguaje — verificado empíricamente: preguntas en español recuperaron correctamente chunks en inglés (scores de similitud coseno entre 0.50 y 0.52 en las pruebas realizadas).

---

## 6. Schema JSON de cada Tool

### `calcular_metrica_negocio`
```json
{
  "name": "calcular_metrica_negocio",
  "description": "Calcula una métrica de negocio estándar (margen bruto, crecimiento porcentual o ticket promedio) a partir de cifras numéricas.",
  "input_schema": {
    "type": "object",
    "properties": {
      "metrica": {"type": "string", "enum": ["margen_bruto", "crecimiento_porcentual", "ticket_promedio"]},
      "valores": {"type": "object", "description": "Valores requeridos según la métrica"}
    },
    "required": ["metrica", "valores"]
  }
}
```

### `consultar_ventas`
```json
{
  "name": "consultar_ventas",
  "description": "Consulta datos reales de ventas de bicicletas (PostgreSQL en Cloud SQL): unidades vendidas e ingresos totales, con filtro opcional por categoría.",
  "input_schema": {
    "type": "object",
    "properties": {
      "categoria": {"type": "string", "enum": ["Montaña", "Urbana", "Ruta", "todas"]}
    },
    "required": ["categoria"]
  }
}
```

### `generar_reporte_ventas`
```json
{
  "name": "generar_reporte_ventas",
  "description": "Genera un reporte de negocio resumido combinando unidades vendidas, ingresos, y margen estimado.",
  "input_schema": {
    "type": "object",
    "properties": {
      "categoria": {"type": "string", "enum": ["Montaña", "Urbana", "Ruta", "todas"]},
      "costos_estimados_pct": {"type": "number", "description": "Porcentaje de costos sobre ingresos, default 65"}
    },
    "required": ["categoria"]
  }
}
```

### `buscar_en_documentos` (soporte del patrón RAG, expuesto también como tool)
```json
{
  "name": "buscar_en_documentos",
  "description": "Busca información en los documentos del corpus (manuales, reportes de mercado, documentación de proyectos).",
  "input_schema": {
    "type": "object",
    "properties": {
      "consulta": {"type": "string"}
    },
    "required": ["consulta"]
  }
}
```

---

## 7. Diagrama de despliegue en GCP

```
┌─────────────────────────────────────────────────────────────┐
│                     Google Cloud Platform                     │
│                  Proyecto: my-first-project-...                │
│                                                                 │
│  ┌──────────────────┐        ┌──────────────────┐            │
│  │   Cloud Run       │        │   Cloud Run       │            │
│  │  bike-sales-       │        │  bike-sales-       │            │
│  │  frontend          │        │  api                │            │
│  │  (React + nginx)   │───────▶│  (FastAPI)          │            │
│  └──────────────────┘        └────────┬─────────┘            │
│                                          │                       │
│                          ┌───────────────┼────────────────┐    │
│                          ▼               ▼                ▼    │
│                 ┌────────────────┐ ┌──────────┐ ┌──────────────┐│
│                 │  Vertex AI      │ │Cloud SQL │ │Secret Manager││
│                 │  (Gemini 2.5    │ │PostgreSQL│ │(contraseña   ││
│                 │   Flash +       │ │+pgvector │ │ de BD)       ││
│                 │   embeddings)   │ │tablas:   │ └──────────────┘│
│                 └────────────────┘ │chunks,   │                 │
│                                     │ventas,   │                 │
│                                     │logs      │                 │
│                                     └──────────┘                 │
│                                                                 │
│  Permisos IAM: Cloud Run service account con roles              │
│  cloudsql.client, secretmanager.secretAccessor, aiplatform.user │
└─────────────────────────────────────────────────────────────┘
```

**URLs reales de despliegue:**
- API: `https://bike-sales-api-575202457786.us-central1.run.app`
- Frontend: `https://bike-sales-frontend-575202457786.us-central1.run.app`

---

## 8. Estimación de costo mensual (escenario: 500 consultas/día)

| Componente | Costo estimado mensual (USD) |
|---|---|
| Vertex AI (Gemini + embeddings), ~500 consultas/día × 30 días, costo promedio por consulta observado ~$0.00004-0.001 según complejidad | $1 - $15 |
| Cloud SQL (`db-custom-1-3840`, 1 vCPU/3.75GB, encendida 24/7) | ~$50 - $60 |
| Cloud Run (API + Frontend, tráfico bajo-medio, con auto-scaling a 0 en inactividad) | $5 - $15 |
| Secret Manager | < $1 |
| **Total estimado** | **~$60 - $90 USD/mes** |

*Nota: el mayor costo fijo es Cloud SQL, porque a diferencia de Cloud Run (que escala a cero), una instancia de base de datos permanece encendida y facturando aunque no reciba tráfico. Recomendación documentada en el Documento de Administrador: evaluar Cloud SQL en modo de menor disponibilidad o pausar la instancia en periodos de inactividad prolongada.*

---

## 9. Decisiones de diseño relevantes y alternativas descartadas

| Decisión | Alternativa descartada | Justificación |
|---|---|---|
| Vector store: Cloud SQL + pgvector | Vertex AI Vector Search | Vertex AI Vector Search requiere aprovisionar un índice y endpoint (20-60 min), riesgo de tiempo alto frente al plazo de entrega. pgvector se levanta en minutos y es SQL estándar. |
| Frontend en React (JavaScript) | Streamlit/Gradio (Python), como sugiere el enunciado en Sección 2.2 | Indicación verbal directa del equipo entrevistador durante el proceso de selección, mencionando explícitamente React. Se documenta el riesgo: el criterio de evaluación "Calidad del código Python (API y frontend) — 15%" podría no reconocer código JavaScript como parte de ese criterio. Decisión informada, tomada conscientemente por la candidata. |
| Reranking LLM-based (Gemini) | Cross-encoder especializado (ej. `ms-marco-MiniLM`) | Un cross-encoder requiere descargar e instalar un modelo aparte; reusar Gemini (ya configurado) fue más simple para el tiempo disponible, y el enunciado acepta explícitamente ambas alternativas. |
| Datos de ventas: sintéticos, con forma realista | Datos reales de la empresa City Bike | La empresa es real (negocio familiar de la candidata), pero se optó por datos sintéticos para no comprometer información comercial real en un repositorio público de GitHub. El corpus RAG sí usa documentación real de la empresa y de proyectos previos de la candidata. |
| Migración de `consultar_ventas` de CSV local a PostgreSQL real | Dejar el CSV local | El enunciado exige explícitamente que al menos una tool consulte datos reales (BigQuery/PostgreSQL/API REST); un CSV local no cumple ese requisito de forma literal, aunque funcionara. |
| Sin agente de fallback ante error de Vertex AI | Implementar reintentos con backoff y modelo secundario | Fuera de alcance por tiempo; documentado como limitación conocida (ver Guía de Usuario). |

