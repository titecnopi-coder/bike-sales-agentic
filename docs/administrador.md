# Documento de Administrador
## Sistema Agéntico City Bike

---

## 1. Prerrequisitos

- Cuenta de Google Cloud con facturación activa (se requiere para Vertex AI, aunque exista prueba gratuita).
- `gcloud CLI` instalado y autenticado (`gcloud auth login` + `gcloud auth application-default login`).
- Node.js 18+ (para construir el frontend).
- Python 3.12+.
- Git.

### 1.1 Permisos IAM necesarios

La cuenta de servicio de Cloud Run (`{PROJECT_NUMBER}-compute@developer.gserviceaccount.com`) requiere los siguientes roles, otorgados una sola vez:

```
gcloud projects add-iam-policy-binding PROJECT_ID --member="serviceAccount:PROJECT_NUMBER-compute@developer.gserviceaccount.com" --role="roles/cloudsql.client"
gcloud projects add-iam-policy-binding PROJECT_ID --member="serviceAccount:PROJECT_NUMBER-compute@developer.gserviceaccount.com" --role="roles/secretmanager.secretAccessor"
gcloud projects add-iam-policy-binding PROJECT_ID --member="serviceAccount:PROJECT_NUMBER-compute@developer.gserviceaccount.com" --role="roles/aiplatform.user"
gcloud projects add-iam-policy-binding PROJECT_ID --member="serviceAccount:PROJECT_NUMBER-compute@developer.gserviceaccount.com" --role="roles/storage.objectViewer"
gcloud projects add-iam-policy-binding PROJECT_ID --member="serviceAccount:PROJECT_NUMBER-compute@developer.gserviceaccount.com" --role="roles/artifactregistry.writer"
gcloud projects add-iam-policy-binding PROJECT_ID --member="serviceAccount:PROJECT_NUMBER-compute@developer.gserviceaccount.com" --role="roles/logging.logWriter"
```

Obtener `PROJECT_NUMBER`:
```
gcloud projects describe PROJECT_ID --format="value(projectNumber)"
```

### 1.2 APIs de GCP a habilitar

```
gcloud services enable aiplatform.googleapis.com
gcloud services enable sqladmin.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable secretmanager.googleapis.com
gcloud services enable compute.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable artifactregistry.googleapis.com
```

### 1.3 Cuotas de Vertex AI

El proyecto usa `gemini-2.5-flash` y `text-embedding-004`. Las cuotas por defecto de un proyecto nuevo son suficientes para el volumen de este proyecto (cientos de consultas/día); para producción a mayor escala, revisar cuotas en Vertex AI → Cuotas.

---

## 2. Instrucciones de despliegue

### 2.1 Despliegue local (desarrollo)

```
git clone https://github.com/titecnopi-coder/bike-sales-agentic.git
cd bike-sales-agentic
pip install -r requirements.txt

set DB_PASSWORD=<contraseña real>
set GCP_PROJECT_ID=<tu project id>

uvicorn api.main:app --reload
```

Frontend, en otra terminal:
```
cd frontend
npm install
npm run dev
```

### 2.2 Creación de la infraestructura en GCP (una sola vez)

```
gcloud sql instances create bike-sales-db --database-version=POSTGRES_15 --tier=db-custom-1-3840 --region=us-central1 --root-password=<contraseña>
gcloud sql databases create bike_sales --instance=bike-sales-db
echo <contraseña> | gcloud secrets create db-password --data-file=-
```

Luego, con `DB_PASSWORD` configurada localmente:
```
python -m observability.crear_tabla_logs
python -m rag.ingesta
python -m rag.migrar_a_cloud_sql
python -m rag.migrar_ventas_a_cloud_sql
```

### 2.3 Despliegue en Cloud Run

**API:**
```
gcloud run deploy bike-sales-api --source . --region us-central1 --allow-unauthenticated --set-secrets=DB_PASSWORD=db-password:latest --set-env-vars=GCP_PROJECT_ID=<tu project id> --memory 1Gi --timeout 300
```

