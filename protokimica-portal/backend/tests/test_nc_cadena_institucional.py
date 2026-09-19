"""
La cadena de una nota crédito de Ventas Institucionales.

Un punto de venta pide y Contabilidad autoriza: eso es un trámite entre dos.
Una venta institucional es otra cosa — hay producto que vuelve a una bodega,
una decisión comercial sobre si la devolución procede, y una verificación
ante la DIAN de si la factura tiene saldo a favor. Son cuatro manos, y el
orden importa: aprobar comercialmente algo que la bodega todavía no ha visto
es firmar sin mirar.

Lo que se defiende aquí:

- **el orden lo impone el servidor**, no la buena memoria de la gente: un
  endpoint único responde según la etapa en la que está la solicitud, así que
  no hay URL que se pueda escribir para saltarse un paso;
- **la bodega la atiende quien responde por ella** — Guayabal no confirma lo
  que entró a La 65, igual que Belén no atiende las PQRS de Guayabal;
- **devolver no es rechazar**: la solicitud sigue viva, en manos de quien la
  pidió, y al reenviarla vuelve al principio — arrastrar la firma de quien ya
  había aprobado sería darla por buena sobre unos datos que cambiaron;
- **sin producto no hay bodega**, y la rama del punto de venta no se movió.
"""
from app.core.capacidades import otorgar_a_area
from app.models.nota_credito import MotivoNotaCredito, SolicitudNotaCredito
from app.models.user import User
from app.modules.notas_credito import flujo

INSTITUCIONAL = "Venta institucional"
PUNTO = "Punto de venta Itagüí"
GUAYABAL = "Guayabal"
LA_65 = "La 65"


# ── Montaje ──────────────────────────────────────────────────────────────

def _capacidad(entorno, capacidad, area):
    db = entorno.Session()
    otorgar_a_area(db, entorno.tenant_id, capacidad, area, entorno.ids["admin"])
    db.close()


def _montar_la_cadena(entorno):
    """Deja el portal como queda tras la migración: cada área con lo suyo."""
    _capacidad(entorno, "notas_credito.confirmar_producto", "Logística")
    _capacidad(entorno, "notas_credito.confirmar_producto", "Producción")
    _capacidad(entorno, "notas_credito.aprobar_comercial", "Comercial")
    _capacidad(entorno, "notas_credito.verificar_dian", "Contabilidad")
    _capacidad(entorno, "notas_credito.registrar", "Contabilidad")


def _usuario(entorno, clave, area, bodega=None, rol="lider"):
    db = entorno.Session()
    u = User(tenant_id=entorno.tenant_id, nombre=clave.title(), email=f"{clave}@p.com",
             password_hash="x", rol=rol, area=area, bodega=bodega, activo=True)
    db.add(u)
    db.commit()
    entorno.ids[clave] = u.id
    db.close()
    return entorno.ids[clave]


def _motivo(entorno, nombre, con_producto):
    db = entorno.Session()
    m = MotivoNotaCredito(tenant_id=entorno.tenant_id, nombre=nombre,
                          activo=True, requiere_bodega=con_producto)
    db.add(m)
    db.commit()
    mid = m.id
    db.close()
    return mid


def _radicar(entorno, punto=INSTITUCIONAL, motivo_id=None, bodega=None):
    datos = {
        "punto_venta": punto,
        "factura_afectada": "FV-8801",
        "observaciones": "El cliente devolvió dos canecas que llegaron rotas.",
    }
    if motivo_id is not None:
        datos["motivo_id"] = motivo_id
    if bodega is not None:
        datos["bodega"] = bodega
    return entorno.post("/notas-credito", data=datos)


def _estado(entorno, sid):
    db = entorno.Session()
    estado = db.get(SolicitudNotaCredito, sid).estado
    db.close()
    return estado


def _responder(entorno, sid, decision, comentario=None):
    cuerpo = {"decision": decision}
    if comentario:
        cuerpo["comentario"] = comentario
    return entorno.post(f"/notas-credito/{sid}/responder", json=cuerpo)


