"""
Marcaciones: guardar lo que manda el script y responder lo que se pregunta.

Dos mitades que no se mezclan:

- **Escribir** (`sincronizar`): reemplaza la malla, agrega las marcaciones
  nuevas sin duplicar y registra el envío. Es idempotente: el script reenvía
  los últimos días en cada pasada.
- **Leer** (`dia`, `persona`, `informe`): trae marcaciones y malla, y deja que
  `evaluacion.py` decida qué es una novedad. Aquí no hay ninguna regla de
  asistencia, solo acarreo, zona horaria y agrupación.

**Zona horaria.** Se guarda en UTC y todo lo que ve una persona va en la hora
de pared de la empresa (`settings.ZONA_HORARIA`): lo que dice el reloj de la
pared, que es lo que dice la malla.
"""
import csv
import io
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.dias_habiles import hoy
from app.core.fechas import con_zona
from app.core.supervision import areas_visibles
from app.models.marcaciones import (
    MarEmpleado, MarExcepcion, MarFestivo, MarJustificacion, MarMarcacion, MarSincronizacion,
)
from app.models.user import User
from app.modules.marcaciones import constants as C
from app.modules.marcaciones import evaluacion
from app.modules.marcaciones.permisos import Alcance

DIAS_COLS = ("lun", "mar", "mie", "jue", "vie", "sab", "dom")
SIN_AREA = "Sin área"
SIN_LIDER = "Sin líder asignado"
ABREVIATURA = {"0": "Entrada", "1": "Salida", "2": "Sale a descanso", "3": "Regresa de descanso",
               "4": "Extra entrada", "5": "Extra salida"}


# ── Zona horaria ──────────────────────────────────────────────

def _zona() -> ZoneInfo:
    return ZoneInfo(settings.ZONA_HORARIA)


def local_a_utc(local: datetime) -> datetime:
    return local.replace(tzinfo=_zona()).astimezone(timezone.utc)


def utc_a_local(valor: datetime) -> datetime:
    """Hora de pared sin zona, que es lo que entiende `evaluacion.py`."""
    return con_zona(valor).astimezone(_zona()).replace(tzinfo=None)


def ahora_local() -> datetime:
    return datetime.now(_zona()).replace(tzinfo=None)


# ── Escribir: lo que manda el script ──────────────────────────

def registrar(db: Session, tenant_id: int, *, resumen: dict | None = None, error: str | None = None) -> None:
    """Deja constancia del envío, también del fallido: es la única forma de notar que el script se cayó."""
    resumen = resumen or {}
    ultima = resumen.get("ultima_marcacion")
    db.add(MarSincronizacion(
        tenant_id=tenant_id, ok=error is None, error=error,
        empleados=resumen.get("empleados", 0),
        marcaciones_nuevas=resumen.get("marcaciones_nuevas", 0),
        ultima_marcacion=local_a_utc(ultima) if ultima else None,
    ))


def _sincronizar_malla(db: Session, tenant_id: int, empleados: list[dict]) -> dict:
    existentes = {e.emp_code: e for e in db.query(MarEmpleado).filter(MarEmpleado.tenant_id == tenant_id)}
    nuevos = cambiados = 0
    for datos in empleados:
        fila = existentes.get(datos["emp_code"])
        if fila is None:
            db.add(MarEmpleado(tenant_id=tenant_id, activo=True, **datos))
            nuevos += 1
            continue
        if not fila.activo or any(getattr(fila, k) != v for k, v in datos.items()):
            for k, v in datos.items():
                setattr(fila, k, v)
            fila.activo = True
            cambiados += 1
    # Quien ya no está en la malla se desactiva, no se borra: sus marcaciones
    # viejas siguen siendo historia de la empresa.
    llegaron = {d["emp_code"] for d in empleados}
    desactivados = 0
    for codigo, fila in existentes.items():
        if codigo not in llegaron and fila.activo:
            fila.activo = False
            desactivados += 1
    return {"nuevos": nuevos, "actualizados": cambiados, "desactivados": desactivados}


