# Imagen base: Python 3.12, versión "slim" (más liviana, menos peso extra)
FROM python:3.12-slim

# Carpeta de trabajo dentro del contenedor
WORKDIR /app

# Copiamos primero solo requirements.txt (no todo el código) para que
# Docker pueda reusar esta capa si el código cambia pero las
# dependencias no -- acelera builds futuros.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Ahora sí copiamos el resto del código de la aplicación
COPY orchestrator/ orchestrator/
COPY tools/ tools/
COPY rag/ rag/
COPY judge/ judge/
COPY observability/ observability/
COPY api/ api/

# Cloud Run inyecta la variable de entorno PORT en tiempo real
# (normalmente 8080) -- por eso usamos ${PORT:-8080} en vez de un
# número fijo, así el mismo Dockerfile funciona igual local y en la nube.
ENV PORT=8080
EXPOSE 8080

CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8080}"]