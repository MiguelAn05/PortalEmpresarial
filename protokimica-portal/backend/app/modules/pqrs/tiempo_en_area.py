"""
Cuánto tiempo tiene cada área una PQRS: máximo 3 días hábiles.

Es una regla de negocio de Protokimica, aparte del plazo legal: el plazo de
la Ley 1755 es de la PQRS completa (15 días hábiles una petición), y si un
área se demora una semana con el caso, las demás llegan sin tiempo. Por eso
cada área tiene su propio reloj:

- **Aplica a todas**, también a Servicio al Cliente.
- **Arranca de cero cada vez que el caso llega a un área**, aunque ya la
  hubiera tenido antes.
- **Pedir una autorización le pasa el reloj al área que firma**: el caso
  viaja a su bandeja (ver `autorizaciones/router.py`), y al responder vuelve
  a quien reparte con el reloj en cero.
- **Corre solo mientras la PQRS está abierta** (`ESTADOS_ABIERTOS`). Una
  resuelta ya respondió, igual que con el plazo legal; si el cliente la
  rechaza y se reabre, el área que la retoma empieza de cero.

El tramo que está corriendo vive en la PQRS (`area_responsable` +
`area_desde`); los que terminan quedan en `pqrs_pasos_area`, que es de
donde sale cualquier informe o indicador de qué área se demora.

**Todo lo que cambie el área o el estado de una PQRS llama a
`registrar_cambio()`**, después de cambiarlos. Así el reloj no depende de que
cada pantalla se acuerde de moverlo.
"""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core import capacidades
from app.core.dias_habiles import contar_habiles, limite_en_habiles
from app.core.fechas import con_zona
from app.models.pqrs import MAX_DIAS_HABILES_EN_AREA, PQRSPasoArea, PQRSSolicitud
from app.models.user import User
from app.modules.pqrs.pendientes import ESTADOS_ABIERTOS
from app.modules.pqrs.permisos import CAPACIDAD_GESTION


def _corre(area: str | None, estado: str | None) -> bool:
    return bool(area) and estado in ESTADOS_ABIERTOS


def registrar_cambio(db: Session, solicitud: PQRSSolicitud,
                     area_anterior: str | None, estado_anterior: str | None,
                     momento: datetime | None = None) -> None:
    """
    Mueve el reloj después de que la PQRS cambió de área o de estado.

    Si sigue en la misma área y abierta, no pasa nada: el tramo continúa.
    Si cambió de área, o dejó de estar abierta, el tramo que corría se
    guarda en `pqrs_pasos_area`; y si ahora corre, empieza uno nuevo en cero.
    Para una PQRS recién creada, `area_anterior` y `estado_anterior` van en
    None. No hace commit.
    """
    momento = momento or datetime.now(timezone.utc)
    corria = _corre(area_anterior, estado_anterior) and solicitud.area_desde is not None
    corre = _corre(solicitud.area_responsable, solicitud.estado)

    if corria and corre and area_anterior == solicitud.area_responsable:
        return

    if corria:
        desde = con_zona(solicitud.area_desde)
        db.add(PQRSPasoArea(
            tenant_id=solicitud.tenant_id, pqrs_id=solicitud.id, area=area_anterior,
            desde=desde, hasta=momento,
            dias_habiles=contar_habiles(desde.date(), momento.date()),
            excedio=momento > limite_en_habiles(desde, MAX_DIAS_HABILES_EN_AREA),
        ))

    solicitud.area_desde = momento if corre else None


def vencidas_en_area(db: Session, tenant_id: int, dias_aviso: int = 0) -> dict:
    """
    Las PQRS que su área ya tiene hace más de 3 días hábiles —o a las que
    les quedan `dias_aviso` días o menos—, agrupadas por área y con los
    correos de esa área.

    Lo consume el aviso diario de n8n, igual que `/pqrs/por-vencer`: el
    portal arma los grupos y resuelve los correos, n8n solo los manda. Un
    área sin nadie activo no se descarta: sus casos van a quien reparte
    (`pqrs.cerrar`), que es quien puede moverlos.
    """
    ahora = datetime.now(timezone.utc)
    hoy = ahora.date()

    solicitudes = db.query(PQRSSolicitud).filter(
        PQRSSolicitud.tenant_id == tenant_id,
        PQRSSolicitud.estado.in_(ESTADOS_ABIERTOS),
        PQRSSolicitud.area_desde.isnot(None),
    ).all()

    por_area: dict[str, list[dict]] = {}
    for s in solicitudes:
        limite = s.area_limite
        if limite is None:
            continue
        if limite.date() >= hoy:
            restantes = contar_habiles(hoy, limite.date())
        else:
            restantes = -contar_habiles(limite.date(), hoy)
        if restantes > dias_aviso:
            continue
        por_area.setdefault(s.area_responsable, []).append({
            "pqrs_id": s.id,
            "codigo": s.codigo_seguimiento or s.radicado_calidad,
            "tipo": s.tipo,
            "cliente": s.empresa or s.cliente_nombre,
            "dias_en_area": s.dias_en_area,
            "dias_restantes": restantes,
            "vencida": ahora > limite,
            "en_area_desde": con_zona(s.area_desde).isoformat(),
        })

    areas = []
    sin_destinatario = []
    for area, casos in por_area.items():
        casos.sort(key=lambda c: c["dias_restantes"])
        correos = sorted({
            u.email for u in db.query(User).filter(
                User.tenant_id == tenant_id, User.area == area, User.activo.is_(True),
            ).all() if u.email
        })
        grupo = {
            "area": area,
            "destinatarios": correos,
            "total": len(casos),
            "vencidas": sum(1 for c in casos if c["vencida"]),
            "casos": casos,
        }
        (areas if correos else sin_destinatario).append(grupo)

    areas.sort(key=lambda g: (-g["vencidas"], -g["total"]))
    return {
        "generado_en": ahora.isoformat(),
        "max_dias_habiles": MAX_DIAS_HABILES_EN_AREA,
        "dias_aviso": dias_aviso,
        "total": sum(g["total"] for g in areas + sin_destinatario),
        "areas": areas,
        # Áreas sin nadie activo a quien avisarle: van a quien reparte.
        "sin_destinatario": sin_destinatario,
        "correos_de_quien_reparte": capacidades.correos_de(db, tenant_id, CAPACIDAD_GESTION),
    }