def _escenario(entorno, con_producto=True, bodega=GUAYABAL):
    """Una institucional recién radicada, con toda la gente montada."""
    _montar_la_cadena(entorno)
    _usuario(entorno, "opera", "Producción", bodega=GUAYABAL)
    _usuario(entorno, "logis65", "Logística", bodega=LA_65)
    _usuario(entorno, "comercial", "Comercial")
    _usuario(entorno, "conta", "Contabilidad")
    _usuario(entorno, "vendedor", "Ventas Institucionales", rol="agente")

    motivo_id = _motivo(entorno, "Devolución de mercancía", con_producto)
    entorno.como("vendedor")
    r = _radicar(entorno, motivo_id=motivo_id, bodega=bodega if con_producto else None)
    assert r.status_code == 201, r.text[:300]
    return r.json()["id"]


# ── Por dónde entra cada una ─────────────────────────────────────────────

def test_con_producto_empieza_en_la_bodega(entorno, v):
    sid = _escenario(entorno)
    v.check("nace esperando a la bodega", _estado(entorno, sid) == "en_bodega",
            _estado(entorno, sid))


def test_sin_producto_se_salta_la_bodega(entorno, v):
    """Pedir que confirmen un producto que no existe es una firma que no mira nada."""
    sid = _escenario(entorno, con_producto=False)
    v.check("arranca en Comercial", _estado(entorno, sid) == "en_comercial",
            _estado(entorno, sid))


def test_un_punto_de_venta_tambien_empieza_por_comercial(entorno, v):
    """
    Lo que NO cambió de la rama del mostrador: no se le pide bodega aunque
    el motivo implique producto —el cliente lo devuelve en el mismo almacén,
    no hay nada que esperar a que llegue—.

    Lo que SÍ cambió: ya no entra directo a Contabilidad. Quien decide si se
    devuelve la plata es Comercial, venga la venta de un mostrador o de una
    institución; antes Contabilidad terminaba decidiendo eso sola.
    """
    _montar_la_cadena(entorno)
    _capacidad(entorno, "notas_credito.autorizar", "Contabilidad")
    motivo_id = _motivo(entorno, "Devolución de mercancía", True)

    entorno.como("logistica")
    r = _radicar(entorno, punto=PUNTO, motivo_id=motivo_id)
    v.check("se radica sin pedir bodega", r.status_code == 201, r.text[:300])
    v.check("y queda esperando a Comercial",
            r.json()["estado"] == "en_comercial", r.json()["estado"])
    v.check("sin bodega", r.json()["bodega"] is None, r.json())


def test_con_producto_hay_que_decir_a_que_bodega(entorno, v):
    _montar_la_cadena(entorno)
    _usuario(entorno, "vendedor", "Ventas Institucionales", rol="agente")
    motivo_id = _motivo(entorno, "Devolución de mercancía", True)

    entorno.como("vendedor")
    r = _radicar(entorno, motivo_id=motivo_id)
    v.check("no deja radicar sin bodega", r.status_code == 400, r.status_code)
    v.check("y dice por qué", "bodega" in r.json()["detail"].lower(), r.json())

    r = _radicar(entorno, motivo_id=motivo_id, bodega="Sabaneta")
    v.check("una bodega inventada tampoco", r.status_code == 400, r.status_code)


# ── El orden lo impone el servidor ───────────────────────────────────────

def test_comercial_no_puede_adelantarse_a_la_bodega(entorno, v):
    """
    El caso que justifica que sea UN endpoint y no uno por etapa: no hay URL
    que escribir para saltarse un paso.
    """
    sid = _escenario(entorno)
    entorno.como("comercial")
    r = _responder(entorno, sid, "aprobar")
    v.check("no es su turno", r.status_code == 403, r.status_code)
    v.check("sigue en la bodega", _estado(entorno, sid) == "en_bodega", _estado(entorno, sid))


