# Build en 2 etapas: primero compila el frontend con Node, luego lo sirve
# con Nginx. La imagen final NO tiene Node ni node_modules, solo los
# archivos estáticos ya compilados — más liviana y más segura.

FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --include=dev
RUN echo "=== DIAGNOSTICO ===" \
    && node --version \
    && npm --version \
    && echo "--- npm ls vite ---" \
    && npm ls vite || true \
    && echo "--- contenido de node_modules/.bin (primeras 30 lineas) ---" \
    && ls node_modules/.bin | head -30 \
    && echo "--- existe carpeta node_modules/vite? ---" \
    && ls node_modules/vite 2>&1 || true \
    && echo "=== FIN DIAGNOSTICO ==="
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
