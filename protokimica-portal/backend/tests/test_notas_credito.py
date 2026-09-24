"""
Solicitudes de nota crédito, contra la API real.

Lo que se defiende:
  - el consecutivo sale del MÁXIMO y no de un conteo;
  - el punto de venta es lista cerrada, porque de ahí sale el informe por
    almacén;
  - autoriza y registra quien tenga la CAPACIDAD (por defecto, el área de
    Contabilidad), no un cargo — primer módulo migrado al sistema de
    permisos por capacidad, ver `core/capacidades.py`;
  - el número de la nota crédito solo se registra sobre una ya aprobada —es
    lo que separa «aprobada» de «hecha»;
  - quien radica ve lo suyo y nada más.

**Estar en el área de Contabilidad ya NO basta por sí solo**: hace falta que
la capacidad esté otorgada. En producción eso lo garantizó la migración de
datos `d81f6a4c92e3` para los tenants que ya existían; aquí, cada prueba que
necesita un autorizador la otorga explícitamente con `_dar_capacidades_nc`
— es la versión de prueba de lo que esa migración hizo una sola vez.
"""
from app.core.capacidades import otorgar_a_area
from app.models.nota_credito import SolicitudNotaCredito
from app.models.user import User

AREA_CONTABILIDAD = "Contabilidad"
PUNTO = "Punto de venta Itagüí"


def _con_area(portal, clave, area):
    db = portal.Session()
    u = db.get(User, portal.ids[clave])
    u.area = area
    db.commit()
    db.close()


def _dar_capacidades_nc(portal, area=AREA_CONTABILIDAD):
    """Otorga las dos capacidades de notas crédito a un área, para pruebas."""
    db = portal.Session()
    otorgar_a_area(db, portal.tenant_id, "notas_credito.autorizar", area, portal.ids["admin"])
    otorgar_a_area(db, portal.tenant_id, "notas_credito.registrar", area, portal.ids["admin"])
    db.close()


def _dar_capacidad_comercial(portal, area):
    """La capacidad del primer turno: sin ella nadie puede mover nada."""
    db = portal.Session()
    otorgar_a_area(db, portal.tenant_id, "notas_credito.aprobar_comercial",
                   area, portal.ids["admin"])
    db.close()


def _pasar_comercial(portal, sid):
    """
    Aprueba el primer turno, el de Comercial.

    En una del MOSTRADOR eso la deja ya lista para emitir: Contabilidad no
    tiene turno ahí. TODA nota crédito empieza por Comercial, así que una
    prueba sobre lo que pasa después tiene que atravesar ese paso antes. Lo
    aprueba el admin, que puede en cualquier etapa: aquí el objetivo es
    llegar al turno siguiente, no probar el paso de Comercial
    —de eso se encarga test_toda_nota_credito_empieza_por_comercial—.

    Deja autenticado al admin: cada prueba dice con como() quién sigue.
    """
    portal.como("admin")
    r = portal.post(f"/notas-credito/{sid}/responder", json={"decision": "aprobar"})
    assert r.status_code == 200, r.text[:250]
    return r


def _radicar(portal, **extra):
    datos = {
        "punto_venta": PUNTO,
        "factura_afectada": "POS#141824",
        "observaciones": "El cliente pidió alcohol al 70% y se facturó otro.",
    }
    datos.update(extra)
    return portal.post("/notas-credito", data=datos)


# ── Radicar ──────────────────────────────────────────────────────────────

def test_radicar_deja_consecutivo_y_estado(entorno, v):
    portal = entorno
    portal.como("logistica")
    r = _radicar(portal)
    v.check("se radica", r.status_code == 201, r.text[:250])

    cuerpo = r.json()
    v.check("con consecutivo propio", (cuerpo["codigo"] or "").startswith("NC-"), cuerpo["codigo"])
    v.check("arranca esperando a Comercial", cuerpo["estado"] == "en_comercial", cuerpo["estado"])
    v.check("guarda quién la pidió", cuerpo["solicitante_nombre"] == "Logi", cuerpo)
    v.check("y de qué punto de venta", cuerpo["punto_venta"] == PUNTO, cuerpo)


