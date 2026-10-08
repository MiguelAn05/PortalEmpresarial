"""
El flujo REAL de las PQRS, reconstruido desde su historial.

Es el primer paso para automatizar el recorrido de una PQRS: antes de
decidir «un reclamo por mala entrega va a Logística y vuelve», hay que saber
por dónde han ido de verdad. Esto no decide nada ni escribe nada: lee el
historial y cuenta. **La ruta oficial la deciden las personas** con este
reporte en la mano; los datos dicen cómo se hace hoy, errores incluidos.

De dónde sale cada cosa:

- **Los movimientos de área**, del comentario que el propio portal redacta
  al moverla. Hoy es «Área: X -> Y.» (gestión y autorizaciones); antes fue
  «Área asignada: Y.», que no dice el origen y se completa con el área que
  tenía la PQRS justo antes. Si alguien escribió un comentario propio en ese
  formato viejo, el destino no se puede leer: **se cuenta aparte, no se
  adivina**.
- **El área con la que nació**: el origen del primer movimiento, o el área
  actual si nunca se movió.
- **Quién la resolvió**: el área que la tenía cuando pasó a «resuelto».
- **Los tiempos por área**, de `pqrs_pasos_area`, que existe desde la 0.48.
"""
import re
from collections import Counter, defaultdict
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from app.core import areas
from app.core.dias_habiles import contar_habiles
from app.core.fechas import con_zona
from app.models.autorizacion import AutorizacionPQRS, TipoAutorizacion
from app.models.pqrs import PQRSAsociado, PQRSPasoArea, PQRSSeguimiento, PQRSSolicitud

SIN_AREA = "Sin asignar"

# «Área: Servicio al Cliente -> Calidad.» y «… -> Calidad mientras se responde.»
# El nombre termina en el punto que cierra la frase. No confundir con «Área
# causante: …», que es otra cosa y no mueve el caso.
_MOVIMIENTO = re.compile(r"Área: (?P<origen>[^.]+?) -> (?P<destino>[^.]+?)(?: mientras se responde)?\.(?:\s|$)")
_MOVIMIENTO_VIEJO = re.compile(r"Área asignada: (?P<destino>[^.]+?)\.(?:\s|$)")

# Con al menos esta parte de los casos, un recorrido ya es la norma y vale la
# pena proponerlo como ruta. Por debajo, no hay patrón: hay que decidir.
UMBRAL_PATRON = 0.5
# Con menos casos que estos, un porcentaje no dice nada.
MINIMO_CASOS = 3

TIPOS = {
    "peticion": "Petición", "queja": "Queja", "reclamo": "Reclamo",
    "sugerencia": "Sugerencia", "felicitacion": "Felicitación",
}


def _area(nombre: str | None) -> str:
    nombre = (nombre or "").strip()
    if not nombre or nombre.lower() == "sin asignar":
        return SIN_AREA
    return areas.normalizar(nombre) or SIN_AREA


def movimientos(seguimiento: PQRSSeguimiento) -> list[tuple[str | None, str]] | None:
    """
    Los movimientos de área que dice un evento del historial, como pares
    (origen, destino). Origen None = el formato viejo, que no lo dice.
    Devuelve None si el evento es de mover área pero no se puede leer.
    """
    texto = seguimiento.comentario or ""
    encontrados = [(_area(m["origen"]), _area(m["destino"])) for m in _MOVIMIENTO.finditer(texto)]
    if not encontrados:
        encontrados = [(None, _area(m["destino"])) for m in _MOVIMIENTO_VIEJO.finditer(texto)]
    if not encontrados and seguimiento.tipo_evento == "asignacion_area":
        return None
    return encontrados


