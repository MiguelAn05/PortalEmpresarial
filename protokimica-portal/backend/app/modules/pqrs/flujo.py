"""
El flujo de conceptos de una PQRS: qué autorizaciones se piden, en qué orden,
y que el portal pida la siguiente solo.

**Por qué es una cadena de conceptos y no una ruta de áreas.** El análisis del
historial (`flujo_historico.py`, 56 PQRS reales) mostró que el caso no viaja
de área en área: Servicio al Cliente pide un concepto, el área responde, el
caso vuelve, se pide el siguiente. En venta institucional casi siempre es un
concepto de bodega o técnico, y luego Analista Financiera → Analista Contable
→ Cartera. Lo que fallaba era pedirlos a mano: el orden, a quién, y volver a
pedir el que se mandó mal.

**Cómo funciona:**

1. Una **plantilla** (`PQRSFlujo`) por tipo de canal, editable en
   Administración. Sus pasos son de tres clases: un concepto fijo, el
   concepto de la **bodega** de donde salió el producto (Logística para el CD
   y La 65, Producción para Guayabal) y el concepto **técnico** de la causa
   («Asociado a» → Área Técnica, Logística…).
2. Servicio al Cliente ve la **propuesta** ya resuelta para esa PQRS, quita o
   agrega pasos y la **inicia**: se copia a la cadena de la PQRS y se pide el
   primer concepto.
3. **Al aprobarse un concepto, se pide el siguiente solo**, y el caso pasa
   directo a la siguiente área sin volver a Servicio al Cliente en cada paso.
4. **Al rechazarse o devolverse, el flujo se DETIENE** y el caso vuelve a
   quien reparte, que decide: volver a pedir ese concepto, seguir con el
   siguiente, cambiar los pasos o terminar.
5. Al aprobarse el último, el caso vuelve a quien reparte para resolverlo.

La cadena se copia al iniciar: cambiar la plantilla después no le mueve los
pasos a las PQRS que ya van en camino.
"""
import unicodedata

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core import canales
from app.models.autorizacion import AutorizacionPQRS, TipoAutorizacion
from app.models.pqrs import (
    PQRSBodegaDespacho, PQRSCadenaPaso, PQRSFlujo, PQRSFlujoPaso,
    PQRSSeguimiento, PQRSSolicitud,
)
from app.modules.autorizaciones.service import registrar_solicitud
from app.modules.pqrs import asociados

ESTADO_POR_DECISION = {"aprobada": "aprobado", "rechazada": "rechazado", "devuelta": "devuelto"}
TERMINADOS = ("aprobado", "rechazado", "devuelto")
TIPOS_CANAL = ("sede", "institucional", "general")


def _clave(texto: str | None) -> str:
    sin = unicodedata.normalize("NFD", texto or "")
    return " ".join("".join(c for c in sin if unicodedata.category(c) != "Mn").lower().split())


def _buscar_tipo(tipos: list[TipoAutorizacion], *palabras: str) -> TipoAutorizacion | None:
    """El tipo cuyo nombre trae todas esas palabras, sin tildes ni mayúsculas."""
    for t in tipos:
        if t.activo and all(p in _clave(t.nombre) for p in palabras):
            return t
    return None


# ── Siembra ────────────────────────────────────────────────────────────

def sembrar(db: Session, tenant_id: int) -> None:
    """
    El arranque, la primera vez: las bodegas de despacho, las dos plantillas
    que salieron del análisis y el concepto técnico de cada causa. Busca los
    tipos de autorización por su nombre; el que no exista simplemente no se
    pone, y se completa en Administración. Idempotente.
    """
    if db.query(PQRSFlujo.id).filter(PQRSFlujo.tenant_id == tenant_id).first():
        return
    tipos = db.query(TipoAutorizacion).filter(TipoAutorizacion.tenant_id == tenant_id).all()
    logistica = _buscar_tipo(tipos, "coordinacion logistica")
    produccion = _buscar_tipo(tipos, "produccion")
    tecnica = _buscar_tipo(tipos, "area tecnica protokimica") or _buscar_tipo(tipos, "area tecnica")
    financiera = _buscar_tipo(tipos, "analista financiera")
    contable = _buscar_tipo(tipos, "analista contable")
    cartera = _buscar_tipo(tipos, "cartera")

    if not db.query(PQRSBodegaDespacho.id).filter(PQRSBodegaDespacho.tenant_id == tenant_id).first():
        for orden, (nombre, tipo) in enumerate([("CD", logistica), ("La 65", logistica), ("Guayabal", produccion)]):
            db.add(PQRSBodegaDespacho(tenant_id=tenant_id, nombre=nombre, orden=orden,
                                      tipo_autorizacion_id=tipo.id if tipo else None))

    def plantilla(nombre, aplica_a, fijos):
        flujo = PQRSFlujo(tenant_id=tenant_id, nombre=nombre, aplica_a=aplica_a)
        pasos = [("bodega", None), ("tecnico", None)] + [("concepto", t) for t in fijos if t]
        flujo.pasos = [PQRSFlujoPaso(orden=i, clase=c, tipo_autorizacion_id=t.id if t else None)
                       for i, (c, t) in enumerate(pasos)]
        db.add(flujo)

    plantilla("Venta institucional", "institucional", [financiera, contable, cartera])
    plantilla("Punto de venta", "sede", [financiera])

    # El concepto técnico de cada causa: lo que tiene que ver el producto, al
    # Área Técnica; lo que tiene que ver con la entrega del CEDI, a Logística.
    for a in asociados.del_tenant(db, tenant_id, incluir_inactivos=True):
        if a.concepto_tecnico_id:
            continue
        if a.grupo == "Producto y empaque" and tecnica:
            a.concepto_tecnico_id = tecnica.id
        elif a.codigo in ("DE", "TR") or a.nombre == "Mala Entrega (CEDI)":
            if logistica:
                a.concepto_tecnico_id = logistica.id
    db.commit()


