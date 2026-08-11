"""
El formulario que responde el cliente. Sin autenticación.

Es la parte que se abre desde un QR pegado en un punto de venta, así que la
dirección tiene que ser corta y estable: /encuesta/<slug>.

Solo expone lo justo para responder —las preguntas y el mensaje final— y
nunca las respuestas de otros. Aquí no se lee nada de lo que ya contestó
nadie más.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.encuestas import Plantilla
from app.models.tenant import Tenant
from app.modules.encuestas import service
from app.modules.encuestas.schemas import RespuestaCreate

router = APIRouter(prefix="/public/encuestas", tags=["Encuestas (público)"])


def _plantilla_activa(db: Session, slug: str) -> Plantilla:
    # TODO: `slug == "protokimica"` sigue quemado como en el resto de lo
    # público. Cuando el portal sirva a más de una empresa hay que resolver
    # el tenant por dominio, no por constante.
    tenant = db.query(Tenant).filter(Tenant.slug == "protokimica").first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Encuesta no disponible.")

    plantilla = db.query(Plantilla).filter(
        Plantilla.tenant_id == tenant.id,
        Plantilla.slug == slug.strip().lower(),
    ).first()

    if not plantilla or not plantilla.activa:
        raise HTTPException(
            status_code=404,
            detail="Esta encuesta no está disponible. Verifica el enlace o el código QR.",
        )
    return plantilla


@router.get("/{slug}")
def ver_encuesta(slug: str, db: Session = Depends(get_db)):
    """Las preguntas, para pintar el formulario."""
    plantilla = _plantilla_activa(db, slug)
    return {
        "nombre": plantilla.nombre,
        "descripcion": plantilla.descripcion,
        "sujeto_tipo": plantilla.sujeto_tipo,
        "preguntas": [
            {
                "id": p.id,
                "texto": p.texto,
                "ayuda": p.ayuda,
                "tipo": p.tipo,
                "opciones": [o.strip() for o in (p.opciones or "").split("|") if o.strip()],
                "obligatoria": p.obligatoria,
            }
            for p in plantilla.preguntas
        ],
    }


@router.post("/{slug}")
def responder(slug: str, payload: RespuestaCreate, db: Session = Depends(get_db)):
    plantilla = _plantilla_activa(db, slug)
    try:
        service.guardar_respuesta(db, plantilla, payload.model_dump())
    except ValueError as e:
        # Los errores de validación dependen de las preguntas, que son datos:
        # el mensaje ya dice qué falta y qué hacer.
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "mensaje": plantilla.mensaje_final or "¡Gracias por responder!",
    }