**Frontend** (requiere `frontend/.env.production` con la URL real de la API ya desplegada, o el valor por defecto configurado en `App.jsx`/`Dashboard.jsx`):
```
cd frontend
gcloud run deploy bike-sales-frontend --source . --region us-central1 --allow-unauthenticated --memory 512Mi
```

---

## 3. Gestión de variables de entorno y secretos

| Variable | Dónde se usa | Cómo se gestiona |
|---|---|---|
| `DB_PASSWORD` | Conexión a Cloud SQL (RAG, ventas, logs, KPIs) | Secret Manager (`db-password`), inyectada en Cloud Run vía `--set-secrets` |
| `GCP_PROJECT_ID` | Cliente de Vertex AI y conexión a Cloud SQL | Variable de entorno en Cloud Run (`--set-env-vars`), no es secreta |
| `VITE_API_URL` | Frontend, para saber a qué API llamar | Definida en `frontend/.env.production` (leída en build time por Vite) o como valor por defecto en el código |

**Regla de seguridad aplicada:** ninguna contraseña se escribe en el código fuente ni se sube a GitHub (`.gitignore` excluye `.env` y archivos con extensión `.key.json`).

---

## 4. Procedimiento de ingesta de nuevos documentos al corpus RAG

1. Agregar el nuevo documento (`.pdf` o `.md`) a la carpeta `rag/corpus/`.
2. Correr, con `DB_PASSWORD` configurada:
   ```
   python -m rag.ingesta
   python -m rag.migrar_a_cloud_sql
   ```
3. `rag/ingesta.py` procesa **todos** los documentos de la carpeta (no solo el nuevo), generando `rag/vector_store_local.json`.
4. `rag/migrar_a_cloud_sql.py` usa `ON CONFLICT (id) DO UPDATE`, por lo que correrlo de nuevo no duplica chunks ya existentes con el mismo `id`.

---

## 5. Configuración de alertas en Cloud Monitoring

*(Configuración recomendada, no implementada en el dashboard propio actual — el dashboard propio del frontend cubre el requisito de "dashboard accesible desde la UI"; esta sección documenta cómo extenderlo con Cloud Monitoring nativo)*

Alertas recomendadas para los KPIs críticos:

| KPI | Condición de alerta sugerida |
|---|---|
| Tasa de éxito de Tools | < 90% en ventana de 1 hora |
| Score del Juez promedio | < 7.5 en ventana de 1 hora |
| Time to Last Token (p95) | > 10s sostenido por 15 min |
| Costo por consulta | > $0.05 promedio en ventana de 1 día |

Configuración vía Cloud Monitoring → Alerting policies, apuntando a métricas personalizadas exportadas desde la tabla `logs` (extensión futura: exportar estos datos también a Cloud Logging con `structured logging` nativo, no solo a Cloud SQL).

---

## 6. Procedimiento de rollback ante un despliegue fallido

Cloud Run mantiene todas las revisiones anteriores por defecto. Ante un despliegue fallido o con errores:

```
gcloud run revisions list --service=bike-sales-api --region=us-central1
gcloud run services update-traffic bike-sales-api --region=us-central1 --to-revisions=<REVISION_ANTERIOR>=100
```

Esto redirige el 100% del tráfico a la revisión estable anterior sin necesidad de reconstruir la imagen.

---

## 7. Estimación de costo de infraestructura y recomendaciones para reducirlo

Ver Documento de Arquitectura, Sección 8, para el desglose completo (~$60-90 USD/mes).

**Recomendaciones concretas:**
- **Cloud SQL es el mayor costo fijo** (~$50-60/mes, corre 24/7). Si el sistema no necesita disponibilidad continua, pausar la instancia fuera de horario:
  ```
  gcloud sql instances patch bike-sales-db --activation-policy=NEVER
  ```
  Y reactivar:
  ```
  gcloud sql instances patch bike-sales-db --activation-policy=ALWAYS
  ```
- Cloud Run ya escala a cero automáticamente en inactividad — no requiere intervención manual para ahorrar costo.
- Monitorear el KPI de costo por consulta (#4 del dashboard) para detectar consultas anómalamente caras (ej. bucles de refinamiento repetidos).