def test_valor_y_soporte_son_opcionales(entorno, v):
    """No siempre se sabe el valor al pedirla, ni se tiene el soporte a la mano."""
    portal = entorno
    portal.como("logistica")
    r = _radicar(portal)
    v.check("se radica sin adjunto", r.status_code == 201, r.text[:200])
    v.check("y sin valor", r.json()["valor"] is None, r.json())
    v.check("adjunto vacío", r.json()["adjunto"] is None, r.json())


def test_el_consecutivo_sale_del_maximo(entorno, v):
    """
    Con un hueco en el medio, contar da un número que ya existe. Ese error ya
    mordió dos veces en este portal.
    """
    portal = entorno
    portal.como("logistica")
    primeros = [_radicar(portal).json()["codigo"] for _ in range(3)]

    db = portal.Session()
    delmedio = db.query(SolicitudNotaCredito).filter(
        SolicitudNotaCredito.codigo == primeros[1]
    ).first()
    db.delete(delmedio)
    db.commit()
    db.close()

    siguiente = _radicar(portal).json()["codigo"]
    v.check("no repite uno que ya existe", siguiente not in primeros, (primeros, siguiente))
    v.check("sigue después del mayor", siguiente.endswith("0004"), siguiente)


def test_el_punto_de_venta_es_lista_cerrada(entorno, v):
    """
    Escrito a mano, «Itagüí» y «Almacén Itagüí» son dos sitios distintos y el
    informe por almacén deja de servir.
    """
    portal = entorno
    portal.como("logistica")
    r = _radicar(portal, punto_venta="Almacen Itagui")
    v.check("no entra", r.status_code == 400, r.status_code)
    v.check("y dice que elija de la lista",
            "lista" in r.json().get("detail", "").lower(), r.json())


def test_sin_contar_que_paso_no_se_radica(entorno, v):
    portal = entorno
    portal.como("logistica")
    r = _radicar(portal, observaciones="   ")
    v.check("no entra", r.status_code == 400, r.status_code)
    v.check("y el mensaje dice para qué sirve",
            "Comercial" in r.json().get("detail", ""), r.json())


# ── Autorizar ────────────────────────────────────────────────────────────

def test_la_del_mostrador_la_decide_comercial_y_ya(entorno, v):
    """
    El recorrido completo de una del MOSTRADOR: Comercial aprueba y el punto
    la emite. Nadie más.

    Tuvo dos turnos de más, uno detrás del otro. Primero entraba directo a
    Contabilidad, y así era Contabilidad la que decidía un asunto comercial.
    Después pasó a Comercial **y** a Contabilidad, y entonces sobraba la
    segunda firma: la decisión ya estaba tomada, el punto emite contra su
    propia factura y ante la DIAN no hay nada que verificar. Dos manos para
    lo que decide una solo agregan la espera.
    """
    portal = entorno
    _con_area(portal, "tics", "Comercial")
    _dar_capacidad_comercial(portal, "Comercial")
    _con_area(portal, "calidad", AREA_CONTABILIDAD)
    _dar_capacidades_nc(portal)

    portal.como("logistica")
    sid = _radicar(portal).json()["id"]

    # Contabilidad no puede saltarse a Comercial: no es su turno.
    portal.como("calidad")
    r = portal.post(f"/notas-credito/{sid}/responder", json={"decision": "aprobar"})
    v.check("Contabilidad no se adelanta", r.status_code == 403, r.status_code)

    portal.como("tics")
    r = portal.post(f"/notas-credito/{sid}/responder", json={"decision": "aprobar"})
    v.check("Comercial aprueba", r.status_code == 200, r.text[:250])
    v.check("y con eso queda lista para emitir",
            r.json()["estado"] == "aprobada", r.json()["estado"])

    # Y ya no queda un turno de Contabilidad en el medio.
    portal.como("calidad")
    r = portal.post(f"/notas-credito/{sid}/responder", json={"decision": "aprobar"})
    v.check("Contabilidad ya no tiene nada que responder", r.status_code == 400, r.status_code)
    v.check("y el mensaje dice en qué estado está",
            "emitir" in r.json().get("detail", "").lower(), r.json())


