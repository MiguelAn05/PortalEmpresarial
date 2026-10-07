"""
Deja una PQRS con su causa marcada, para las pruebas que la cierran a mano.

Cerrar a mano exige «Asociado a» y área causante (ver `pqrs/asociados.py`).
Las pruebas que no son sobre eso usan esto para no repetir el paso.
"""
from app.models.pqrs import PQRSSolicitud
from app.modules.pqrs import asociados


def con_causa(entorno, pqrs_id, area="Calidad"):
    db = entorno.Session()
    p = db.get(PQRSSolicitud, pqrs_id)
    p.asociado_id = asociados.del_tenant(db, p.tenant_id)[0].id
    p.area_causante = area
    db.commit()
    db.close()
