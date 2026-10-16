"""
De dónde más puede nacer una OMP: los orígenes que declaran los otros
módulos (`origen_omp.py`, ver `core/origenes_omp.py`). Hoy, PQRS.

Se reúnen al pedirlos, filtrados por lo que la empresa tiene contratado:
sin PQRS contratado, una OMP no nace de una PQRS aunque el código esté.
"""
from sqlalchemy.orm import Session

from app.core import modulos, registro
from app.core.origenes_omp import PropuestaOMP
from app.models.user import User


def _reunir() -> dict:
    origenes = {}
    for pieza in registro.piezas("origen_omp"):
        for clave, fn in getattr(pieza, "ORIGENES", {}).items():
            assert clave not in origenes, f"El origen de OMP '{clave}' está declarado dos veces."
            origenes[clave] = (registro.paquete_de(pieza), fn)
    return origenes


ORIGENES = _reunir()


def propuesta(db: Session, origen: str, origen_id: int, usuario: User) -> PropuestaOMP | None:
    """La propuesta de ese origen, o None si no existe, no está contratado o no se ve."""
    if origen not in ORIGENES:
        return None
    paquete, fn = ORIGENES[origen]
    if not modulos.paquete_contratado(usuario.tenant, paquete):
        return None
    return fn(db, usuario.tenant_id, origen_id, usuario)