def test_el_punto_de_venta_emite_apenas_comercial_aprueba(entorno, v):
    """
    Lo que se ganó: entre la decisión y la emisión no queda nadie esperando.
    """
    portal = entorno
    _con_area(portal, "calidad", AREA_CONTABILIDAD)
    _dar_capacidades_nc(portal)
    portal.como("logistica")
    sid = _radicar(portal).json()["id"]
    _pasar_comercial(portal, sid)

    portal.como("calidad")
    r = portal.post(f"/notas-credito/{sid}/aplicar", json={"numero_nc": "NC-9911"})
    v.check("se emite sin pasar por nadie más", r.status_code == 200, r.text[:250])
    v.check("y queda aplicada", r.json()["estado"] == "aplicada", r.json())


def test_solo_quien_tiene_la_capacidad_aprueba(entorno, v):
    portal = entorno
    _con_area(portal, "tics", "Comercial")
    _dar_capacidad_comercial(portal, "Comercial")

    portal.como("logistica")
    sid = _radicar(portal).json()["id"]

    portal.como("calidad")   # líder, pero de un área sin la capacidad
    r = portal.post(f"/notas-credito/{sid}/responder", json={"decision": "aprobar"})
    v.check("un líder de otra área no puede", r.status_code in (403, 404), r.status_code)

    portal.como("tics")
    r = portal.post(f"/notas-credito/{sid}/responder",
                    json={"decision": "aprobar", "comentario": "Va"})
    v.check("quien tiene la capacidad sí", r.status_code == 200, r.text[:250])
    v.check("queda aprobada", r.json()["estado"] == "aprobada", r.json())
    v.check("con quién firmó", r.json()["autorizador_nombre"] == "Tico", r.json())


def test_un_agente_del_area_tambien_aprueba(entorno, v):
    """Manda la capacidad del área, no el cargo: la analista no es líder."""
    portal = entorno
    _con_area(portal, "logistica", "Comercial")   # rol agente
    _dar_capacidad_comercial(portal, "Comercial")

    portal.como("tics")
    sid = _radicar(portal).json()["id"]

    portal.como("logistica")
    r = portal.post(f"/notas-credito/{sid}/responder", json={"decision": "aprobar"})
    v.check("el agente del área firma", r.status_code == 200, r.text[:250])


def test_no_se_responde_dos_veces(entorno, v):
    portal = entorno
    _con_area(portal, "calidad", "Comercial")
    _dar_capacidad_comercial(portal, "Comercial")
    portal.como("logistica")
    sid = _radicar(portal).json()["id"]

    portal.como("calidad")
    portal.post(f"/notas-credito/{sid}/responder", json={"decision": "rechazar"})
    r = portal.post(f"/notas-credito/{sid}/responder", json={"decision": "aprobar"})
    v.check("la segunda no pasa", r.status_code == 400, r.status_code)


# ── Cerrar el ciclo con el número de la NC ───────────────────────────────

def test_el_numero_de_la_nc_cierra_el_ciclo(entorno, v):
    portal = entorno
    _con_area(portal, "calidad", AREA_CONTABILIDAD)
    _dar_capacidades_nc(portal)
    portal.como("logistica")
    sid = _radicar(portal).json()["id"]
    _pasar_comercial(portal, sid)

    portal.como("calidad")
    r = portal.post(f"/notas-credito/{sid}/aplicar", json={"numero_nc": "NC-9911"})
    v.check("se registra", r.status_code == 200, r.text[:250])
    v.check("queda aplicada", r.json()["estado"] == "aplicada", r.json())
    v.check("con el número de la nota", r.json()["numero_nc"] == "NC-9911", r.json())
    v.check("y quién la hizo", r.json()["ejecutor_nombre"] == "Cali", r.json())


