"""
Qué PQRS están por vencer el plazo legal, agrupadas por a quién avisarle.

Existe para que una automatización pueda mandar el recordatorio diario sin
tener que cruzar datos: devuelve el correo del destinatario y la lista de
SUS casos. Un correo que dice "tienes 3 PQRS por vencer" se lee; uno que
lista las 40 de toda la empresa se archiva sin abrir.

El plazo sale de la Ley 1755 de 2015 y se cuenta en días hábiles, así que
vencerse no es un descuido interno: es un incumplimiento legal. Por eso
este es el recordatorio que más importa de los tres.
"""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.dias_habiles import contar_habiles
from app.models.pqrs import PQRSSolicitud
from app.models.user import User

# Estados en los que una PQRS todavía corre contra el reloj. Los válidos son
# recibido | asignado | en_proceso | resuelto | cerrado (ver router.py); una
# resuelta o cerrada ya no vence.
ESTADOS_ABIERTOS = ("recibido", "asignado", "en_proceso")


def _aware(f):
    if f is None:
        return None
    return f if f.tzinfo else f.replace(tzinfo=timezone.utc)


def dias_habiles_restantes(solicitud, ahora: datetime) -> int | None:
    """
    Cuántos días hábiles faltan para el vencimiento. Negativo = ya venció.

    Se cuenta en hábiles y no en corridos porque así está definido el plazo;
    contarlos corridos declararía vencido lo que todavía está en término.
    """
    limite = _aware(solicitud.fecha_limite_sla)
    if not limite:
        return None

    if limite.date() >= ahora.date():
        return contar_habiles(ahora.date(), limite.date())
    return -contar_habiles(limite.date(), ahora.date())


def por_vencer(db: Session, tenant_id: int, dias_aviso: int = 2) -> dict:
    """
    Las PQRS abiertas que vencen dentro de `dias_aviso` días hábiles o que
    ya vencieron, agrupadas por responsable.

    Las que no tienen a nadie asignado van aparte: son las más peligrosas,
    porque el reloj corre y no hay quién responda.
    """
    ahora = datetime.now(timezone.utc)

    solicitudes = db.query(PQRSSolicitud).filter(
        PQRSSolicitud.tenant_id == tenant_id,
        PQRSSolicitud.estado.in_(ESTADOS_ABIERTOS),
        PQRSSolicitud.fecha_limite_sla.isnot(None),
    ).all()

    por_persona: dict[int, dict] = {}
    sin_responsable: list[dict] = []

    for s in solicitudes:
        dias = dias_habiles_restantes(s, ahora)
        if dias is None or dias > dias_aviso:
            continue

        ficha = {
            "pqrs_id": s.id,
            "codigo": s.codigo_seguimiento or s.radicado_calidad,
            "tipo": s.tipo,
            "cliente": s.cliente_nombre,
            "area_responsable": s.area_responsable,
            "dias_restantes": dias,
            "vencida": dias < 0,
            "fecha_limite": s.fecha_limite_sla.isoformat() if s.fecha_limite_sla else None,
        }

        if not s.asignado_a:
            sin_responsable.append(ficha)
            continue

        grupo = por_persona.setdefault(s.asignado_a, {"casos": []})
        grupo["casos"].append(ficha)

    # Se resuelven los correos aquí y no en la automatización: el portal ya
    # tiene los usuarios, y hacer que n8n se autentique para consultarlos
    # sería pedirle que resuelva algo que aquí está a la mano.
    destinatarios = []
    for usuario_id, grupo in por_persona.items():
        usuario = db.get(User, usuario_id)
        if not usuario or not usuario.email or not usuario.activo:
            # Su responsable ya no está activo: el caso queda huérfano y
            # tiene que verlo Servicio al Cliente, no perderse.
            sin_responsable.extend(grupo["casos"])
            continue

        casos = sorted(grupo["casos"], key=lambda c: c["dias_restantes"])
        destinatarios.append({
            "email": usuario.email,
            "nombre": usuario.nombre,
            "total": len(casos),
            "vencidas": sum(1 for c in casos if c["vencida"]),
            "casos": casos,
        })

    destinatarios.sort(key=lambda d: (-d["vencidas"], -d["total"]))
    sin_responsable.sort(key=lambda c: c["dias_restantes"])

    return {
        "generado_en": ahora.isoformat(),
        "dias_aviso": dias_aviso,
        "total": sum(d["total"] for d in destinatarios) + len(sin_responsable),
        "destinatarios": destinatarios,
        "sin_responsable": sin_responsable,
    }
