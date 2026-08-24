"""
El radicado de Calidad sale del máximo, no de un conteo.

Es el mismo defecto que ya costó caro en el código de seguimiento: contar
da el número equivocado en cuanto falta uno del medio, y como la columna es
única, la colisión revienta el commit DESPUÉS de guardar la solicitud.
"""
from datetime import datetime, timezone

from app.models.pqrs import PQRSSolicitud
from app.modules.pqrs.service import generar_radicado_calidad


def _pqrs(db, tenant_id, radicado):
    db.add(PQRSSolicitud(
        tenant_id=tenant_id, tipo="peticion", cliente_nombre="Cliente",
        descripcion="algo", estado="recibido", prioridad="media",
        origen_publico="publico", radicado_calidad=radicado,
    ))
    db.commit()


def test_con_un_hueco_en_el_medio_no_se_repite_el_numero(entorno, v):
    portal = entorno
    db = portal.Session()
    anio = datetime.now(timezone.utc).year

    # Alguien borró la 0002: quedan la 1 y la 3.
    _pqrs(db, portal.tenant_id, f"CAL-{anio}-0001")
    _pqrs(db, portal.tenant_id, f"CAL-{anio}-0003")

    siguiente = generar_radicado_calidad(db, portal.tenant_id)
    v.check("sigue después del mayor, no del conteo",
            siguiente == f"CAL-{anio}-0004", siguiente)
    db.close()


def test_sin_radicados_empieza_en_uno(entorno, v):
    portal = entorno
    db = portal.Session()
    anio = datetime.now(timezone.utc).year
    v.check("arranca en 0001",
            generar_radicado_calidad(db, portal.tenant_id) == f"CAL-{anio}-0001")
    db.close()


def test_pasar_de_9999_no_se_desordena(entorno, v):
    """Por texto, '10000' iría antes que '9999' y el consecutivo retrocedería."""
    portal = entorno
    db = portal.Session()
    anio = datetime.now(timezone.utc).year
    _pqrs(db, portal.tenant_id, f"CAL-{anio}-9999")
    _pqrs(db, portal.tenant_id, f"CAL-{anio}-10000")

    v.check("sigue en 10001",
            generar_radicado_calidad(db, portal.tenant_id) == f"CAL-{anio}-10001",
            generar_radicado_calidad(db, portal.tenant_id))
    db.close()