def test_no_se_aplica_lo_que_nadie_aprobo(entorno, v):
    """
    Anotar el número de una nota crédito que nadie autorizó es saltarse el
    control entero.
    """
    portal = entorno
    _con_area(portal, "calidad", AREA_CONTABILIDAD)
    _dar_capacidades_nc(portal)
    portal.como("logistica")
    sid = _radicar(portal).json()["id"]

    portal.como("calidad")
    r = portal.post(f"/notas-credito/{sid}/aplicar", json={"numero_nc": "NC-9911"})
    v.check("no deja, recién radicada", r.status_code == 400, r.status_code)
    # En palabras y no con el nombre de la columna: «en_comercial» no le dice
    # nada a quien está intentando registrar el número.
    v.check("y dice en qué estado está, en español",
            "Esperando a Coordinación Comercial" in r.json().get("detail", ""), r.json())

    # Tampoco a mitad de camino. En la rama institucional, que Comercial la
    # haya aprobado no la hace emitible: falta la verificación ante la DIAN,
    # y es justo donde queda a una sola firma de parecer lista.
    portal.como("logistica")
    otra = _radicar(portal, punto_venta="Venta institucional").json()["id"]
    _pasar_comercial(portal, otra)

    portal.como("calidad")
    r = portal.post(f"/notas-credito/{otra}/aplicar", json={"numero_nc": "NC-9912"})
    v.check("una institucional con Comercial aprobada todavía no",
            r.status_code == 400, r.status_code)
    v.check("y también dice dónde está",
            "Esperando a Contabilidad" in r.json().get("detail", ""), r.json())


# ── Quién ve qué ─────────────────────────────────────────────────────────

def test_quien_radica_ve_la_suya_y_nadie_mas_la_ajena(entorno, v):
    portal = entorno
    portal.como("logistica")
    sid = _radicar(portal).json()["id"]

    v.check("quien la pidió la ve",
            portal.get(f"/notas-credito/{sid}").status_code == 200)
    v.check("y aparece en su lista", len(portal.get("/notas-credito").json()) == 1)

    portal.como("tics")   # otra área, no autoriza
    v.check("otro no la ve -> 404",
            portal.get(f"/notas-credito/{sid}").status_code == 404)
    v.check("ni le aparece en la lista", portal.get("/notas-credito").json() == [])


def test_contabilidad_las_ve_todas(entorno, v):
    portal = entorno
    portal.como("logistica")
    _radicar(portal)
    portal.como("tics")
    _radicar(portal)

    _con_area(portal, "calidad", AREA_CONTABILIDAD)
    _dar_capacidades_nc(portal)
    portal.como("calidad")
    v.check("ve las dos", len(portal.get("/notas-credito").json()) == 2)


def test_el_alcance_dice_la_verdad(entorno, v):
    """El frontend no decide permisos: los pregunta."""
    portal = entorno
    _con_area(portal, "tics", "Comercial")
    _dar_capacidad_comercial(portal, "Comercial")
    _con_area(portal, "calidad", AREA_CONTABILIDAD)
    _dar_capacidades_nc(portal)
    portal.como("logistica")
    sid = _radicar(portal).json()["id"]

    alcance = portal.get(f"/notas-credito/{sid}").json()["alcance"]
    v.check("quien la pidió no la aprueba", alcance["puede_responder"] is False, alcance)

    portal.como("calidad")
    alcance = portal.get(f"/notas-credito/{sid}").json()["alcance"]
    v.check("Contabilidad tampoco: en el mostrador no es su turno",
            alcance["puede_responder"] is False, alcance)

    portal.como("tics")
    alcance = portal.get(f"/notas-credito/{sid}").json()["alcance"]
    v.check("Comercial sí", alcance["puede_responder"] is True, alcance)
    v.check("pero todavía no se registra el número",
            alcance["puede_aplicar"] is False, alcance)

    portal.post(f"/notas-credito/{sid}/responder", json={"decision": "aprobar"})
    portal.como("calidad")
    alcance = portal.get(f"/notas-credito/{sid}").json()["alcance"]
    v.check("aprobada: ya no se vuelve a firmar",
            alcance["puede_responder"] is False, alcance)
    v.check("y ahora sí se registra el número",
            alcance["puede_aplicar"] is True, alcance)


