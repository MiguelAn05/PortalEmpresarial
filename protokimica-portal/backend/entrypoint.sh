#!/bin/sh
# Se ejecuta cada vez que arranca el contenedor del backend, en CUALQUIER
# equipo. Aplica automáticamente las migraciones de Alembic que falten
# antes de levantar la API — así nadie tiene que acordarse de correr
# "alembic upgrade head" a mano después de un git pull o al clonar el
# repo en un equipo nuevo.
set -e

echo "→ Aplicando migraciones de Alembic..."
alembic upgrade head

echo "→ Iniciando la API..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
