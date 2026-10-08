"""
Pedir una autorización: lo que pasa siempre, la pida una persona o el flujo.

Vivía dentro del endpoint `solicitar`. Ahora también la pide el flujo de la
PQRS (`pqrs/flujo.py`) cuando se aprueba el concepto anterior, y si cada uno
llevara su copia, el día que cambie una regla —mover el caso al área que
firma, contar sus 3 días— una de las dos dejaría de cumplirla.

No hace `commit`: quien llama decide cuándo, para que pedir la autorización y
lo que la provocó queden en la misma transacción.
"""
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.autorizacion import AutorizacionPQRS, TipoAutorizacion
from app.models.pqrs import PQRSSeguimiento, PQRSSolicitud
from app.modules.pqrs import tiempo_en_area


def registrar_solicitud(
    db: Session,
    pqrs: PQRSSolicitud,
    tipo: TipoAutorizacion,
    usuario_id: int,
    *,
    comentario: str | None = None,
    ruta_adjunto: str | None = None,
    nota_flujo: str | None = None,
) -> AutorizacionPQRS:
    """
    Crea la autorización, pasa la PQRS al área que firma (con su reloj de 3
    días) y deja el renglón en el historial. `nota_flujo` dice, cuando la
    pidió el flujo, por qué paso va.
    """
    if pqrs.estado == "cerrado":
        raise HTTPException(status_code=400, detail="No se puede solicitar autorización en una PQRS cerrada.")

    existente = db.query(AutorizacionPQRS).filter(
        AutorizacionPQRS.pqrs_id == pqrs.id,
        AutorizacionPQRS.tipo_id == tipo.id,
        AutorizacionPQRS.estado == "pendiente",
    ).first()
    if existente:
        raise HTTPException(status_code=400, detail="Ya existe una autorización pendiente de ese tipo.")

    autorizacion = AutorizacionPQRS(
        pqrs_id=pqrs.id,
        tipo_id=tipo.id,
        estado="pendiente",
        solicitado_por=usuario_id,
        comentario_solicitud=comentario,
        adjunto_solicitud=ruta_adjunto,
    )
    db.add(autorizacion)

    # La PQRS pasa al área que tiene que firmar: la pregunta y el caso viajan
    # juntos, así aparece en la bandeja de quien puede resolverla.
    area_anterior = pqrs.area_responsable
    pqrs.area_responsable = tipo.area_autorizadora
    # Mientras se firma, los 3 días hábiles son del área que autoriza.
    tiempo_en_area.registrar_cambio(db, pqrs, area_anterior, pqrs.estado)

    detalle = [f"Se solicitó autorización: {tipo.nombre}."]
    if nota_flujo:
        detalle.append(nota_flujo)
    if tipo.area_autorizadora != area_anterior:
        detalle.append(
            f"Área: {area_anterior or 'sin asignar'} -> {tipo.area_autorizadora} "
            "mientras se responde."
        )
    if comentario:
        detalle.append(comentario.strip())

    db.add(PQRSSeguimiento(
        pqrs_id=pqrs.id,
        usuario_id=usuario_id,
        tipo_evento="autorizacion_solicitada",
        comentario=" ".join(detalle),
        adjunto_evidencia=ruta_adjunto,
    ))
    db.flush()
    return autorizacion