# ── La propuesta para una PQRS ─────────────────────────────────────────

def tipo_de_canal(db: Session, pqrs: PQRSSolicitud) -> str | None:
    """`sede`, `institucional` o `general`: por el canal, o por el prefijo del radicado."""
    todos = canales.del_tenant(db, pqrs.tenant_id, incluir_inactivos=True)
    for c in todos:
        if c.nombre == pqrs.canal_atencion:
            return c.tipo
    codigo = pqrs.codigo_seguimiento or ""
    for c in sorted((c for c in todos if c.prefijo), key=lambda c: -len(c.prefijo)):
        resto = codigo[len(c.prefijo):]
        if codigo.startswith(c.prefijo) and resto.isdigit():
            return c.tipo
    return None


def plantilla_para(db: Session, pqrs: PQRSSolicitud) -> PQRSFlujo | None:
    """La plantilla de su tipo de canal; si no hay, la que sirve para cualquiera."""
    sembrar(db, pqrs.tenant_id)
    activas = db.query(PQRSFlujo).filter(
        PQRSFlujo.tenant_id == pqrs.tenant_id, PQRSFlujo.activo.is_(True),
    ).order_by(PQRSFlujo.id).all()
    canal = tipo_de_canal(db, pqrs)
    return (next((f for f in activas if canal and f.aplica_a == canal), None)
            or next((f for f in activas if f.aplica_a is None), None))


def propuesta(db: Session, pqrs: PQRSSolicitud) -> dict:
    """
    La plantilla resuelta para ESTA PQRS: cada paso con su concepto concreto,
    o con lo que falta para saberlo (la bodega, la causa). Un concepto que ya
    salió por otro paso no se repite: una mala entrega del CD pediría a
    Logística por la bodega y por la causa.
    """
    flujo = plantilla_para(db, pqrs)
    pasos, faltan, vistos = [], [], set()
    if not flujo:
        return {"flujo": None, "pasos": [], "faltan": []}

    def agregar(origen, tipo):
        if tipo and tipo.activo and tipo.id not in vistos:
            vistos.add(tipo.id)
            pasos.append({"origen": origen, "tipo_autorizacion_id": tipo.id,
                          "concepto": tipo.nombre, "area": tipo.area_autorizadora})

    for paso in flujo.pasos:
        if paso.clase == "concepto":
            agregar("concepto", db.get(TipoAutorizacion, paso.tipo_autorizacion_id) if paso.tipo_autorizacion_id else None)
        elif paso.clase == "bodega":
            bodega = pqrs.bodega_despacho
            if not bodega:
                faltan.append({"clase": "bodega", "mensaje": "Elige la bodega de despacho para saber si va a Logística o a Producción."})
            elif bodega.tipo_autorizacion_id:
                agregar("bodega", db.get(TipoAutorizacion, bodega.tipo_autorizacion_id))
        elif paso.clase == "tecnico":
            asociado = pqrs.asociado
            if not asociado:
                faltan.append({"clase": "tecnico", "mensaje": "Marca la causa («Asociado a») para saber qué concepto técnico pedir."})
            elif asociado.concepto_tecnico_id:
                agregar("tecnico", db.get(TipoAutorizacion, asociado.concepto_tecnico_id))
    return {"flujo": {"id": flujo.id, "nombre": flujo.nombre}, "pasos": pasos, "faltan": faltan}