def test_la_cadena_completa_de_punta_a_punta(entorno, v):
    sid = _escenario(entorno)

    entorno.como("opera")
    v.check("la bodega confirma", _responder(entorno, sid, "aprobar").status_code == 200)
    v.check("pasa a Comercial", _estado(entorno, sid) == "en_comercial", _estado(entorno, sid))

    entorno.como("comercial")
    v.check("Comercial aprueba", _responder(entorno, sid, "aprobar").status_code == 200)
    v.check("pasa a la DIAN", _estado(entorno, sid) == "en_contabilidad", _estado(entorno, sid))

    entorno.como("conta")
    v.check("Contabilidad verifica", _responder(entorno, sid, "aprobar").status_code == 200)
    v.check("queda lista para emitir", _estado(entorno, sid) == "aprobada", _estado(entorno, sid))

    r = entorno.post(f"/notas-credito/{sid}/aplicar", json={"numero_nc": "NC-991"})
    v.check("y se cierra con su número", r.status_code == 200, r.text[:200])
    v.check("aplicada", _estado(entorno, sid) == "aplicada", _estado(entorno, sid))

    detalle = entorno.get(f"/notas-credito/{sid}").json()
    acciones = [h["accion"] for h in detalle["historial"]]
    v.check("el historial guarda las cuatro manos y la radicación",
            acciones == ["creada", "aprobar", "aprobar", "aprobar", "aplicada"], acciones)
    etapas = [h["etapa"] for h in detalle["historial"]]
    v.check("cada una en su etapa",
            etapas == ["en_bodega", "en_bodega", "en_comercial", "en_contabilidad", "aprobada"],
            etapas)


# ── Cada bodega atiende la suya ──────────────────────────────────────────

def test_la_otra_bodega_no_confirma_lo_ajeno(entorno, v):
    """
    Responde 404 y no 403, como todo lo que queda fuera de alcance en este
    portal: un 403 confirmaría que esa solicitud existe.
    """
    sid = _escenario(entorno, bodega=GUAYABAL)
    entorno.como("logis65")
    r = _responder(entorno, sid, "aprobar")
    v.check("La 65 no confirma lo de Guayabal", r.status_code == 404, r.status_code)
    v.check("y sigue en la bodega que era",
            _estado(entorno, sid) == "en_bodega", _estado(entorno, sid))


def test_quien_no_tiene_bodega_marcada_responde_por_las_dos(entorno, v):
    """El coordinador que cubre las dos: sin esto tendría que inventarse una."""
    sid = _escenario(entorno, bodega=LA_65)
    _usuario(entorno, "jefelog", "Logística")   # sin bodega
    entorno.como("jefelog")
    v.check("puede confirmar", _responder(entorno, sid, "aprobar").status_code == 200)


def test_la_bodega_ajena_ni_siquiera_la_ve(entorno, v):
    """Fuera de alcance responde 404, no 403: un 403 confirma que existe."""
    sid = _escenario(entorno, bodega=GUAYABAL)
    entorno.como("logis65")
    v.check("no la encuentra", entorno.get(f"/notas-credito/{sid}").status_code == 404)

    entorno.como("opera")
    v.check("la suya sí", entorno.get(f"/notas-credito/{sid}").status_code == 200)


