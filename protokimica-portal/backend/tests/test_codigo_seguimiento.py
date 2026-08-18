"""
El código de seguimiento no se puede repetir.

Es lo único que tiene el cliente para consultar su solicitud, y la columna
tiene índice único: un código repetido no es un número feo, es un error 500
en la cara de quien está radicando.

Pasó en producción: el consecutivo se calculaba contando las PQRS del
prefijo. Con VI0001 y VI0003 en la tabla —porque alguien borró la del
medio— contar daba 2 y el siguiente salía VI0003, que ya existía. Y como
el choque ocurre al guardar el código, DESPUÉS de haber guardado la
solicitud, la PQRS quedaba radicada sin código y sin avisarle a nadie.
"""
from app.models.pqrs import PQRSSolicitud
from app.modules.pqrs.service import (
    asignar_codigo_seguimiento, generar_codigo_seguimiento,
)

VENTA_INSTITUCIONAL = "Venta institucional"   # prefijo VI


def _pqrs(entorno, db, codigo=None, canal=VENTA_INSTITUCIONAL):
    p = PQRSSolicitud(
        tenant_id=entorno.tenant_id,
        tipo="queja",
        cliente_nombre="Cliente",
        descripcion="Algo pasó",
        estado="recibido",
        canal_atencion=canal,
        codigo_seguimiento=codigo,
    )
    db.add(p)
    db.commit()
    return p


def test_el_consecutivo_sigue_al_ultimo(entorno):
    db = entorno.Session()
    for c in ["VI0001", "VI0002", "VI0003"]:
        _pqrs(entorno, db, c)

    assert generar_codigo_seguimiento(db, entorno.tenant_id, VENTA_INSTITUCIONAL) == "VI0004"
    db.close()


def test_un_hueco_en_el_medio_no_repite_un_codigo(entorno):
    """El caso que reventó en producción."""
    db = entorno.Session()
    _pqrs(entorno, db, "VI0001")
    _pqrs(entorno, db, "VI0003")      # la VI0002 se borró en algún momento

    codigo = generar_codigo_seguimiento(db, entorno.tenant_id, VENTA_INSTITUCIONAL)

    assert codigo == "VI0004", f"se repitió un código ya usado: {codigo}"
    db.close()


def test_pasar_de_9999_no_retrocede(entorno):
    """Ordenar por texto pondría '10000' antes que '9999'."""
    db = entorno.Session()
    _pqrs(entorno, db, "VI9999")
    _pqrs(entorno, db, "VI10000")

    assert generar_codigo_seguimiento(db, entorno.tenant_id, VENTA_INSTITUCIONAL) == "VI10001"
    db.close()


def test_cada_prefijo_lleva_su_propia_cuenta(entorno):
    """Lo de Guayabal no le roba el número a venta institucional."""
    db = entorno.Session()
    _pqrs(entorno, db, "VI0001")
    _pqrs(entorno, db, "PVG0001")
    _pqrs(entorno, db, "PVG0002")

    assert generar_codigo_seguimiento(db, entorno.tenant_id, VENTA_INSTITUCIONAL) == "VI0002"
    assert generar_codigo_seguimiento(
        db, entorno.tenant_id, "Punto de venta Guayabal") == "PVG0003"
    db.close()


def test_un_codigo_con_basura_no_rompe_la_cuenta(entorno):
    """Un código escrito a mano en la base no puede tumbar la radicación."""
    db = entorno.Session()
    _pqrs(entorno, db, "VI0001")
    _pqrs(entorno, db, "VIsin-numero")

    assert generar_codigo_seguimiento(db, entorno.tenant_id, VENTA_INSTITUCIONAL) == "VI0002"
    db.close()


def test_si_el_codigo_esta_tomado_se_reintenta(entorno):
    """
    Dos personas radicando a la vez leen el mismo número: la segunda choca
    contra el índice único y hay que recalcular, no devolver un 500.
    """
    db = entorno.Session()
    _pqrs(entorno, db, "VI0001")
    solicitud = _pqrs(entorno, db, None)     # la que se está radicando ahora

    # Alguien se le adelanta y toma el VI0002 justo antes del commit.
    original = generar_codigo_seguimiento(db, entorno.tenant_id, VENTA_INSTITUCIONAL)
    assert original == "VI0002"
    otra_sesion = entorno.Session()
    _pqrs(entorno, otra_sesion, "VI0002")
    otra_sesion.close()

    codigo = asignar_codigo_seguimiento(db, solicitud, entorno.tenant_id, VENTA_INSTITUCIONAL)

    assert codigo == "VI0003"
    assert solicitud.codigo_seguimiento == "VI0003"
    db.close()


def test_radicar_dos_veces_seguidas_da_codigos_distintos(entorno):
    """La prueba de verdad, contra la API real."""
    codigos = set()
    for _ in range(3):
        r = entorno.post("/pqrs", data={
            "tipo": "queja",
            "descripcion": "El producto llegó mal.",
            "cliente_nombre": "Cliente",
            "canal_atencion": VENTA_INSTITUCIONAL,
        })
        assert r.status_code == 201, r.text
        codigos.add(r.json()["codigo_seguimiento"])

    assert len(codigos) == 3, f"se repitieron códigos: {codigos}"


def test_ninguna_pqrs_queda_sin_codigo(entorno):
    """Sin código el cliente no puede consultar su solicitud nunca más."""
    r = entorno.post("/pqrs", data={
        "tipo": "reclamo",
        "descripcion": "Falta producto en la caja.",
        "cliente_nombre": "Cliente",
        "canal_atencion": VENTA_INSTITUCIONAL,
    })
    assert r.status_code == 201, r.text
    assert r.json()["codigo_seguimiento"]