def _sincronizar_marcaciones(db: Session, tenant_id: int, marcaciones: list[dict]) -> tuple[int, datetime | None]:
    if not marcaciones:
        return 0, None
    llegadas = {}
    for m in marcaciones:
        llegadas[(m["emp_code"], local_a_utc(m["momento"]), m["estado"])] = m["momento"]
    ini, fin = min(k[1] for k in llegadas), max(k[1] for k in llegadas)
    ya = {
        (c, con_zona(t), e)
        for c, t, e in db.query(MarMarcacion.emp_code, MarMarcacion.momento, MarMarcacion.estado).filter(
            MarMarcacion.tenant_id == tenant_id,
            MarMarcacion.momento >= ini, MarMarcacion.momento <= fin,
        )
    }
    nuevas = [k for k in llegadas if k not in ya]
    db.add_all(MarMarcacion(tenant_id=tenant_id, emp_code=c, momento=t, estado=e) for c, t, e in nuevas)
    return len(nuevas), max(llegadas.values())


def sincronizar(db: Session, tenant_id: int, payload: dict) -> dict:
    """
    Aplica un envío del script. `payload` es el `SincronizacionIn` ya como
    diccionario; una lista ausente (None) no toca nada de lo suyo.
    """
    resumen: dict = {"empleados": 0, "marcaciones_nuevas": 0, "ultima_marcacion": None}

    if payload.get("empleados") is not None:
        resumen["malla"] = _sincronizar_malla(db, tenant_id, payload["empleados"])
        resumen["empleados"] = len(payload["empleados"])

    if payload.get("festivos") is not None:
        db.query(MarFestivo).filter(MarFestivo.tenant_id == tenant_id).delete()
        db.add_all(MarFestivo(tenant_id=tenant_id, fecha=f["fecha"], nombre=f.get("nombre"))
                   for f in {f["fecha"]: f for f in payload["festivos"]}.values())
        resumen["festivos"] = len(payload["festivos"])

    if payload.get("excepciones") is not None:
        db.query(MarExcepcion).filter(MarExcepcion.tenant_id == tenant_id).delete()
        unicas = {(x["emp_code"], x["fecha"]): x for x in payload["excepciones"]}
        db.add_all(MarExcepcion(tenant_id=tenant_id, emp_code=x["emp_code"], fecha=x["fecha"], motivo=x.get("motivo"))
                   for x in unicas.values())
        resumen["excepciones"] = len(unicas)

    nuevas, ultima = _sincronizar_marcaciones(db, tenant_id, payload.get("marcaciones") or [])
    resumen["marcaciones_nuevas"] = nuevas
    resumen["marcaciones_recibidas"] = len(payload.get("marcaciones") or [])
    resumen["ultima_marcacion"] = ultima
    db.flush()
    return resumen