# ── La cadena de una PQRS ──────────────────────────────────────────────

def estado_cadena(pqrs: PQRSSolicitud) -> str:
    """
    sin_flujo: nunca se inició.  en_curso: hay un concepto esperando.
    detenida: el último se rechazó o se devolvió.  lista: quedan pasos y
    nadie los está esperando (se editó).  completa: no queda nada.
    """
    pasos = pqrs.cadena
    if not pasos:
        return "sin_flujo"
    if any(p.estado == "en_curso" for p in pasos):
        return "en_curso"
    terminados = [p for p in pasos if p.estado in TERMINADOS]
    if terminados and terminados[-1].estado in ("rechazado", "devuelto"):
        return "detenida"
    if any(p.estado == "pendiente" for p in pasos):
        return "lista"
    return "completa"


def _tipos_validos(db: Session, tenant_id: int, ids: list[int]) -> list[TipoAutorizacion]:
    tipos = []
    for i in ids:
        tipo = db.query(TipoAutorizacion).filter(
            TipoAutorizacion.id == i, TipoAutorizacion.tenant_id == tenant_id,
        ).first()
        if not tipo or not tipo.activo:
            raise HTTPException(status_code=400, detail="Uno de los conceptos no existe o está desactivado. Elígelo otra vez de la lista.")
        tipos.append(tipo)
    return tipos


def _renumerar(pqrs: PQRSSolicitud, nuevos_pendientes: list[PQRSCadenaPaso]) -> None:
    """Lo ya pedido queda como está; los pendientes van después, en el orden dado."""
    hechos = [p for p in pqrs.cadena if p.estado != "pendiente"]
    for i, p in enumerate(sorted(hechos, key=lambda p: p.orden) + nuevos_pendientes):
        p.orden = i


def _nota(db: Session, pqrs: PQRSSolicitud, texto: str, usuario_id: int | None) -> None:
    db.add(PQRSSeguimiento(pqrs_id=pqrs.id, usuario_id=usuario_id, tipo_evento="flujo", comentario=texto))


def _exigir_abierta(pqrs: PQRSSolicitud) -> None:
    if pqrs.estado == "cerrado":
        raise HTTPException(status_code=400, detail="La PQRS está cerrada: su flujo ya no se mueve.")


def pedir_siguiente(db: Session, pqrs: PQRSSolicitud, usuario_id: int) -> tuple[PQRSCadenaPaso, AutorizacionPQRS] | None:
    """Pide el primer paso pendiente. None si ya no queda ninguno."""
    pendientes = [p for p in pqrs.cadena if p.estado == "pendiente"]
    if not pendientes:
        return None
    paso = min(pendientes, key=lambda p: p.orden)
    numero = sorted(pqrs.cadena, key=lambda p: p.orden).index(paso) + 1
    autorizacion = registrar_solicitud(
        db, pqrs, paso.tipo, paso.creado_por or usuario_id,
        nota_flujo=f"Paso {numero} de {len(pqrs.cadena)} del flujo.",
    )
    paso.estado = "en_curso"
    paso.autorizacion_id = autorizacion.id
    return paso, autorizacion


def iniciar(db: Session, pqrs: PQRSSolicitud, usuario_id: int, pasos: list[dict],
            bodega_despacho_id: int | None = None) -> tuple[PQRSCadenaPaso, AutorizacionPQRS]:
    """
    Copia los pasos elegidos a la cadena de la PQRS y pide el primero. Si ya
    tuvo un flujo que terminó o se detuvo, los nuevos se agregan después: el
    historial de lo ya pedido no se toca.
    """
    _exigir_abierta(pqrs)
    if estado_cadena(pqrs) == "en_curso":
        raise HTTPException(status_code=409, detail="Ya hay un concepto en curso. Espera su respuesta o edita los pasos que faltan.")
    if db.query(AutorizacionPQRS.id).filter(
        AutorizacionPQRS.pqrs_id == pqrs.id, AutorizacionPQRS.estado == "pendiente",
    ).first():
        raise HTTPException(status_code=409, detail="Hay una autorización pendiente pedida a mano. Espera su respuesta antes de iniciar el flujo.")
    if not pasos:
        raise HTTPException(status_code=400, detail="El flujo no tiene pasos. Agrega al menos un concepto.")

    if bodega_despacho_id is not None:
        elegir_bodega(db, pqrs, bodega_despacho_id)

    tipos = _tipos_validos(db, pqrs.tenant_id, [p["tipo_autorizacion_id"] for p in pasos])
    # Los pendientes de un flujo anterior se reemplazan por los nuevos.
    for p in [p for p in pqrs.cadena if p.estado == "pendiente"]:
        pqrs.cadena.remove(p)
    nuevos = [
        PQRSCadenaPaso(tipo_autorizacion_id=t.id, tipo=t, origen=p.get("origen") or "agregado",
                       estado="pendiente", creado_por=usuario_id)
        for t, p in zip(tipos, pasos)
    ]
    pqrs.cadena.extend(nuevos)
    _renumerar(pqrs, nuevos)
    _nota(db, pqrs, "Se inició el flujo: " + " -> ".join(t.nombre for t in tipos) + ".", usuario_id)
    db.flush()
    return pedir_siguiente(db, pqrs, usuario_id)


