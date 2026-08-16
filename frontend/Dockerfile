# Este Dockerfile tiene DOS etapas (multi-stage build):
# Etapa 1: usa Node.js para "compilar" React a archivos HTML/CSS/JS estáticos
# Etapa 2: usa un servidor web liviano (nginx) para servir esos archivos
# Ventaja: la imagen final es mucho más pequeña, no carga todo Node.js,
# solo el resultado final ya construido.

# --- Etapa 1: build ---
FROM node:20-slim AS build
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
# La URL de la API se "hornea" dentro de los archivos estáticos en este
# paso -- por eso se pasa como --build-arg al momento de construir.
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

# --- Etapa 2: servir con nginx ---
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
# Cloud Run espera que el contenedor escuche en el puerto de la
# variable PORT (normalmente 8080), pero nginx por defecto usa el 80.
# Este script pequeño ajusta la configuración al arrancar.
RUN sed -i 's/listen  *80;/listen 8080;/' /etc/nginx/conf.d/default.conf
EXPOSE 8080
CMD ["nginx", "-g", "daemon off;"]
