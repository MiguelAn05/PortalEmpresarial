"""
Buscador de productos del formulario público. Sin autenticación.

Lo consume el cliente que va a radicar una PQRS, así que está abierto a
internet. Tres cosas lo acotan:

  - Solo devuelve código, nombre y presentación. En la copia local no hay
    precios ni existencias, así que no hay nada más que pudiera filtrarse.
  - Exige un mínimo de caracteres y devuelve pocos resultados.
  - Tiene límite por IP, para que nadie se descargue el catálogo consultando
    letra por letra.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.rate_limit import limitar_busqueda_publica
from app.models.tenant import Tenant
from app.modules.catalogo import service

router = APIRouter(prefix="/public/catalogo", tags=["Catálogo (público)"])


@router.get("/productos", dependencies=[Depends(limitar_busqueda_publica)])
def buscar_productos_publico(q: str = "", db: Session = Depends(get_db)):
    tenant = db.query(Tenant).filter(Tenant.slug == "protokimica").first()
    if not tenant:
        raise HTTPException(status_code=500, detail="Error de configuración.")
    return service.buscar(db, tenant.id, q)