def editar_pendientes(db: Session, pqrs: PQRSSolicitud, usuario_id: int, pasos: list[dict]) -> None:
    """Cambia los pasos que faltan: quitar, agregar, reordenar. Lo ya pedido no se toca."""
    _exigir_abierta(pqrs)
    if not pqrs.cadena:
        raise HTTPException(status_code=400, detail="Esta PQRS no tiene flujo. Inícialo primero.")
    tipos = _tipos_validos(db, pqrs.tenant_id, [p["tipo_autorizacion_id"] for p in pasos])
    viejos = {p.id: p for p in pqrs.cadena if p.estado == "pendiente"}
    nuevos = []
    for t, p in zip(tipos, pasos):
        existente = viejos.pop(p.get("id"), None) if p.get("id") else None
        if existente and existente.tipo_autorizacion_id == t.id:
            nuevos.append(existente)
        else:
            paso = PQRSCadenaPaso(tipo_autorizacion_id=t.id, tipo=t, origen=p.get("origen") or "agregado",
                                  estado="pendiente", creado_por=usuario_id)
            pqrs.cadena.append(paso)
            nuevos.append(paso)
    for sobrante in viejos.values():
        pqrs.cadena.remove(sobrante)
    _renumerar(pqrs, nuevos)
    _nota(db, pqrs, "Pasos que faltan: " + (" -> ".join(t.nombre for t in tipos) or "ninguno") + ".", usuario_id)
    db.flush()


def reanudar(db: Session, pqrs: PQRSSolicitud, usuario_id: int, repetir: bool = False):
    """
    Después de un rechazo o una devolución: volver a pedir ese mismo concepto
    (`repetir`), o seguir con el siguiente pendiente.
    """
    _exigir_abierta(pqrs)
    estado = estado_cadena(pqrs)
    if estado == "en_curso":
        raise HTTPException(status_code=409, detail="Ya hay un concepto en curso: no hay nada que reanudar.")
    if estado in ("sin_flujo", "completa") and not repetir:
        raise HTTPException(status_code=400, detail="No quedan pasos. Agrega uno o da el flujo por terminado.")
    if repetir:
        ultimo = max((p for p in pqrs.cadena if p.estado in ("rechazado", "devuelto")), key=lambda p: p.orden, default=None)
        if not ultimo:
            raise HTTPException(status_code=400, detail="No hay un concepto rechazado o devuelto para volver a pedir.")
        pendientes = sorted((p for p in pqrs.cadena if p.estado == "pendiente"), key=lambda p: p.orden)
        otra_vez = PQRSCadenaPaso(tipo_autorizacion_id=ultimo.tipo_autorizacion_id, tipo=ultimo.tipo,
                                  origen=ultimo.origen, estado="pendiente", creado_por=usuario_id)
        pqrs.cadena.append(otra_vez)
        _renumerar(pqrs, [otra_vez] + pendientes)
    db.flush()
    return pedir_siguiente(db, pqrs, usuario_id)


def terminar(db: Session, pqrs: PQRSSolicitud, usuario_id: int) -> None:
    """Quita lo que faltaba. Lo ya pedido queda en la cadena como constancia."""
    if estado_cadena(pqrs) == "en_curso":
        raise HTTPException(status_code=409, detail="Hay un concepto en curso. Espera su respuesta antes de terminar el flujo.")
    for p in [p for p in pqrs.cadena if p.estado == "pendiente"]:
        pqrs.cadena.remove(p)
    _nota(db, pqrs, "Se dio por terminado el flujo.", usuario_id)
    db.flush()


