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

from app.core import areas, canales, capacidades
from app.core.dias_habiles import contar_habiles
from app.core.fechas import con_zona
from app.models.autorizacion import AutorizacionPQRS, TipoAutorizacion
from app.models.pqrs import PQRSAsociado, PQRSPasoArea, PQRSSeguimiento, PQRSSolicitud
from app.modules.pqrs.permisos import CAPACIDAD_GESTION

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


def areas_repetidas(ruta: list[str], centro: str | None) -> list[str]:
    """
    Las áreas que tuvieron el caso más de una vez, SIN contar al centro.

    Servicio al Cliente aparece una y otra vez por diseño: cada concepto sale
    de ahí y vuelve ahí. Contarlo como «ida y vuelta» hacía ver como error lo
    que es la forma de trabajar (40 de 56 en la primera corrida). Lo que sí
    es señal es que OTRA área reciba el mismo caso dos veces: se le pidió
    algo, se le volvió a pedir — casi siempre porque la primera vez fue mal.
    """
    vistas = Counter(a for a in ruta if a != centro and a != SIN_AREA)
    return [a for a, n in vistas.items() if n > 1]


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


def _nombre_concepto(nombre: str) -> str:
    # «Concepto Área Técnica  (Calidad)» con dos espacios es el mismo concepto.
    return " ".join((nombre or "").split())


def plantilla(cadenas: list[list[str]]) -> dict:
    """
    La plantilla candidata de un grupo: los conceptos que pide al menos la
    mitad de sus PQRS (de las que piden alguno), en el orden en que suelen
    pedirse. Es lo que el portal podría pedir solo, uno detrás de otro.

    El orden se saca de la posición PROMEDIO de cada concepto, no de la
    cadena más repetida: en los datos reales el orden varía de un caso a
    otro, y por eso ninguna cadena exacta se repite aunque el trámite sea
    casi siempre el mismo.
    """
    con_conceptos = [c for c in cadenas if c]
    if len(con_conceptos) < MINIMO_CASOS:
        n = len(con_conceptos)
        if n == 0:
            return {"hay_plantilla": False, "motivo": "Ninguna PQRS pidió conceptos."}
        return {"hay_plantilla": False,
                "motivo": f"Solo {n} {'PQRS pidió' if n == 1 else 'PQRS pidieron'} conceptos: muy pocas para decidir."}

    presencia = Counter()
    posiciones = defaultdict(list)
    for cadena in con_conceptos:
        vistos = []
        for concepto in cadena:
            if concepto not in vistos:  # el segundo pedido es un reintento, no otro paso
                vistos.append(concepto)
        for i, concepto in enumerate(vistos):
            presencia[concepto] += 1
            posiciones[concepto].append(i / max(len(vistos) - 1, 1))

    total = len(con_conceptos)
    frecuentes = [c for c, n in presencia.items() if n / total >= UMBRAL_PATRON]
    if not frecuentes:
        mas = presencia.most_common(1)[0]
        return {"hay_plantilla": False,
                "motivo": f"Ningún concepto lo pide la mitad de las PQRS (el más común, {mas[0]}, el {_pct(mas[1], total)}%)."}
    orden = sorted(frecuentes, key=lambda c: sum(posiciones[c]) / len(posiciones[c]))
    return {
        "hay_plantilla": True,
        "pasos": [{"concepto": c, "pct": _pct(presencia[c], total)} for c in orden],
        "sobre": total,
    }


def _tipo_de_canal(solicitud: PQRSSolicitud, canales_por_nombre: dict, prefijos: list) -> str | None:
    """
    El tipo del canal por el que entró: por su nombre, o si no lo tiene, por
    el prefijo del radicado (`VI0012` → Venta institucional). Exacto, como en
    la lista: `PVCR0001` no es de `PVC`.
    """
    canal = canales_por_nombre.get(solicitud.canal_atencion)
    if canal:
        return canal.tipo
    codigo = solicitud.codigo_seguimiento or ""
    for prefijo, tipo in prefijos:
        if re.fullmatch(rf"{re.escape(prefijo)}\d+", codigo):
            return tipo
    return None


ETIQUETA_CANAL = {
    "institucional": "Venta institucional",
    "sede": "Punto de venta",
    "general": "Otros canales (WhatsApp, línea…)",
    None: "Sin canal",
}


