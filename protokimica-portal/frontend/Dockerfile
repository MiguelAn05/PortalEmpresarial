# Build en 2 etapas: primero compila el frontend con Node, luego lo sirve
# con Nginx. La imagen final NO tiene Node ni node_modules, solo los
# archivos estáticos ya compilados — más liviana y más segura.

FROM node:20-bookworm-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./

# Esta red tiene cortes intermitentes. Alpine (musl) maneja peor esos
# cortes que Debian y dispara un bug conocido de npm ("Exit handler
# never called!"); por eso esta etapa usa node:20-bookworm-slim en vez
# de node:20-alpine. Igual se deja tolerancia a fallos de red por si acaso.
RUN npm config set fetch-retries 5 \
    && npm config set fetch-retry-mintimeout 20000 \
    && npm config set fetch-retry-maxtimeout 120000 \
    && npm config set fetch-timeout 300000 \
    && for i in 1 2 3; do \
         echo "Intento $i de instalar dependencias..."; \
         rm -rf node_modules; \
         npm ci --include=dev && test -f node_modules/.bin/vite && break; \
         echo "Intento $i falló o quedó incompleto, reintentando en 10s..."; \
         sleep 10; \
       done \
    && test -f node_modules/.bin/vite || (echo "ERROR: no se pudo instalar vite después de 3 intentos" && exit 1)

COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