# ── Catálogo de motivos ──────────────────────────────────────────────────

def test_los_motivos_se_siembran_solos_y_no_se_duplican(entorno, v):
    """
    Se siembran al pedirlos para que una empresa nueva funcione sin un paso
    manual, y solo se agrega lo que falta: una siembra que reescribiera le
    devolvería a Contabilidad los motivos que ya había desactivado.
    """
    portal = entorno
    portal.como("logistica")
    primera = portal.get("/notas-credito/motivos").json()
    segunda = portal.get("/notas-credito/motivos").json()

    v.check("hay motivos de arranque", len(primera) > 0, primera)
    v.check("y pedirlos otra vez no los duplica",
            len(segunda) == len(primera), (len(primera), len(segunda)))


def test_desactivar_un_motivo_no_lo_borra(entorno, v):
    """El histórico apunta a él: borrarlo dejaría solicitudes sin motivo."""
    portal = entorno
    portal.como("admin")
    motivos = portal.get("/notas-credito/motivos").json()
    mid = motivos[0]["id"]

    portal.delete(f"/notas-credito/motivos/{mid}")
    activos = portal.get("/notas-credito/motivos").json()
    todos = portal.get("/notas-credito/motivos?incluir_inactivos=true").json()

    v.check("desaparece de los activos", all(m["id"] != mid for m in activos))
    v.check("pero sigue existiendo", any(m["id"] == mid for m in todos))


def test_la_ruta_de_motivos_no_se_la_come_el_id(entorno, v):
    """
    /motivos va declarada antes que /{id}. Si no, 'motivos' entra como id y
    responde un 422 — el mismo orden de rutas que ya mordió en este portal.
    """
    portal = entorno
    portal.como("logistica")
    r = portal.get("/notas-credito/motivos")
    v.check("responde el catálogo, no un error de tipo", r.status_code == 200, r.status_code)
    v.check("y es una lista", isinstance(r.json(), list), type(r.json()).__name__)


# ── A quién se le avisa ──────────────────────────────────────────────────

def _primer_aviso(portal, sid):
    from app.modules.notas_credito.notificaciones import avisos_en_turno

    db = portal.Session()
    solicitud = db.get(SolicitudNotaCredito, sid)
    avisos = avisos_en_turno(db, portal.tenant_id, solicitud)
    db.close()
    return avisos


def test_el_primer_aviso_va_a_comercial(entorno, v):
    """
    Sin esto habríamos cambiado un correo que funciona por una pantalla que
    nadie mira.

    El primer turno es de Comercial, así que el primer correo es suyo. Y en
    una del MOSTRADOR Contabilidad ya no va en copia: no le toca después, así
    que sería un correo sobre algo en lo que no tiene que hacer nada — que es
    como se aprende a no abrirlos.
    """
    portal = entorno
    _con_area(portal, "tics", "Comercial")
    _dar_capacidad_comercial(portal, "Comercial")
    _con_area(portal, "calidad", AREA_CONTABILIDAD)
    _dar_capacidades_nc(portal)
    portal.como("logistica")
    sid = _radicar(portal).json()["id"]

    avisos = _primer_aviso(portal, sid)
    v.check("se arma un aviso", len(avisos) == 1, avisos)
    evento, payload = avisos[0]
    v.check("por el evento del turno", evento == "nc-en-turno", evento)
    v.check("le llega a Comercial",
            payload["destinatarios"] == ["tics@p.com"], payload["destinatarios"])
    v.check("y Contabilidad NO va en copia",
            "calidad@p.com" not in payload["en_copia"], payload["en_copia"])
    v.check("dice de qué factura es",
            payload["factura_afectada"] == "POS#141824", payload)
    v.check("y qué tiene que hacer quien lo recibe", bool(payload["que_hacer"]), payload)


