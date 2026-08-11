"""
Endpoints internos del módulo de Encuestas.

Ver respuestas es de lectura y lo puede hacer cualquiera con sesión; crear y
editar plantillas escribe, así que pasa por `solo_lectura_no` — lo que
bloquea también a `gerencia`, igual que en el resto del portal.

El formulario que responde el cliente NO está aquí: va sin autenticación en
`router_public.py`.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, get_current_tenant_id, solo_lectura_no
from app.models.encuestas import Plantilla, Pregunta, Respuesta
from app.models.user import User
from app.modules.encuestas import service
from app.modules.encuestas.schemas import (
    PlantillaCreate, PlantillaOut, PlantillaUpdate, validar_tipo_pregunta,
)

router = APIRouter(prefix="/encuestas", tags=["Encuestas"])


def _get_plantilla_o_404(db: Session, plantilla_id: int, tenant_id: int) -> Plantilla:
    plantilla = db.query(Plantilla).filter(
        Plantilla.id == plantilla_id, Plantilla.tenant_id == tenant_id,
    ).first()
    if not plantilla:
        raise HTTPException(status_code=404, detail="Encuesta no encontrada.")
    return plantilla


def _contar_respuestas(db: Session, plantilla_id: int) -> int:
    return db.query(Respuesta).filter(Respuesta.plantilla_id == plantilla_id).count()


def _salida(db: Session, plantilla: Plantilla) -> dict:
    datos = PlantillaOut.model_validate(plantilla).model_dump()
    datos["total_respuestas"] = _contar_respuestas(db, plantilla.id)
    return datos


# ── Panel: todas las respuestas, vengan de donde vengan ─────────────────
# Va declarado ANTES que /{plantilla_id}, o el path variable se lo come.

@router.get("/panel")
def panel(
    origen: str | None = None,
    desde: datetime | None = None,
    hasta: datetime | None = None,
    sujeto: str | None = None,
    limite: int = 200,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(get_current_user),
):
    """
    Resumen, ranking por calificado y las respuestas del filtro.

    Junta la encuesta de PQRS con las de este módulo: para quien consulta son
    todas encuestas, aunque por dentro vivan en tablas distintas.
    """
    return service.construir_panel(db, tenant_id, origen, desde, hasta, sujeto, limite)


# ── Plantillas ──────────────────────────────────────────────────────────

@router.get("", response_model=list[PlantillaOut])
def listar_plantillas(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(get_current_user),
):
    plantillas = db.query(Plantilla).filter(
        Plantilla.tenant_id == tenant_id,
    ).order_by(Plantilla.nombre).all()
    return [_salida(db, p) for p in plantillas]


@router.post("", response_model=PlantillaOut, status_code=status.HTTP_201_CREATED)
def crear_plantilla(
    payload: PlantillaCreate,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(solo_lectura_no),
):
    slug = payload.slug.strip().lower()
    if not slug:
        raise HTTPException(
            status_code=400,
            detail="La encuesta necesita una dirección web (slug), por ejemplo «vendedores».",
        )

    existe = db.query(Plantilla).filter(
        Plantilla.tenant_id == tenant_id, Plantilla.slug == slug,
    ).first()
    if existe:
        raise HTTPException(
            status_code=400,
            detail=f"Ya hay una encuesta con la dirección «{slug}». Elige otra.",
        )

    for pregunta in payload.preguntas:
        try:
            validar_tipo_pregunta(pregunta.tipo)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    plantilla = Plantilla(
        tenant_id=tenant_id,
        **payload.model_dump(exclude={"preguntas", "slug"}),
        slug=slug,
    )
    db.add(plantilla)
    db.flush()

    for orden, pregunta in enumerate(payload.preguntas):
        datos = pregunta.model_dump()
        datos["orden"] = datos.get("orden") or orden
        db.add(Pregunta(plantilla_id=plantilla.id, **datos))

    db.commit()
    db.refresh(plantilla)
    return _salida(db, plantilla)


@router.get("/{plantilla_id}", response_model=PlantillaOut)
def obtener_plantilla(
    plantilla_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(get_current_user),
):
    return _salida(db, _get_plantilla_o_404(db, plantilla_id, tenant_id))


@router.patch("/{plantilla_id}", response_model=PlantillaOut)
def actualizar_plantilla(
    plantilla_id: int,
    payload: PlantillaUpdate,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(solo_lectura_no),
):
    plantilla = _get_plantilla_o_404(db, plantilla_id, tenant_id)
    datos = payload.model_dump(exclude_unset=True)
    preguntas = datos.pop("preguntas", None)

    if preguntas is not None:
        respondidas = _contar_respuestas(db, plantilla.id)
        if respondidas:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Esta encuesta ya tiene {respondidas} respuesta(s): cambiarle las "
                    "preguntas dejaría esas respuestas contestando algo que ya no se "
                    "pregunta. Desactívala y crea una versión nueva."
                ),
            )
        for pregunta in preguntas:
            try:
                validar_tipo_pregunta(pregunta["tipo"])
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        plantilla.preguntas.clear()
        db.flush()
        for orden, pregunta in enumerate(preguntas):
            pregunta["orden"] = pregunta.get("orden") or orden
            db.add(Pregunta(plantilla_id=plantilla.id, **pregunta))

    for campo, valor in datos.items():
        setattr(plantilla, campo, valor)

    db.commit()
    db.refresh(plantilla)
    return _salida(db, plantilla)


@router.delete("/{plantilla_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_plantilla(
    plantilla_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(solo_lectura_no),
):
    plantilla = _get_plantilla_o_404(db, plantilla_id, tenant_id)
    respondidas = _contar_respuestas(db, plantilla.id)
    if respondidas:
        raise HTTPException(
            status_code=409,
            detail=(
                f"No se puede borrar: tiene {respondidas} respuesta(s) que se perderían. "
                "Desactívala para que deje de recibir respuestas nuevas."
            ),
        )
    db.delete(plantilla)
    db.commit()