def estado(db: Session, tenant_id: int) -> dict:
    """
    Si lo que se ve está al día. Un tablero «en vivo» que dejó de estarlo y no
    lo dice es peor que no tenerlo.
    """
    ultima = (db.query(MarSincronizacion)
              .filter(MarSincronizacion.tenant_id == tenant_id, MarSincronizacion.ok.is_(True))
              .order_by(MarSincronizacion.creada_en.desc()).first())
    fallo = (db.query(MarSincronizacion)
             .filter(MarSincronizacion.tenant_id == tenant_id, MarSincronizacion.ok.is_(False))
             .order_by(MarSincronizacion.creada_en.desc()).first())
    if ultima is None:
        return {"nunca": True, "atrasado": True, "minutos_sin_datos": None,
                "ultima_sincronizacion": None, "ultima_marcacion": None,
                "ultimo_error": fallo.error if fallo else None}
    creada = con_zona(ultima.creada_en)
    minutos = int((datetime.now(timezone.utc) - creada).total_seconds() // 60)
    ultimo_error = None
    # Por id y no por hora: crece siempre, y dos envíos del mismo segundo no se confunden.
    if fallo and fallo.id > ultima.id:
        ultimo_error = fallo.error  # el último intento falló: es lo que hay que saber
    return {
        "nunca": False,
        "atrasado": minutos > C.MINUTOS_DATOS_ATRASADOS,
        "minutos_sin_datos": minutos,
        "ultima_sincronizacion": utc_a_local(creada).isoformat(sep=" ", timespec="seconds"),
        "ultima_marcacion": utc_a_local(ultima.ultima_marcacion).isoformat(sep=" ", timespec="seconds")
        if ultima.ultima_marcacion else None,
        "ultimo_error": ultimo_error,
    }


# ── Leer: acarreo, no reglas ──────────────────────────────────

def _empleado_dict(e: MarEmpleado) -> dict:
    d = {"emp_code": e.emp_code, "nombre": e.nombre, "area": e.area, "correo": e.correo, "activo": e.activo}
    d.update({c: getattr(e, c) or "" for c in DIAS_COLS})
    return d


def _empleados(db: Session, tenant_id: int, alcance: Alcance, area: str | None = None,
               emp_code: str | None = None) -> list[dict]:
    """La malla que esta persona puede ver, ya recortada por su alcance."""
    filas = db.query(MarEmpleado).filter(MarEmpleado.tenant_id == tenant_id).all()
    out = []
    for e in filas:
        if not alcance.permite(e.area, e.correo):
            continue
        if area and (e.area or SIN_AREA) != area:
            continue
        if emp_code and e.emp_code != emp_code:
            continue
        out.append(_empleado_dict(e))
    return out


def _marcas(db: Session, tenant_id: int, desde: date, hasta: date, codigos: list[str]) -> dict:
    """{emp_code: {fecha: [(hora_local, estado)]}} para [desde, hasta], ambos inclusive."""
    if not codigos:
        return {}
    ini = local_a_utc(datetime.combine(desde, time.min))
    fin = local_a_utc(datetime.combine(hasta + timedelta(days=1), time.min))
    por_codigo: dict = defaultdict(lambda: defaultdict(list))
    consulta = db.query(MarMarcacion.emp_code, MarMarcacion.momento, MarMarcacion.estado).filter(
        MarMarcacion.tenant_id == tenant_id,
        MarMarcacion.momento >= ini, MarMarcacion.momento < fin,
        MarMarcacion.emp_code.in_(codigos),
    )
    for codigo, momento, est in consulta:
        local = utc_a_local(momento)
        por_codigo[codigo][local.date()].append((local, est))
    for dias in por_codigo.values():
        for lista in dias.values():
            lista.sort()
    return por_codigo


def _historial(emp: dict, marcas_de_la_persona: dict, dia: date, festivos: set) -> list[str]:
    """Los turnos que esta persona hizo con certeza en sus últimos días: de ahí sale su turno habitual."""
    turnos = []
    for d in sorted((x for x in marcas_de_la_persona if x < dia), reverse=True):
        if d in festivos:
            continue
        t = evaluacion.turno_de_ese_dia(evaluacion.opciones_de(emp, d), d, marcas_de_la_persona[d])
        if t:
            turnos.append(t)
        if len(turnos) >= C.MAX_HISTORIAL:
            break
    return turnos


def _justificacion_dict(j: MarJustificacion) -> dict:
    return {"texto": j.texto, "autor": j.autor_nombre,
            "cuando": utc_a_local(j.actualizada_en or j.creada_en).isoformat(sep=" ", timespec="minutes")
            if (j.actualizada_en or j.creada_en) else None}


def _justificaciones(db: Session, tenant_id: int, desde: date, hasta: date, codigos: list[str]) -> dict:
    """{(fecha, emp_code, tipo): {texto, autor, cuando}} de las que cubren el rango."""
    if not codigos:
        return {}
    filas = db.query(MarJustificacion).filter(
        MarJustificacion.tenant_id == tenant_id,
        MarJustificacion.fecha >= desde, MarJustificacion.fecha <= hasta,
        MarJustificacion.emp_code.in_(codigos)).all()
    return {(j.fecha, j.emp_code, j.tipo): _justificacion_dict(j) for j in filas}


def evaluar_rango(db: Session, tenant_id: int, desde: date, hasta: date, empleados: list[dict]) -> dict[date, list[dict]]:
    """
    {fecha: filas evaluadas} de `desde` a `hasta`. Un día futuro no se evalúa;
    uno pasado se evalúa con el reloj en su último segundo; hoy, con la hora real.
    """
    codigos = [e["emp_code"] for e in empleados]
    marcas = _marcas(db, tenant_id, desde - timedelta(days=C.DIAS_HISTORIAL_TURNO), hasta, codigos)
    festivos = {f for (f,) in db.query(MarFestivo.fecha).filter(MarFestivo.tenant_id == tenant_id)}
    excepciones: dict = defaultdict(dict)
    for codigo, fecha, motivo in db.query(MarExcepcion.emp_code, MarExcepcion.fecha, MarExcepcion.motivo).filter(
            MarExcepcion.tenant_id == tenant_id, MarExcepcion.fecha >= desde, MarExcepcion.fecha <= hasta):
        excepciones[fecha][codigo] = motivo or "Justificado"

    justificaciones = _justificaciones(db, tenant_id, desde, hasta, codigos)

    hoy_ = hoy()
    ahora = ahora_local()
    resultado: dict[date, list[dict]] = {}
    dia = desde
    while dia <= hasta:
        if dia <= hoy_:
            reloj = ahora if dia == hoy_ else datetime.combine(dia, time(23, 59, 59))
            presentes = [e for e in empleados if e["activo"] or marcas.get(e["emp_code"], {}).get(dia)]
            del_dia = {e["emp_code"]: marcas.get(e["emp_code"], {}).get(dia, []) for e in presentes}
            historial = {e["emp_code"]: _historial(e, marcas.get(e["emp_code"], {}), dia, festivos) for e in presentes}
            resultado[dia] = evaluacion.evaluar_dia(
                dia, reloj, presentes, del_dia, historial,
                justificados=excepciones.get(dia), festivo=dia in festivos)
            # La novedad se calcula; el motivo se le pega después, así la regla
            # de asistencia no sabe nada de justificaciones.
            for fila in resultado[dia]:
                for n in fila["novedades"]:
                    n["justificacion"] = justificaciones.get((dia, fila["emp_code"], n["tipo"]))
        else:
            resultado[dia] = []
        dia += timedelta(days=1)
    return resultado


# ── Resúmenes ─────────────────────────────────────────────────

def _contar(filas: list[dict]) -> dict:
    cuenta = {p: 0 for p in C.PRESENCIAS}
    novedades = {n: 0 for n in C.NOVEDADES}
    justificadas = 0
    con_novedad = 0
    for f in filas:
        cuenta[f["presencia"]] = cuenta.get(f["presencia"], 0) + 1
        if f["novedades"]:
            con_novedad += 1
        for n in f["novedades"]:
            novedades[n["tipo"]] += 1
            if n.get("justificacion"):
                justificadas += 1
    total = sum(novedades.values())
    return {"personas": len(filas), **cuenta, "con_novedad": con_novedad,
            "total_novedades": total, "justificadas": justificadas,
            "sin_justificar": total - justificadas, "novedades": novedades}


def _lideres(db: Session, tenant_id: int) -> list[dict]:
    """Quienes responden por áreas: usuarios activos con rol de líder y lo que supervisan."""
    usuarios = db.query(User).filter(User.tenant_id == tenant_id, User.activo.is_(True), User.rol == "lider").all()
    return [{"nombre": u.nombre, "areas": areas_visibles(u)} for u in usuarios if areas_visibles(u)]


def _quienes(filas: list[dict]) -> list[dict]:
    """
    Las personas de un grupo que tienen novedad, con cuáles: lo que sale al
    pasar el cursor por la cifra de «Novedades». Una cifra que obliga a
    filtrar la lista para saber de quién habla no responde la pregunta.
    """
    con = [f for f in filas if f["novedades"]]
    con.sort(key=lambda f: (-len(f["novedades"]), f["nombre"].casefold()))
    return [{"emp_code": f["emp_code"], "nombre": f["nombre"],
             "novedades": [n["etiqueta"] for n in f["novedades"]]} for f in con]


def _grupo(filas: list[dict]) -> dict:
    return {**_contar(filas), "quienes": _quienes(filas)}


def resumen(filas: list[dict], lideres: list[dict]) -> dict:
    por_area: dict = defaultdict(list)
    for f in filas:
        por_area[f["area"] or SIN_AREA].append(f)
    areas = [{"area": a, **_grupo(fs)} for a, fs in sorted(por_area.items(), key=lambda kv: kv[0].casefold())]

    por_lider = []
    con_lider = set()
    for lid in lideres:
        suyas = [f for f in filas if (f["area"] or SIN_AREA) in lid["areas"]]
        if suyas:
            con_lider.update(f["emp_code"] for f in suyas)
            por_lider.append({"lider": lid["nombre"], "areas": lid["areas"], **_grupo(suyas)})
    huerfanas = [f for f in filas if f["emp_code"] not in con_lider]
    if huerfanas:
        por_lider.append({"lider": SIN_LIDER, "areas": sorted({f["area"] or SIN_AREA for f in huerfanas}),
                          **_grupo(huerfanas)})
    por_lider.sort(key=lambda x: (x["lider"] == SIN_LIDER, x["lider"].casefold()))
    return {"totales": _contar(filas), "por_area": areas, "por_lider": por_lider}


# ── Lo que consumen los endpoints ─────────────────────────────

def dia(db: Session, tenant_id: int, alcance: Alcance, fecha: date, area: str | None = None) -> dict:
    empleados = _empleados(db, tenant_id, alcance, area)
    filas = evaluar_rango(db, tenant_id, fecha, fecha, empleados)[fecha]
    festivo = db.query(MarFestivo).filter(MarFestivo.tenant_id == tenant_id, MarFestivo.fecha == fecha).first()
    lideres = _lideres(db, tenant_id) if alcance.tipo != "propio" else []
    return {
        "fecha": fecha.isoformat(), "es_hoy": fecha == hoy(),
        "futuro": fecha > hoy(),
        "festivo": festivo.nombre or "Festivo" if festivo else None,
        "generado": ahora_local().isoformat(sep=" ", timespec="seconds"),
        "alcance": {"tipo": alcance.tipo, "areas": list(alcance.areas),
                    "puede_justificar": alcance.puede_justificar},
        "estado": estado(db, tenant_id),
        "resumen": resumen(filas, lideres),
        "personas": filas,
    }


# ── Justificar (lo único que se escribe desde la pantalla) ────

def _persona_visible(db: Session, tenant_id: int, alcance: Alcance, emp_code: str) -> dict:
    if not alcance.puede_justificar:
        raise HTTPException(status_code=403, detail="Con tu rol solo puedes ver tus marcaciones; no justificar novedades.")
    empleados = _empleados(db, tenant_id, alcance, emp_code=emp_code)
    if not empleados:
        # Igual si no existe que si no es de su área: no se confirma que exista.
        raise HTTPException(status_code=404, detail="No se encontró a esa persona entre las marcaciones que puedes ver.")
    return empleados[0]


def _validar_tipo_y_fecha(tipo: str, fecha: date) -> None:
    if tipo not in C.NOVEDADES:
        raise HTTPException(status_code=400, detail=f"«{tipo}» no es una novedad conocida.")
    if fecha > hoy():
        raise HTTPException(status_code=400, detail="Ese día todavía no llega: no hay novedades que justificar.")


def justificar(db: Session, usuario: User, alcance: Alcance, emp_code: str, fecha: date, tipo: str, texto: str) -> dict:
    """Guarda (o corrige) el motivo de una novedad que esa persona tiene ese día."""
    _validar_tipo_y_fecha(tipo, fecha)
    emp = _persona_visible(db, usuario.tenant_id, alcance, emp_code)
    filas = evaluar_rango(db, usuario.tenant_id, fecha, fecha, [emp])[fecha]
    if not any(n["tipo"] == tipo for f in filas for n in f["novedades"]):
        raise HTTPException(status_code=400, detail="Esa persona no tiene esa novedad ese día; no hay nada que justificar.")
    j = db.query(MarJustificacion).filter(
        MarJustificacion.tenant_id == usuario.tenant_id, MarJustificacion.emp_code == emp_code,
        MarJustificacion.fecha == fecha, MarJustificacion.tipo == tipo).first()
    if j is None:
        j = MarJustificacion(tenant_id=usuario.tenant_id, emp_code=emp_code, fecha=fecha, tipo=tipo,
                             texto=texto, autor_id=usuario.id, autor_nombre=usuario.nombre)
        db.add(j)
    else:
        j.texto, j.autor_id, j.autor_nombre = texto, usuario.id, usuario.nombre
        j.actualizada_en = datetime.now(timezone.utc)
    db.commit()
    db.refresh(j)
    return _justificacion_dict(j)


def quitar_justificacion(db: Session, usuario: User, alcance: Alcance, emp_code: str, fecha: date, tipo: str) -> None:
    _validar_tipo_y_fecha(tipo, fecha)
    _persona_visible(db, usuario.tenant_id, alcance, emp_code)
    db.query(MarJustificacion).filter(
        MarJustificacion.tenant_id == usuario.tenant_id, MarJustificacion.emp_code == emp_code,
        MarJustificacion.fecha == fecha, MarJustificacion.tipo == tipo).delete()
    db.commit()


def _validar_rango(desde: date, hasta: date) -> None:
    if hasta < desde:
        raise HTTPException(status_code=400, detail="La fecha final es anterior a la inicial. Revisa el rango.")
    if (hasta - desde).days + 1 > C.MAX_DIAS_INFORME:
        raise HTTPException(
            status_code=400,
            detail=f"El rango es de más de {C.MAX_DIAS_INFORME} días. Pide el informe por tramos más cortos.")


def persona(db: Session, tenant_id: int, alcance: Alcance, emp_code: str, desde: date, hasta: date) -> dict:
    _validar_rango(desde, hasta)
    empleados = _empleados(db, tenant_id, alcance, emp_code=emp_code)
    if not empleados:
        # Igual si no existe que si no es suya: no se confirma que exista.
        raise HTTPException(status_code=404, detail="No se encontró a esa persona entre las marcaciones que puedes ver.")
    por_dia = evaluar_rango(db, tenant_id, desde, hasta, empleados)
    dias = []
    for fecha in sorted(por_dia, reverse=True):
        for f in por_dia[fecha]:
            dias.append({"fecha": fecha.isoformat(), **f})
    e = empleados[0]
    return {
        "persona": {"emp_code": e["emp_code"], "nombre": e["nombre"], "area": e["area"], "activo": e["activo"],
                    "malla": {c: e[c] for c in DIAS_COLS}},
        "desde": desde.isoformat(), "hasta": hasta.isoformat(),
        "puede_justificar": alcance.puede_justificar,
        "totales": _contar([d for d in dias]),
        "dias": dias,
    }


def informe(db: Session, tenant_id: int, alcance: Alcance, desde: date, hasta: date,
            area: str | None = None, emp_code: str | None = None, solo_novedades: bool = False) -> dict:
    _validar_rango(desde, hasta)
    # Las personas que se pueden elegir en el filtro: las del alcance y el
    # área, sin recortar por la persona elegida (si no, el desplegable
    # quedaría con una sola opción y no habría cómo cambiarla).
    del_alcance = _empleados(db, tenant_id, alcance, area)
    empleados = [e for e in del_alcance if not emp_code or e["emp_code"] == emp_code]
    por_dia = evaluar_rango(db, tenant_id, desde, hasta, empleados)
    filas = []
    for fecha in sorted(por_dia):
        for f in por_dia[fecha]:
            if solo_novedades and not f["novedades"]:
                continue
            filas.append({"fecha": fecha.isoformat(), **f})

    acumulado: dict = {}
    for f in filas:
        p = acumulado.setdefault(f["emp_code"], {
            "emp_code": f["emp_code"], "nombre": f["nombre"], "area": f["area"] or SIN_AREA,
            "dias": 0, "dias_con_novedad": 0, **{n: 0 for n in C.NOVEDADES}, "total_novedades": 0})
        if f["presencia"] not in ("justificado", "sin_turno"):
            p["dias"] += 1
        if f["novedades"]:
            p["dias_con_novedad"] += 1
        for n in f["novedades"]:
            p[n["tipo"]] += 1
            p["total_novedades"] += 1
    por_persona = sorted(acumulado.values(), key=lambda p: (-p["total_novedades"], p["nombre"].casefold()))

    por_area: dict = {}
    for p in por_persona:
        a = por_area.setdefault(p["area"], {"area": p["area"], "personas": 0, "dias_con_novedad": 0,
                                            **{n: 0 for n in C.NOVEDADES}, "total_novedades": 0})
        a["personas"] += 1
        a["dias_con_novedad"] += p["dias_con_novedad"]
        a["total_novedades"] += p["total_novedades"]
        for n in C.NOVEDADES:
            a[n] += p[n]

    return {
        "desde": desde.isoformat(), "hasta": hasta.isoformat(),
        "generado": ahora_local().isoformat(sep=" ", timespec="seconds"),
        "filtros": {"area": area, "emp_code": emp_code, "solo_novedades": solo_novedades},
        "alcance": {"tipo": alcance.tipo, "areas": list(alcance.areas),
                    "puede_justificar": alcance.puede_justificar},
        "totales": _contar(filas),
        "por_area": sorted(por_area.values(), key=lambda a: a["area"].casefold()),
        "por_persona": por_persona,
        "personas": sorted(({"emp_code": e["emp_code"], "nombre": e["nombre"], "area": e["area"] or SIN_AREA}
                            for e in del_alcance), key=lambda e: e["nombre"].casefold()),
        "filas": filas,
    }


# ── CSV ───────────────────────────────────────────────────────

def _celda(valor) -> str:
    """Una celda segura: un nombre que empiece por «=» no debe ejecutarse como fórmula al abrirlo en Excel."""
    texto = "" if valor is None else str(valor)
    return "'" + texto if texto[:1] in ("=", "+", "-", "@", "\t", "\r") else texto


def informe_csv(datos: dict) -> str:
    """
    Una fila por persona y día. Separador «;» y BOM UTF-8: es lo que abre bien
    Excel en español sin pasar por el asistente de importación.
    """
    salida = io.StringIO()
    w = csv.writer(salida, delimiter=";", lineterminator="\r\n")
    w.writerow(["Fecha", "Código", "Nombre", "Área", "Turno", "Primera entrada", "Marcaciones",
                "Estado", "Novedades", "Detalle", "Justificación"])
    for f in datos["filas"]:
        marcas = ", ".join(f"{m['hora']} {ABREVIATURA.get(m['estado'], m['estado'])}" for m in f["marcas"])
        w.writerow([_celda(x) for x in [
            f["fecha"], f["emp_code"], f["nombre"], f["area"] or SIN_AREA,
            f["turno"] or f["turno_opciones"] or "", f["primera_entrada"] or "", marcas,
            C.PRESENCIAS.get(f["presencia"], f["presencia"]),
            " | ".join(n["etiqueta"] for n in f["novedades"]),
            " | ".join(n["detalle"] for n in f["novedades"]),
            " | ".join(
                f"{n['etiqueta']}: {n['justificacion']['texto']} ({n['justificacion']['autor']})"
                for n in f["novedades"] if n.get("justificacion")),
        ]])
    return "﻿" + salida.getvalue()