def test_en_la_institucional_contabilidad_sigue_yendo_en_copia(entorno, v):
    """
    Ahí sí le toca después —verificar ante la DIAN—, así que puede ir mirando
    la factura en vez de empezar a averiguarla cuando le llegue el turno. La
    copia sale de la CADENA, no de una lista escrita a mano: por eso una rama
    la lleva y la otra no, sin que nadie tenga que acordarse.
    """
    portal = entorno
    _con_area(portal, "tics", "Comercial")
    _dar_capacidad_comercial(portal, "Comercial")
    _con_area(portal, "calidad", AREA_CONTABILIDAD)
    _dar_capacidades_nc(portal)
    db = portal.Session()
    otorgar_a_area(db, portal.tenant_id, "notas_credito.verificar_dian",
                   AREA_CONTABILIDAD, portal.ids["admin"])
    db.close()

    portal.como("logistica")
    sid = _radicar(portal, punto_venta="Venta institucional").json()["id"]

    _, payload = _primer_aviso(portal, sid)[0]
    v.check("le llega a Comercial",
            payload["destinatarios"] == ["tics@p.com"], payload["destinatarios"])
    v.check("y Contabilidad va en copia",
            "calidad@p.com" in payload["en_copia"], payload["en_copia"])


def test_despues_de_comercial_el_aviso_es_de_contabilidad(entorno, v):
    """El turno se mueve y el correo lo sigue: nadie tiene que avisar a mano."""
    from app.modules.notas_credito.notificaciones import avisos_en_turno

    portal = entorno
    _con_area(portal, "calidad", AREA_CONTABILIDAD)
    _dar_capacidades_nc(portal)
    portal.como("logistica")
    sid = _radicar(portal).json()["id"]
    _pasar_comercial(portal, sid)

    db = portal.Session()
    solicitud = db.get(SolicitudNotaCredito, sid)
    avisos = avisos_en_turno(db, portal.tenant_id, solicitud)
    db.close()

    _, payload = avisos[0]
    v.check("ahora le llega a Contabilidad",
            payload["destinatarios"] == ["calidad@p.com"], payload["destinatarios"])
    v.check("y ya no va nadie en copia: es el último que decide",
            payload["en_copia"] == [], payload["en_copia"])


def test_el_lider_del_area_se_entera_de_que_su_gente_pidio_una(entorno, v):
    """
    El líder del área de quien radica va en COPIA del primer aviso.

    No es un paso del flujo —no firma nada y la solicitud no lo espera—: es
    enterarse de que su sede pidió una nota crédito. Meterlo en la cadena
    habría sido una firma que nadie pidió y un sitio donde la solicitud se
    queda quieta cuando el líder está de vacaciones.
    """
    from app.modules.notas_credito.notificaciones import avisos_en_turno

    portal = entorno
    _con_area(portal, "tics", "Comercial")
    _dar_capacidad_comercial(portal, "Comercial")
    # "calidad" es líder del área Calidad; "logistica" queda en esa área para
    # que sea su jefe quien tenga que enterarse.
    _con_area(portal, "logistica", "Calidad")
    portal.como("logistica")
    sid = _radicar(portal).json()["id"]

    db = portal.Session()
    solicitud = db.get(SolicitudNotaCredito, sid)
    avisos = avisos_en_turno(db, portal.tenant_id, solicitud)
    db.close()

    _, payload = avisos[0]
    v.check("el turno sigue siendo de Comercial",
            payload["destinatarios"] == ["tics@p.com"], payload["destinatarios"])
    v.check("y el líder del área va en copia",
            "calidad@p.com" in payload["en_copia"], payload["en_copia"])
    v.check("sin recibir el correo como si le tocara a él",
            "calidad@p.com" not in payload["destinatarios"], payload)


def test_el_lider_solo_se_entera_al_principio(entorno, v):
    """
    En los turnos siguientes ya no aporta nada, y serían cuatro correos por
    una sola nota crédito — que es como se aprende a no abrirlos.
    """
    from app.modules.notas_credito.notificaciones import avisos_en_turno

    portal = entorno
    _con_area(portal, "logistica", "Calidad")   # su líder es "calidad"
    _dar_capacidades_nc(portal, "Calidad")
    portal.como("logistica")
    sid = _radicar(portal).json()["id"]
    _pasar_comercial(portal, sid)

    db = portal.Session()
    solicitud = db.get(SolicitudNotaCredito, sid)
    avisos = avisos_en_turno(db, portal.tenant_id, solicitud)
    db.close()

    _, payload = avisos[0]
    v.check("en el segundo turno el líder ya no va en copia",
            "calidad@p.com" not in payload["en_copia"], payload["en_copia"])