def test_comercial_ve_las_dos_ramas_porque_abre_las_dos(entorno, v):
    """
    Antes Comercial solo veía las institucionales, que eran las únicas que
    tocaba. Desde que TODA nota crédito empieza por su aprobación, esconderle
    las del mostrador dejaría su primer turno sin nadie que lo pueda
    atender: no aparecerían en su lista y al abrirlas por id responderían 404.

    La bodega y la verificación ante la DIAN siguen viendo solo las
    institucionales — esas dos sí son pasos que las del mostrador no tienen.
    """
    _montar_la_cadena(entorno)
    _capacidad(entorno, "notas_credito.autorizar", "Contabilidad")
    _usuario(entorno, "comercial", "Comercial")
    _usuario(entorno, "vendedor", "Ventas Institucionales", rol="agente")

    entorno.como("logistica")
    del_punto = _radicar(entorno, punto=PUNTO).json()["id"]
    entorno.como("vendedor")
    institucional = _radicar(entorno).json()["id"]

    entorno.como("comercial")
    vistas = {s["id"] for s in entorno.get("/notas-credito").json()}
    v.check("ve la institucional", institucional in vistas, vistas)
    v.check("y también la del punto de venta", del_punto in vistas, vistas)
    v.check("y puede abrirla, no solo verla en la lista",
            entorno.get(f"/notas-credito/{del_punto}").status_code == 200)


# ── Devolver no es rechazar ──────────────────────────────────────────────

def test_devolver_la_deja_viva_en_manos_del_vendedor(entorno, v):
    sid = _escenario(entorno)
    entorno.como("opera")
    r = _responder(entorno, sid, "devolver", "Llegó una caneca, no dos. Revisa la cantidad.")
    v.check("se devuelve", r.status_code == 200, r.text[:200])
    v.check("queda devuelta", _estado(entorno, sid) == "devuelta", _estado(entorno, sid))

    entorno.como("vendedor")
    alcance = entorno.get(f"/notas-credito/{sid}").json()["alcance"]
    v.check("y él puede corregirla", alcance["puede_reenviar"] is True, alcance)


def test_devolver_sin_decir_qué_corregir_no_pasa(entorno, v):
    """Una devolución muda obliga a una llamada: justo el ir y venir que sobra."""
    sid = _escenario(entorno)
    entorno.como("opera")
    r = _responder(entorno, sid, "devolver")
    v.check("lo rechaza el servidor", r.status_code == 400, r.status_code)


def test_al_reenviarla_vuelve_al_principio(entorno, v):
    """
    Quien ya aprobó lo hizo sobre unos datos que cambiaron. Arrastrar esa
    firma sería darla por buena sin que nadie la vuelva a mirar.

    Se manda el cuerpo **vacío**, que es exactamente lo que manda la pantalla.
    No es un detalle: reenviar y cancelar reusaban el schema de responder, que
    exige `decision`, así que el botón respondía 422 mientras esta prueba
    pasaba —porque mandaba un `decision` inventado que la pantalla no tenía
    por qué mandar—. El arreglo que depende de un parámetro hay que probarlo
    con el parámetro que de verdad viaja.
    """
    sid = _escenario(entorno)
    entorno.como("opera")
    _responder(entorno, sid, "aprobar")
    entorno.como("comercial")
    _responder(entorno, sid, "devolver", "Falta el soporte de la devolución.")

    entorno.como("vendedor")
    r = entorno.post(f"/notas-credito/{sid}/reenviar", json={})
    v.check("la reenvía", r.status_code == 200, r.text[:200])
    v.check("y vuelve a la bodega, no a Comercial",
            _estado(entorno, sid) == "en_bodega", _estado(entorno, sid))


def test_solo_quien_la_pidio_la_reenvia(entorno, v):
    sid = _escenario(entorno)
    entorno.como("opera")
    _responder(entorno, sid, "devolver", "Corrige la cantidad.")

    entorno.como("comercial")
    r = entorno.post(f"/notas-credito/{sid}/reenviar", json={})
    v.check("otro no puede", r.status_code in (403, 404), r.status_code)


def test_rechazar_la_cierra(entorno, v):
    sid = _escenario(entorno)
    entorno.como("opera")
    _responder(entorno, sid, "aprobar")
    entorno.como("comercial")
    v.check("Comercial la rechaza",
            _responder(entorno, sid, "rechazar", "No procede.").status_code == 200)
    v.check("queda rechazada", _estado(entorno, sid) == "rechazada", _estado(entorno, sid))

    entorno.como("conta")
    r = _responder(entorno, sid, "aprobar")
    v.check("y ya nadie la mueve", r.status_code == 400, r.status_code)