def elegir_bodega(db: Session, pqrs: PQRSSolicitud, bodega_id: int | None) -> None:
    if bodega_id is None:
        pqrs.bodega_despacho_id = None
        return
    bodega = db.query(PQRSBodegaDespacho).filter(
        PQRSBodegaDespacho.id == bodega_id, PQRSBodegaDespacho.tenant_id == pqrs.tenant_id,
    ).first()
    if not bodega:
        raise HTTPException(status_code=404, detail="Esa bodega no existe. Elígela de la lista.")
    if pqrs.bodega_despacho_id != bodega.id:
        anterior = pqrs.bodega_despacho.nombre if pqrs.bodega_despacho else "sin definir"
        pqrs.bodega_despacho_id = bodega.id
        pqrs.bodega_despacho = bodega
        _nota(db, pqrs, f"Bodega de despacho: {anterior} -> {bodega.nombre}.", None)


# ── Lo que pasa al pedir y al responder una autorización ───────────────

def al_pedir_a_mano(db: Session, pqrs: PQRSSolicitud, autorizacion: AutorizacionPQRS, usuario_id: int) -> None:
    """
    Una autorización pedida a mano con un flujo andando entra a la cadena,
    antes de los pendientes: si no, al responderla el flujo no se enteraría y
    no pediría el siguiente.
    """
    if not pqrs.cadena:
        return
    pendientes = sorted((p for p in pqrs.cadena if p.estado == "pendiente"), key=lambda p: p.orden)
    paso = PQRSCadenaPaso(tipo_autorizacion_id=autorizacion.tipo_id, origen="agregado", estado="en_curso",
                          autorizacion_id=autorizacion.id, creado_por=usuario_id)
    paso.tipo = db.get(TipoAutorizacion, autorizacion.tipo_id)
    # Va después de lo ya pedido y antes de lo que falta.
    paso.orden = 10 ** 6
    pqrs.cadena.append(paso)
    _renumerar(pqrs, pendientes)
    db.flush()


def registrar_respuesta(db: Session, pqrs: PQRSSolicitud, autorizacion: AutorizacionPQRS, decision: str) -> dict:
    """
    Marca el paso de esta autorización y dice qué sigue, SIN pedirlo todavía:
    quien responde deja primero su renglón en el historial y después se pide
    el siguiente, para que el historial se lea en el orden en que pasó.

    Devuelve `{"en_flujo", "sigue", "estado"}`: `sigue` es el paso que hay que
    pedir (solo si se aprobó y queda alguno).
    """
    paso = next((p for p in pqrs.cadena if p.autorizacion_id == autorizacion.id), None)
    if not paso:
        return {"en_flujo": False, "sigue": None, "estado": None}
    paso.estado = ESTADO_POR_DECISION.get(decision, paso.estado)
    sigue = None
    if paso.estado == "aprobado":
        pendientes = [p for p in pqrs.cadena if p.estado == "pendiente"]
        sigue = min(pendientes, key=lambda p: p.orden) if pendientes else None
    db.flush()
    return {"en_flujo": True, "sigue": sigue, "estado": estado_cadena(pqrs)}


# ── Lo que ve la pantalla ──────────────────────────────────────────────

def resumen(db: Session, pqrs: PQRSSolicitud, puede_gestionar: bool) -> dict:
    estado = estado_cadena(pqrs)
    autorizaciones = {a.id: a for a in db.query(AutorizacionPQRS).filter(AutorizacionPQRS.pqrs_id == pqrs.id)}
    pasos = []
    for p in sorted(pqrs.cadena, key=lambda p: p.orden):
        aut = autorizaciones.get(p.autorizacion_id)
        pasos.append({
            "id": p.id, "orden": p.orden, "origen": p.origen, "estado": p.estado,
            "tipo_autorizacion_id": p.tipo_autorizacion_id,
            "concepto": p.tipo.nombre if p.tipo else None,
            "area": p.tipo.area_autorizadora if p.tipo else None,
            "autorizacion_id": p.autorizacion_id,
            "respondida_en": aut.fecha_respuesta if aut else None,
            "respondida_por": aut.autorizador_nombre if aut else None,
        })
    sembrar(db, pqrs.tenant_id)
    bodegas = db.query(PQRSBodegaDespacho).filter(
        PQRSBodegaDespacho.tenant_id == pqrs.tenant_id, PQRSBodegaDespacho.activo.is_(True),
    ).order_by(PQRSBodegaDespacho.orden, PQRSBodegaDespacho.nombre).all()
    return {
        "estado": estado,
        "pasos": pasos,
        # La propuesta solo hace falta cuando no hay nada andando.
        "propuesta": propuesta(db, pqrs) if estado in ("sin_flujo", "completa") else None,
        "bodega_despacho_id": pqrs.bodega_despacho_id,
        "bodegas": [{"id": b.id, "nombre": b.nombre} for b in bodegas],
        "puede_gestionar": puede_gestionar and pqrs.estado != "cerrado",
    }