def recorrido(solicitud: PQRSSolicitud, seguimientos: list[PQRSSeguimiento]) -> dict:
    """
    Por qué áreas pasó una PQRS, en orden, sin repetir la misma dos veces
    seguidas; qué área la tenía al resolverse, y cuántos movimientos no se
    pudieron leer.
    """
    eventos = sorted(seguimientos, key=lambda s: (con_zona(s.fecha) or datetime.min.replace(tzinfo=timezone.utc), s.id))
    pares, ilegibles = [], 0
    # Cuántos movimientos llevaba cuando se resolvió: el área se sabe al
    # final, porque la de nacimiento sale del PRIMER movimiento, que puede
    # venir después de resolverla (se reabrió y se movió).
    movimientos_al_resolver = None
    for s in eventos:
        leidos = movimientos(s)
        if leidos is None:
            ilegibles += 1
            continue
        for origen, destino in leidos:
            # El formato viejo no dice de dónde salió: del área que tenía.
            anterior = pares[-1][1] if pares else None
            pares.append((origen if origen is not None else anterior, destino))
        if s.estado_nuevo == "resuelto" and movimientos_al_resolver is None:
            movimientos_al_resolver = len(pares)

    if pares:
        ruta = [pares[0][0] or SIN_AREA]
        for _, destino in pares:
            if destino != ruta[-1]:
                ruta.append(destino)
    else:
        ruta = [_area(solicitud.area_responsable)]

    if movimientos_al_resolver is not None:
        resolvio = pares[movimientos_al_resolver - 1][1] if movimientos_al_resolver else ruta[0]
    elif solicitud.estado in ("resuelto", "cerrado"):
        # Sin evento «resuelto» en el historial (PQRS vieja, o cerrada directo):
        # la que la tenía al final.
        resolvio = ruta[-1]
    else:
        resolvio = None

    return {"ruta": ruta, "resolvio": resolvio, "ilegibles": ilegibles}


def _hay_ida_y_vuelta(ruta: list[str]) -> bool:
    """A → B → A: el caso volvió a un área que ya lo había tenido."""
    return any(ruta[i] == ruta[i + 2] for i in range(len(ruta) - 2))


def _pct(n: int, total: int) -> float:
    return round(n * 100 / total, 1) if total else 0.0


def _recorridos(rutas: list[tuple[str, ...]], top: int) -> list[dict]:
    conteo = Counter(rutas)
    total = len(rutas)
    return [
        {"ruta": list(r), "n": n, "pct": _pct(n, total)}
        for r, n in conteo.most_common(top)
    ]


def _patron(rutas: list[tuple[str, ...]]) -> dict:
    """¿Hay un recorrido que ya sea la norma? Lo que se propondría como ruta."""
    if len(rutas) < MINIMO_CASOS:
        casos = "1 caso" if len(rutas) == 1 else f"{len(rutas)} casos"
        return {"hay_patron": False, "motivo": f"Solo {casos}: muy pocos para decidir."}
    ruta, n = Counter(rutas).most_common(1)[0]
    share = n / len(rutas)
    if share >= UMBRAL_PATRON:
        return {"hay_patron": True, "ruta": list(ruta), "pct": round(share * 100, 1)}
    return {"hay_patron": False, "motivo": f"El recorrido más común es solo el {round(share * 100, 1)}%: no hay una norma."}


