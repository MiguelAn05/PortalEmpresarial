"""
El contrato de un origen de OMP: de dónde puede nacer una oportunidad de
mejora además de un indicador.

Una PQRS cuya causa lo sugiere («Asociado a» con `sugiere_omp`) se vuelve
OMP desde su detalle. Mejora no puede leer la tabla de PQRS —un módulo no
importa de otro, ver `tests/test_modularidad.py`—, así que PQRS declara en
`modules/pqrs/origen_omp.py` cómo se lee una de sus solicitudes, y Mejora lo
reúne con `core/registro.py`. Aquí vive solo la forma común.

Un módulo declara `ORIGENES = {clave: fn}`, donde
`fn(db, tenant_id, id, usuario)` devuelve una `PropuestaOMP`, o `None` si
ese registro no existe o esa persona no lo puede ver (para quien pregunta,
es lo mismo: 404).
"""
from dataclasses import dataclass


@dataclass
class PropuestaOMP:
    """Con qué arranca el formulario de la OMP. Todo se puede cambiar."""
    referencia: str             # cómo se nombra el origen: «PQRS PVG0010»
    titulo: str
    descripcion: str
    area: str | None            # el área que la va a trabajar, si se sabe
    sugiere: bool               # la causa marcada pide una OMP
    motivo: str | None = None   # por qué lo sugiere, dicho para la pantalla
