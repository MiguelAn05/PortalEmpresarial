"""
Quién hace qué en Fichas de seguridad.

**El rol abre el módulo; la capacidad decide quién escribe.** Las fichas se
consultan desde todos los roles (una ficha de seguridad la necesita quien
manipula el producto, no solo quien la archiva), así que entran los cinco
(ver `core/modulos.py`). Subir una ficha, subirle una versión, corregirla,
desactivarla o borrarla es de quien tenga la capacidad
`fichas_seguridad.gestionar`, que se otorga a un área o a una persona en
Administración › Capacidades. No va sembrada: qué área es dueña de las fichas
lo decide la empresa, no el código.

Encima de eso, `solo_lectura_no` (en el router) sigue bloqueando a `lectura` y
a `gerencia` en toda escritura, tengan o no la capacidad.
"""
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core import capacidades
from app.models.user import User

CAPACIDAD_GESTIONAR = "fichas_seguridad.gestionar"


def puede_gestionar(usuario: User) -> bool:
    return capacidades.del_usuario(usuario, CAPACIDAD_GESTIONAR)


def exigir_gestionar(db: Session, usuario: User) -> None:
    """403 que dice a quién pedírselo, leído de la tabla de capacidades."""
    if not puede_gestionar(usuario):
        quienes = capacidades.quienes_lo_hacen(db, usuario.tenant_id, CAPACIDAD_GESTIONAR)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Subir o cambiar fichas de seguridad le corresponde a {quienes}. "
                   "Si lo necesitas, pídeselo.",
        )
