FROM python:3.11-slim

WORKDIR /app

# No hacen falta gcc ni libpq-dev: requirements.txt usa psycopg2-binary,
# que ya viene compilado y trae la libpq embebida. Instalarlos solo hacía
# la imagen más pesada y el build mucho más lento (y se quedaba sin
# memoria en equipos con poca RAM libre).

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x entrypoint.sh

EXPOSE 8000

CMD ["./entrypoint.sh"]
