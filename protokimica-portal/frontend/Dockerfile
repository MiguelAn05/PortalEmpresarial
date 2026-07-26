# Build en 2 etapas: primero compila el frontend con Node, luego lo sirve
# con Nginx. La imagen final NO tiene Node ni node_modules, solo los
# archivos estáticos ya compilados — más liviana y más segura.

FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./

# Esta red tiene cortes intermitentes que a veces hacen que npm se caiga
# a la mitad de la descarga (bug conocido de npm: "Exit handler never
# called!"). Se sube la tolerancia a fallos de red y se reintenta hasta
# 5 veces, limpiando node_modules entre intentos, hasta que quede una
# instalación completa de verdad (se valida al final que vite exista).
RUN npm config set fetch-retries 5 \
    && npm config set fetch-retry-mintimeout 20000 \
    && npm config set fetch-retry-maxtimeout 120000 \
    && npm config set fetch-timeout 300000 \
    && for i in 1 2 3 4 5; do \
         echo "Intento $i de instalar dependencias..."; \
         rm -rf node_modules; \
         npm ci --include=dev && test -f node_modules/.bin/vite && break; \
         echo "Intento $i falló o quedó incompleto, reintentando en 10s..."; \
         sleep 10; \
       done \
    && test -f node_modules/.bin/vite || (echo "ERROR: no se pudo instalar vite después de 5 intentos" && exit 1)

COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
