"""
A qué empresa pertenece una página pública: el formulario de PQRS, los QR de
las sedes, las encuestas, el buscador del catálogo.

Ahí no hay sesión de la que sacar el tenant. Hoy el portal atiende a una sola
empresa, así que es una sola —`SLUG_PUBLICO`—; antes ese `slug ==
"protokimica"` estaba escrito a mano en cuatro routers. El día que el portal
atienda a varias (fase 4 del plan de modularización), la empresa sale del
dominio por el que se entró y solo cambia este archivo.
"""
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.modulos import contratados_de
from app.models.tenant import Tenant

SLUG_PUBLICO = "protokimica"


def tenant_publico(db: Session) -> Tenant:
    tenant = db.query(Tenant).filter(Tenant.slug == SLUG_PUBLICO).first()
    if not tenant:
        raise HTTPException(status_code=500, detail="Error de configuración: no existe la empresa del portal público.")
    return tenant


def contratado_en_publico(modulo: str):
    """
    Dependencia para los routers públicos: si la empresa no tiene el módulo,
    la página no existe (404). Un cliente que abre un QR viejo no tiene por
    qué enterarse de qué contrató la empresa.
    """
    def verificar(db: Session = Depends(get_db)) -> None:
        if modulo not in contratados_de(tenant_publico(db)):
            raise HTTPException(status_code=404, detail="Esta página no está disponible.")
    return verificar
