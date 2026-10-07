"""
El informe gerencial de PQRS de un periodo: cuántas entraron, de qué tipo,
por qué causa, por dónde y quién las radicó, y cómo se respondieron.

**Todo se calcula aquí**, porcentajes incluidos y redondeados una sola vez.
La pantalla solo lo pinta: si contara por su cuenta, el número del informe y
el de la lista terminarían sin coincidir, y en un informe que se le pasa a
gerencia eso es lo único que alguien va a recordar.

**El periodo es por fecha de RADICACIÓN, en la hora de la empresa.** «Las de
octubre» son las que entraron en octubre, aunque se hayan cerrado en
noviembre; y el día empieza a medianoche en Colombia, no en UTC (si no, las
que entran después de las 7 p. m. del 31 contarían para el mes siguiente).

**Cada quien ve el informe de lo que puede ver** (`filtrar_visibles`): un
punto de venta, el de sus PQRS; el resto, el de toda la empresa. Un informe
que mostrara más que la lista sería la forma de saltarse esa regla.
"""
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core import canales
from app.core.config import settings
from app.core.dias_habiles import contar_habiles, hoy
from app.core.fechas import con_zona
from app.models.pqrs import (
    PQRSAsociado, PQRSPasoArea, PQRSProducto, PQRSSeguimiento, PQRSSolicitud,
)
from app.models.user import User
from app.modules.pqrs.pendientes import ESTADOS_ABIERTOS
from app.modules.pqrs.permisos import filtrar_visibles

TIPOS = {
    "peticion": "Petición",
    "queja": "Queja",
    "reclamo": "Reclamo",
    "sugerencia": "Sugerencia",
    "felicitacion": "Felicitación",
}
ESTADOS = {
    "recibido": "Recibida",
    "asignado": "Asignada",
    "en_proceso": "En proceso",
    "resuelto": "Resuelta",
    "cerrado": "Cerrada",
}
# Un año y un poco: alcanza para comparar un año contra el anterior sin
# pedirle a la base el histórico completo de una vez.
MAX_DIAS_PERIODO = 400
# Hasta dos meses la tendencia va día por día; más largo, por mes.
MAX_DIAS_TENDENCIA_DIARIA = 62
TOP_PRODUCTOS = 8

MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre")


def _zona() -> ZoneInfo:
    return ZoneInfo(settings.ZONA_HORARIA)


def _inicio(dia: date) -> datetime:
    """Medianoche de ese día en la hora de la empresa, en UTC."""
    return datetime.combine(dia, time.min, tzinfo=_zona()).astimezone(timezone.utc)


def _dia_local(momento: datetime) -> date:
    return con_zona(momento).astimezone(_zona()).date()


def _pct(n: int, total: int) -> float | None:
    return round(n * 100 / total, 1) if total else None


def _filas(conteo: Counter, total: int, etiquetas: dict | None = None, extra: dict | None = None) -> list[dict]:
    """Una fila por categoría, de mayor a menor, con su porcentaje sobre `total`."""
    filas = []
    for clave, n in sorted(conteo.items(), key=lambda kv: (-kv[1], str(kv[0]))):
        fila = {"clave": clave, "etiqueta": (etiquetas or {}).get(clave, clave), "n": n, "pct": _pct(n, total)}
        fila.update((extra or {}).get(clave, {}))
        filas.append(fila)
    return filas


def etiqueta_periodo(desde: date, hasta: date) -> str:
    if desde.day == 1 and desde.year == hasta.year and desde.month == hasta.month:
        return f"{MESES[desde.month - 1].capitalize()} de {desde.year}"
    return f"Del {desde.day} de {MESES[desde.month - 1]} de {desde.year} " \
           f"al {hasta.day} de {MESES[hasta.month - 1]} de {hasta.year}"


def resolver_periodo(desde: date | None, hasta: date | None) -> tuple[date, date]:
    """Sin fechas, el mes en curso hasta hoy."""
    hoy_ = hoy()
    desde = desde or hoy_.replace(day=1)
    hasta = hasta or hoy_
    if desde > hasta:
        raise HTTPException(status_code=400, detail="La fecha inicial es posterior a la final. Revisa el periodo.")
    if (hasta - desde).days > MAX_DIAS_PERIODO:
        raise HTTPException(
            status_code=400,
            detail=f"El periodo puede ser de hasta {MAX_DIAS_PERIODO} días. Pide el informe por partes.",
        )
    return desde, hasta


