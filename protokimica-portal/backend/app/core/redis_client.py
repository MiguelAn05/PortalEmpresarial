"""
Cliente Redis compartido. Hoy solo se usa para el freno de intentos de
login, pero queda listo para cache/colas que se necesiten más adelante.
"""
import redis

from app.core.config import settings

redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