def test_el_vendedor_la_retira_y_eso_no_es_un_rechazo(entorno, v):
    """Una que el vendedor retira no es un caso que la empresa negó."""
    sid = _escenario(entorno)
    entorno.como("vendedor")
    r = entorno.post(f"/notas-credito/{sid}/cancelar", json={})
    v.check("la retira", r.status_code == 200, r.text[:200])
    v.check("queda cancelada, no rechazada",
            _estado(entorno, sid) == "cancelada", _estado(entorno, sid))


# ── Lo que la pantalla necesita saber ────────────────────────────────────

def test_el_detalle_dice_en_qué_paso_va_y_qué_sigue(entorno, v):
    """Lo redacta el servidor: «en_contabilidad» no es un texto para nadie."""
    sid = _escenario(entorno)
    entorno.como("opera")
    detalle = entorno.get(f"/notas-credito/{sid}").json()

    v.check("dice la etapa en palabras",
            "bodega" in (detalle["etapa_nombre"] or "").lower(), detalle["etapa_nombre"])
    v.check("dice qué hacer", bool(detalle["que_hacer"]), detalle)
    v.check("y quién sigue",
            "Comercial" in (detalle["etapa_siguiente"] or ""), detalle["etapa_siguiente"])
    v.check("es su turno", detalle["alcance"]["puede_responder"] is True, detalle["alcance"])


def test_mi_turno_trae_solo_lo_que_le_toca_a_cada_uno(entorno, v):
    sid = _escenario(entorno)
    entorno.como("comercial")
    v.check("Comercial no tiene nada todavía",
            entorno.get("/notas-credito?estado=mi_turno").json() == [], )

    entorno.como("opera")
    mias = [s["id"] for s in entorno.get("/notas-credito?estado=mi_turno").json()]
    v.check("la bodega sí", mias == [sid], mias)


# ── La cadena, sin pasar por la API ──────────────────────────────────────

def test_la_cadena_declara_los_pasos_de_cada_rama(v):
    v.check("punto de venta: comercial, autorizar y emitir",
            flujo.cadena(PUNTO) == ("en_comercial", "solicitada", "aprobada"),
            flujo.cadena(PUNTO))
    v.check("las dos ramas arrancan en Comercial",
            flujo.estado_inicial(PUNTO) == flujo.estado_inicial(INSTITUCIONAL) == "en_comercial",
            (flujo.estado_inicial(PUNTO), flujo.estado_inicial(INSTITUCIONAL)))
    v.check("institucional sin producto: comercial, DIAN y emitir",
            flujo.cadena(INSTITUCIONAL) == ("en_comercial", "en_contabilidad", "aprobada"),
            flujo.cadena(INSTITUCIONAL))
    v.check("con producto, la bodega va primero",
            flujo.cadena(INSTITUCIONAL, True)[0] == "en_bodega",
            flujo.cadena(INSTITUCIONAL, True))
    v.check("el último paso de la cadena no tiene siguiente",
            flujo.siguiente("aprobada", INSTITUCIONAL, True) is None)
    v.check("un estado ajeno a la cadena no inventa un paso",
            flujo.siguiente("rechazada", INSTITUCIONAL) is None)


def test_cada_turno_tiene_quien_lo_atienda(v):
    """
    Un turno sin capacidad es una solicitud parada para siempre, y nadie
    sabría por qué: no hay error, simplemente no aparece en la bandeja de
    nadie.
    """
    for rama in (flujo.cadena(PUNTO), flujo.cadena(INSTITUCIONAL, True)):
        for paso in rama:
            v.check(f"«{paso}» tiene capacidad", flujo.capacidad_de(paso) is not None, paso)
            v.check(f"«{paso}» se dice en palabras",
                    paso in flujo.ETIQUETA_ESTADO and paso in flujo.QUE_HACER, paso)