def _solicitudes(db: Session, usuario: User, desde: date, hasta: date) -> list[PQRSSolicitud]:
    consulta = db.query(PQRSSolicitud).filter(
        PQRSSolicitud.tenant_id == usuario.tenant_id,
        PQRSSolicitud.fecha_creacion >= _inicio(desde),
        PQRSSolicitud.fecha_creacion < _inicio(hasta + timedelta(days=1)),
    )
    return filtrar_visibles(consulta, usuario).all()


def _quien_radico(db: Session, solicitudes: list[PQRSSolicitud]) -> dict[int, str]:
    """
    Quién la radicó: el cliente por el formulario web, o el ÁREA de quien la
    registró por dentro (Servicio al Cliente, Puntos de Venta…). Sale del
    primer evento del historial, que es el de la radicación y lleva al usuario.
    """
    internas = [s.id for s in solicitudes if s.origen_publico != "publico"]
    primero: dict[int, int | None] = {}
    if internas:
        for pqrs_id, usuario_id in (
            db.query(PQRSSeguimiento.pqrs_id, PQRSSeguimiento.usuario_id)
            .filter(PQRSSeguimiento.pqrs_id.in_(internas))
            .order_by(PQRSSeguimiento.pqrs_id, PQRSSeguimiento.id)
        ):
            primero.setdefault(pqrs_id, usuario_id)
    ids_usuario = {u for u in primero.values() if u}
    areas = dict(db.query(User.id, User.area).filter(User.id.in_(ids_usuario))) if ids_usuario else {}

    origen = {}
    for s in solicitudes:
        if s.origen_publico == "publico":
            origen[s.id] = "Cliente (formulario web)"
        else:
            area = areas.get(primero.get(s.id))
            origen[s.id] = f"Interno · {area}" if area else "Interno · sin área"
    return origen


def _respuesta(s: PQRSSolicitud) -> datetime | None:
    """Cuándo se le respondió al cliente: al resolverla, o al cerrarla directo."""
    return con_zona(s.fecha_resuelto) or con_zona(s.fecha_cierre)


def _tendencia(solicitudes: list[PQRSSolicitud], desde: date, hasta: date) -> dict:
    dias = (hasta - desde).days + 1
    por_dia = Counter(_dia_local(s.fecha_creacion) for s in solicitudes)
    if dias <= MAX_DIAS_TENDENCIA_DIARIA:
        puntos = []
        for i in range(dias):
            d = desde + timedelta(days=i)
            puntos.append({"clave": d.isoformat(), "etiqueta": str(d.day), "n": por_dia.get(d, 0)})
        return {"escala": "dia", "puntos": puntos}

    por_mes = Counter()
    for d, n in por_dia.items():
        por_mes[(d.year, d.month)] += n
    puntos = []
    anio, mes = desde.year, desde.month
    while (anio, mes) <= (hasta.year, hasta.month):
        puntos.append({"clave": f"{anio}-{mes:02d}", "etiqueta": f"{MESES[mes - 1][:3]} {anio}",
                       "n": por_mes.get((anio, mes), 0)})
        anio, mes = (anio + 1, 1) if mes == 12 else (anio, mes + 1)
    return {"escala": "mes", "puntos": puntos}


