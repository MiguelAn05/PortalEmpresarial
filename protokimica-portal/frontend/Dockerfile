# Build en 2 etapas: primero compila el frontend con Node, luego lo sirve
# con Nginx. La imagen final NO tiene Node ni node_modules, solo los
# archivos estáticos ya compilados — más liviana y más segura.

FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --include=dev
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