def analizar(db: Session, tenant_id: int, desde: date | None = None, top: int = 5) -> dict:
    consulta = db.query(PQRSSolicitud).filter(PQRSSolicitud.tenant_id == tenant_id)
    if desde:
        consulta = consulta.filter(PQRSSolicitud.fecha_creacion >= datetime.combine(desde, datetime.min.time(), tzinfo=timezone.utc))
    solicitudes = consulta.all()
    ids = [s.id for s in solicitudes]

    # El centro es quien reparte; si nadie tiene la capacidad, no hay centro.
    centro = capacidades.area_principal(db, tenant_id, CAPACIDAD_GESTION)

    seguimientos = defaultdict(list)
    if ids:
        for s in db.query(PQRSSeguimiento).filter(PQRSSeguimiento.pqrs_id.in_(ids)):
            seguimientos[s.pqrs_id].append(s)

    # Los conceptos (autorizaciones) de cada PQRS, en el orden en que se pidieron.
    conceptos = defaultdict(list)
    if ids:
        filas = (
            db.query(AutorizacionPQRS, TipoAutorizacion)
            .join(TipoAutorizacion, AutorizacionPQRS.tipo_id == TipoAutorizacion.id)
            .filter(AutorizacionPQRS.pqrs_id.in_(ids))
        )
        for aut, tipo in filas:
            conceptos[aut.pqrs_id].append((aut, tipo))
    for lista in conceptos.values():
        lista.sort(key=lambda par: (con_zona(par[0].fecha_solicitud) or datetime.min.replace(tzinfo=timezone.utc), par[0].id))

    asociados = {a.id: a for a in db.query(PQRSAsociado).filter(PQRSAsociado.tenant_id == tenant_id)}
    todos_canales = canales.del_tenant(db, tenant_id, incluir_inactivos=True)
    canales_por_nombre = {c.nombre: c for c in todos_canales}
    # Los prefijos largos primero: `PVCR` antes que `PVC`.
    prefijos = sorted(((c.prefijo, c.tipo) for c in todos_canales if c.prefijo), key=lambda p: -len(p[0]))

    casos = []
    for s in solicitudes:
        r = recorrido(s, seguimientos[s.id])
        cadena = [_nombre_concepto(t.nombre) for _, t in conceptos[s.id]]
        casos.append({
            "id": s.id, "codigo": s.codigo_seguimiento or f"#{s.id}", "tipo": s.tipo,
            "estado": s.estado, "asociado_id": s.asociado_id,
            "canal": _tipo_de_canal(s, canales_por_nombre, prefijos),
            "conceptos": cadena,
            "repetidas": areas_repetidas(r["ruta"], centro),
            **r,
        })

    total = len(casos)
    rutas = [tuple(c["ruta"]) for c in casos]
    movidas = [c for c in casos if len(c["ruta"]) > 1]
    con_repetidas = [c for c in casos if c["repetidas"]]

    # Transiciones A → B y en cuántas PQRS aparece cada área
    transiciones = Counter()
    presencia = Counter()
    for c in casos:
        presencia.update(set(c["ruta"]))
        transiciones.update(zip(c["ruta"], c["ruta"][1:]))

    resolvio = Counter(c["resolvio"] for c in casos if c["resolvio"])

    # Por tipo, por canal y por causa: la cadena de conceptos más común y la
    # plantilla candidata, que es lo que se automatizaría.
    def agrupado(clave_de, etiqueta_de, incluir_vacios=False):
        grupos = defaultdict(list)
        for c in casos:
            clave = clave_de(c)
            if clave is not None or incluir_vacios:
                grupos[clave].append(c)
        salida = []
        for clave, grupo in sorted(grupos.items(), key=lambda kv: -len(kv[1])):
            cadenas = [c["conceptos"] for c in grupo]
            salida.append({
                "grupo": etiqueta_de(clave), "n": len(grupo),
                "sin_conceptos": sum(1 for c in cadenas if not c),
                "cadenas": [
                    {"cadena": list(k), "n": n, "pct": _pct(n, len(grupo))}
                    for k, n in Counter(tuple(c) for c in cadenas if c).most_common(top)
                ],
                "plantilla": plantilla(cadenas),
                "recorridos": _recorridos([tuple(c["ruta"]) for c in grupo], top),
                "resuelve": Counter(c["resolvio"] for c in grupo if c["resolvio"]).most_common(3),
                "patron": _patron([tuple(c["ruta"]) for c in grupo]),
            })
        return salida

    por_tipo = agrupado(lambda c: c["tipo"], lambda t: TIPOS.get(t, t))
    # «Sin canal» también es un grupo: son PQRS que existen y hay que verlas.
    por_canal = agrupado(lambda c: c["canal"], lambda t: ETIQUETA_CANAL.get(t, t), incluir_vacios=True)
    por_tipo_y_canal = agrupado(
        lambda c: (c["tipo"], c["canal"]),
        lambda k: f"{TIPOS.get(k[0], k[0])} · {ETIQUETA_CANAL.get(k[1], k[1])}",
    )
    por_asociado = agrupado(
        lambda c: c["asociado_id"],
        lambda i: f"({asociados[i].codigo}) {asociados[i].nombre}" if i in asociados else f"#{i}",
    )

    # Cada concepto: cuántas veces, en cuántas PQRS, cómo se respondió, cuánto
    # tarda, y cuántas veces se volvió a pedir después de un rechazo o una
    # devolución (la señal de que se había pedido mal o incompleto).
    estadisticas = defaultdict(lambda: {"veces": 0, "pqrs": set(), "estados": Counter(), "dias": [],
                                        "repedido": 0, "area": None})
    for pqrs_id, lista in conceptos.items():
        cerrados = set()
        for aut, tipo in lista:
            nombre = _nombre_concepto(tipo.nombre)
            e = estadisticas[(nombre, tipo.area_autorizadora)]
            e["veces"] += 1
            e["pqrs"].add(pqrs_id)
            e["estados"][aut.estado] += 1
            e["area"] = tipo.area_autorizadora
            if nombre in cerrados:
                e["repedido"] += 1
            if aut.estado in ("rechazada", "devuelta"):
                cerrados.add(nombre)
            if aut.fecha_respuesta and aut.fecha_solicitud:
                e["dias"].append(contar_habiles(con_zona(aut.fecha_solicitud).date(), con_zona(aut.fecha_respuesta).date()))
    autorizaciones = [
        {
            "tipo": nombre, "area": area, "n": e["veces"], "pqrs": len(e["pqrs"]),
            "estados": dict(e["estados"]), "repedido": e["repedido"],
            "dias_promedio": round(sum(e["dias"]) / len(e["dias"]), 1) if e["dias"] else None,
        }
        for (nombre, area), e in sorted(estadisticas.items(), key=lambda kv: -kv[1]["veces"])
    ]

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
        "centro": centro,
        "resumen": {
            "pqrs": total,
            "abiertas": sum(1 for c in casos if c["estado"] != "cerrado"),
            "se_movieron": len(movidas),
            "areas_promedio": round(sum(len(c["ruta"]) for c in casos) / total, 2) if total else 0,
            "areas_maximo": max((len(c["ruta"]) for c in casos), default=0),
            "con_repetidas": len(con_repetidas),
            "con_conceptos": sum(1 for c in casos if c["conceptos"]),
            "conceptos_promedio": round(sum(len(c["conceptos"]) for c in casos if c["conceptos"])
                                        / max(1, sum(1 for c in casos if c["conceptos"])), 1),
            "movimientos_ilegibles": sum(c["ilegibles"] for c in casos),
            "con_causa": sum(1 for c in casos if c["asociado_id"]),
        },
        "recorridos": _recorridos(rutas, top * 2),
        "por_tipo": por_tipo,
        "por_canal": por_canal,
        "por_tipo_y_canal": por_tipo_y_canal,
        "por_asociado": por_asociado,
        "areas": [
            {"area": a, "pqrs": n, "pct": _pct(n, total), "resolvio": resolvio.get(a, 0)}
            for a, n in presencia.most_common()
        ],
        "transiciones": [{"de": a, "a": b, "n": n} for (a, b), n in transiciones.most_common(15)],
        "repetidas": [{"codigo": c["codigo"], "areas": c["repetidas"], "ruta": c["ruta"]} for c in con_repetidas[:15]],
        "autorizaciones": autorizaciones,
        "tiempos": tiempos,
        "casos": casos,
    }