def construir(db: Session, usuario: User, desde: date | None = None, hasta: date | None = None) -> dict:
    desde, hasta = resolver_periodo(desde, hasta)
    solicitudes = _solicitudes(db, usuario, desde, hasta)
    total = len(solicitudes)
    ids = [s.id for s in solicitudes]
    ahora = datetime.now(timezone.utc)

    # El periodo anterior, del mismo largo y pegado a este: «octubre contra
    # septiembre», o «estas dos semanas contra las dos de antes».
    largo = (hasta - desde).days + 1
    ant_hasta = desde - timedelta(days=1)
    ant_desde = ant_hasta - timedelta(days=largo - 1)
    total_anterior = len(_solicitudes(db, usuario, ant_desde, ant_hasta))

    # ── Cómo se respondieron ──
    abiertas = [s for s in solicitudes if s.estado in ESTADOS_ABIERTOS]
    vencidas = [s for s in abiertas if con_zona(s.fecha_limite_sla) and con_zona(s.fecha_limite_sla) < ahora]
    respondidas = [s for s in solicitudes if _respuesta(s)]
    con_plazo = [s for s in respondidas if con_zona(s.fecha_limite_sla)]
    a_tiempo = [s for s in con_plazo if _respuesta(s) <= con_zona(s.fecha_limite_sla)]
    dias_respuesta = [
        contar_habiles(_dia_local(s.fecha_creacion), _dia_local(_respuesta(s))) for s in respondidas
    ]

    # ── Causa ──
    catalogo = {a.id: a for a in db.query(PQRSAsociado).filter(PQRSAsociado.tenant_id == usuario.tenant_id)}
    con_causa = [s for s in solicitudes if s.asociado_id]
    por_asociado = Counter(s.asociado_id for s in con_causa)
    por_grupo = Counter(catalogo[s.asociado_id].grupo for s in con_causa if s.asociado_id in catalogo)

    # ── Por dónde y quién ──
    tipos_canal = {c.nombre: c.tipo for c in canales.del_tenant(db, usuario.tenant_id, incluir_inactivos=True)}
    por_canal = Counter(s.canal_atencion or "Sin canal" for s in solicitudes)
    origen = _quien_radico(db, solicitudes)

    # ── Productos ──
    productos = Counter()
    if ids:
        for p in db.query(PQRSProducto).filter(PQRSProducto.pqrs_id.in_(ids)):
            nombre = (p.producto_nombre or "").strip()
            if nombre:
                productos[nombre + (" (sin confirmar)" if p.por_confirmar else "")] += 1

    # ── Tiempo de cada área (tramos terminados: el que está en curso no tiene final) ──
    tramos = defaultdict(list)
    if ids:
        for paso in db.query(PQRSPasoArea).filter(PQRSPasoArea.pqrs_id.in_(ids)):
            tramos[paso.area].append(paso)
    tiempo_por_area = sorted((
        {
            "area": area,
            "tramos": len(pasos),
            "promedio_dias": round(sum(p.dias_habiles for p in pasos) / len(pasos), 1),
            "excedidos": sum(1 for p in pasos if p.excedio),
            "pct_excedidos": _pct(sum(1 for p in pasos if p.excedio), len(pasos)),
        } for area, pasos in tramos.items()
    ), key=lambda f: (-f["tramos"], f["area"]))

    return {
        "periodo": {
            "desde": desde.isoformat(), "hasta": hasta.isoformat(),
            "etiqueta": etiqueta_periodo(desde, hasta),
            "anterior": {"desde": ant_desde.isoformat(), "hasta": ant_hasta.isoformat(),
                         "etiqueta": etiqueta_periodo(ant_desde, ant_hasta)},
            "generado": ahora.isoformat(),
        },
        "resumen": {
            "total": total,
            "total_anterior": total_anterior,
            "variacion_pct": (round((total - total_anterior) * 100 / total_anterior, 1)
                              if total_anterior else None),
            "abiertas": len(abiertas),
            "vencidas": len(vencidas),
            "respondidas": len(respondidas),
            "a_tiempo": len(a_tiempo),
            "con_plazo": len(con_plazo),
            "pct_a_tiempo": _pct(len(a_tiempo), len(con_plazo)),
            "dias_respuesta_promedio": (round(sum(dias_respuesta) / len(dias_respuesta), 1)
                                        if dias_respuesta else None),
            "con_causa": len(con_causa),
            "sin_causa": total - len(con_causa),
            "pct_con_causa": _pct(len(con_causa), total),
        },
        "por_tipo": _filas(Counter(s.tipo for s in solicitudes), total, TIPOS),
        "por_estado": _filas(Counter(s.estado for s in solicitudes), total, ESTADOS),
        # La causa se mide sobre las que TIENEN causa: si no, el «sin
        # clasificar» se comería los porcentajes y no se sabría qué pesa más.
        "por_asociado": _filas(
            por_asociado, len(con_causa),
            {i: f"({a.codigo}) {a.nombre}" for i, a in catalogo.items()},
            {i: {"grupo": a.grupo} for i, a in catalogo.items()},
        ),
        "por_grupo_causa": _filas(por_grupo, len(con_causa)),
        "por_area_causante": _filas(
            Counter(s.area_causante for s in solicitudes if s.area_causante),
            sum(1 for s in solicitudes if s.area_causante),
        ),
        "por_canal": _filas(por_canal, total, extra={
            nombre: {"tipo": tipos_canal.get(nombre)} for nombre in por_canal
        }),
        "por_origen": _filas(Counter(origen.values()), total),
        "por_area_actual": _filas(Counter(s.area_responsable or "Sin asignar" for s in abiertas), len(abiertas)),
        "top_productos": _filas(Counter(dict(productos.most_common(TOP_PRODUCTOS))), sum(productos.values())),
        "productos_distintos": len(productos),
        "tiempo_por_area": tiempo_por_area,
        "tendencia": _tendencia(solicitudes, desde, hasta),
    }
