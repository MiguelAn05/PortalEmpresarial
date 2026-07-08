"""
Lógica de negocio de PQRS.
"""
from datetime import datetime, timedelta, timezone
import random
import string

import httpx

from app.core.config import settings

SLA_DIAS_POR_TIPO = {
    "peticion":   15,
    "queja":       5,
    "reclamo":     8,
    "sugerencia": 10,
}

PRIORIDAD_POR_TIPO = {
    "peticion":   "media",
    "queja":      "alta",
    "reclamo":    "alta",
    "sugerencia": "baja",
}


def calcular_fecha_limite_sla(tipo: str) -> datetime:
    dias = SLA_DIAS_POR_TIPO.get(tipo, 10)
    return datetime.now(timezone.utc) + timedelta(days=dias)


def calcular_prioridad(tipo: str) -> str:
    return PRIORIDAD_POR_TIPO.get(tipo, "media")


def generar_codigo_seguimiento() -> str:
    """
    Genera un código único para que el cliente consulte su PQRS.
    Formato: PK-2026-XXXX donde XXXX son 4 dígitos aleatorios.
    Ejemplo: PK-2026-4821
    """
    año = datetime.now().year
    numero = ''.join(random.choices(string.digits, k=4))
    return f"PK-{año}-{numero}"


def disparar_webhook_n8n(evento: str, payload: dict) -> None:
    """
    Notifica a n8n para automatizaciones: email, Teams, escalamiento, etc.
    Si n8n no está configurado, se ignora silenciosamente.
    """
    url = getattr(settings, "N8N_WEBHOOK_URL", None)
    if not url:
        return

    try:
        httpx.post(f"{url}/{evento}", json=payload, timeout=3.0)
    except httpx.HTTPError:
        pass