def test_la_respuesta_le_llega_a_quien_la_pidio_y_no_al_area(entorno, v):
    """
    Es una persona la que está esperando para atender a su cliente. Mandarlo
    al área entera es que le llegue a todo el almacén menos, en la práctica, a
    quien tiene que actuar.
    """
    from app.modules.notas_credito.notificaciones import avisos_respondida

    portal = entorno
    portal.como("logistica")
    sid = _radicar(portal).json()["id"]

    db = portal.Session()
    solicitud = db.get(SolicitudNotaCredito, sid)
    avisos = avisos_respondida(db, portal.tenant_id, solicitud, "aprobada", "Cali")
    db.close()

    _, payload = avisos[0]
    v.check("le llega a una sola persona", len(payload["destinatarios"]) == 1, payload)
    v.check("y es quien la pidió",
            payload["destinatarios"] == ["logistica@p.com"], payload["destinatarios"])
    v.check("con la decisión", payload["decision"] == "aprobada", payload)


def test_el_soporte_no_viaja_como_enlace(entorno, v):
    """`/uploads` no pide sesión: un enlace en un correo se reenvía solo."""
    from app.modules.notas_credito.notificaciones import avisos_en_turno

    portal = entorno
    _con_area(portal, "tics", "Comercial")
    _dar_capacidad_comercial(portal, "Comercial")
    portal.como("logistica")
    sid = _radicar(portal).json()["id"]

    db = portal.Session()
    solicitud = db.get(SolicitudNotaCredito, sid)
    solicitud.adjunto = "/uploads/notas-credito/loquesea.pdf"
    db.commit()
    avisos = avisos_en_turno(db, portal.tenant_id, solicitud)
    db.close()

    _, payload = avisos[0]
    v.check("avisa que hay soporte", payload["tiene_adjunto"] is True, payload)
    v.check("pero no manda la ruta",
            not any("uploads" in str(x) for x in payload.values()), payload)


# ── El caso real que motivó la migración ──────────────────────────────────

def test_una_segunda_area_aprueba_sin_quitarle_nada_a_la_primera(entorno, v):
    """
    Aseguramiento también tramita notas crédito, no solo el área que ya tenía
    la capacidad — el caso real que hizo migrar este módulo al sistema de
    capacidades. Se otorga por la MISMA API que usaría un administrador desde
    Administración › Capacidades, y de ahí en adelante es el flujo real:
    endpoint /responder, no una llamada directa a una función de permisos.
    """
    from app.core.capacidades import otorgar_a_area

    portal = entorno
    _con_area(portal, "calidad", "Comercial")
    _dar_capacidad_comercial(portal, "Comercial")

    portal.como("logistica")
    sid = _radicar(portal).json()["id"]

    # Aseguramiento la recibe AHORA, con gente ya trabajando en el portal,
    # sin tocar código ni desplegar nada.
    _con_area(portal, "tics", "Aseguramiento")
    db = portal.Session()
    otorgar_a_area(db, portal.tenant_id, "notas_credito.aprobar_comercial",
                   "Aseguramiento", portal.ids["admin"])
    db.close()

    portal.como("tics")
    r = portal.post(f"/notas-credito/{sid}/responder", json={"decision": "aprobar"})
    v.check("Aseguramiento aprueba", r.status_code == 200, r.text[:250])

    # Y la primera área conserva su capacidad intacta: otorgar a una segunda
    # no le quitó nada.
    portal.como("logistica")
    sid2 = _radicar(portal).json()["id"]
    portal.como("calidad")
    r = portal.post(f"/notas-credito/{sid2}/responder", json={"decision": "aprobar"})
    v.check("Comercial sigue aprobando", r.status_code == 200, r.text[:250])