def analizar(db: Session, tenant_id: int, desde: date | None = None, top: int = 5) -> dict:
    consulta = db.query(PQRSSolicitud).filter(PQRSSolicitud.tenant_id == tenant_id)
    if desde:
        consulta = consulta.filter(PQRSSolicitud.fecha_creacion >= datetime.combine(desde, datetime.min.time(), tzinfo=timezone.utc))
    solicitudes = consulta.all()
    ids = [s.id for s in solicitudes]

    seguimientos = defaultdict(list)
    if ids:
        for s in db.query(PQRSSeguimiento).filter(PQRSSeguimiento.pqrs_id.in_(ids)):
            seguimientos[s.pqrs_id].append(s)

    asociados = {a.id: a for a in db.query(PQRSAsociado).filter(PQRSAsociado.tenant_id == tenant_id)}

    casos = []
    for s in solicitudes:
        r = recorrido(s, seguimientos[s.id])
        casos.append({
            "id": s.id, "codigo": s.codigo_seguimiento or f"#{s.id}", "tipo": s.tipo,
            "estado": s.estado, "asociado_id": s.asociado_id, **r,
        })

    total = len(casos)
    rutas = [tuple(c["ruta"]) for c in casos]
    movidas = [c for c in casos if len(c["ruta"]) > 1]
    idas_y_vueltas = [c for c in casos if _hay_ida_y_vuelta(c["ruta"])]

    # Transiciones A → B y en cuántas PQRS aparece cada área
    transiciones = Counter()
    presencia = Counter()
    for c in casos:
        presencia.update(set(c["ruta"]))
        transiciones.update(zip(c["ruta"], c["ruta"][1:]))

    resolvio = Counter(c["resolvio"] for c in casos if c["resolvio"])

    # Por tipo y por causa: el recorrido más común y si ya es la norma.
    def agrupado(clave_de, etiqueta_de):
        grupos = defaultdict(list)
        for c in casos:
            clave = clave_de(c)
            if clave is not None:
                grupos[clave].append(c)
        salida = []
        for clave, grupo in sorted(grupos.items(), key=lambda kv: -len(kv[1])):
            rutas_g = [tuple(c["ruta"]) for c in grupo]
            salida.append({
                "grupo": etiqueta_de(clave), "n": len(grupo),
                "recorridos": _recorridos(rutas_g, top),
                "resuelve": Counter(c["resolvio"] for c in grupo if c["resolvio"]).most_common(3),
                "patron": _patron(rutas_g),
            })
        return salida

    por_tipo = agrupado(lambda c: c["tipo"], lambda t: TIPOS.get(t, t))
    por_asociado = agrupado(
        lambda c: c["asociado_id"],
        lambda i: f"({asociados[i].codigo}) {asociados[i].nombre}" if i in asociados else f"#{i}",
    )

    # Autorizaciones: a quién se le pide qué, y cuántas vuelven devueltas
    # (una devuelta es un caso mal dirigido).
    autorizaciones = []
    if ids:
        filas = (
            db.query(AutorizacionPQRS, TipoAutorizacion)
            .join(TipoAutorizacion, AutorizacionPQRS.tipo_id == TipoAutorizacion.id)
            .filter(AutorizacionPQRS.pqrs_id.in_(ids))
        )
        por_tipo_aut = defaultdict(list)
        for aut, tipo in filas:
            por_tipo_aut[(tipo.nombre, tipo.area_autorizadora)].append(aut)
        for (nombre, area), lista in sorted(por_tipo_aut.items(), key=lambda kv: -len(kv[1])):
            dias = [
                contar_habiles(con_zona(a.fecha_solicitud).date(), con_zona(a.fecha_respuesta).date())
                for a in lista if a.fecha_respuesta and a.fecha_solicitud
            ]
            estados = Counter(a.estado for a in lista)
            autorizaciones.append({
                "tipo": nombre, "area": area, "n": len(lista),
                "estados": dict(estados),
                "dias_promedio": round(sum(dias) / len(dias), 1) if dias else None,
            })

    # Tiempo en cada área (tramos terminados, desde la 0.48)
    tiempos = []
    if ids:
        tramos = defaultdict(list)
        for p in db.query(PQRSPasoArea).filter(PQRSPasoArea.pqrs_id.in_(ids)):
            tramos[_area(p.area)].append(p)
        for area, lista in sorted(tramos.items(), key=lambda kv: -len(kv[1])):
            tiempos.append({
                "area": area, "tramos": len(lista),
                "dias_promedio": round(sum(p.dias_habiles for p in lista) / len(lista), 1),
                "pasadas": sum(1 for p in lista if p.excedio),
            })

    return {
        "resumen": {
            "pqrs": total,
            "abiertas": sum(1 for c in casos if c["estado"] != "cerrado"),
            "se_movieron": len(movidas),
            "areas_promedio": round(sum(len(c["ruta"]) for c in casos) / total, 2) if total else 0,
            "areas_maximo": max((len(c["ruta"]) for c in casos), default=0),
            "idas_y_vueltas": len(idas_y_vueltas),
            "movimientos_ilegibles": sum(c["ilegibles"] for c in casos),
            "con_causa": sum(1 for c in casos if c["asociado_id"]),
        },
        "recorridos": _recorridos(rutas, top * 2),
        "por_tipo": por_tipo,
        "por_asociado": por_asociado,
        "areas": [
            {"area": a, "pqrs": n, "pct": _pct(n, total), "resolvio": resolvio.get(a, 0)}
            for a, n in presencia.most_common()
        ],
        "transiciones": [{"de": a, "a": b, "n": n} for (a, b), n in transiciones.most_common(15)],
        "idas_y_vueltas": [{"codigo": c["codigo"], "ruta": c["ruta"]} for c in idas_y_vueltas[:15]],
        "autorizaciones": autorizaciones,
        "tiempos": tiempos,
        "casos": casos,
    }
