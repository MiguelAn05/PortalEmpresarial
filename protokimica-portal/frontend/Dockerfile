# El frontend se compila en la máquina de desarrollo (npm run build),
# NO en el servidor. La red de este servidor tiene cortes intermitentes
# que hacen que npm falle de forma consistente durante la instalación
# de dependencias (bug conocido de npm con conexiones largas/inestables).
# Este Dockerfile solo empaqueta el resultado ya compilado (frontend/dist)
# dentro de Nginx — no descarga nada de npm.
#
# Antes de cada "docker compose ... --build" en el servidor, hay que
# haber corrido "npm run build" en local y commiteado la carpeta dist/.

FROM nginx:1.27-alpine
COPY dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
