"""
Registro de cambios de proyectos y tareas.

Criterio: se guardan los campos que gerencia necesita auditar (fechas,
estado, prioridad, responsables, avance, presupuesto) con su valor anterior
y nuevo. De los textos largos solo se deja constancia de que cambiaron —
volcar párrafos completos convierte el historial en un muro ilegible y lo
que importa ahí es el "cuándo y quién", no el diff palabra por palabra.
"""
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.master_planner import HistorialCambio
from app.models.user import User

# Campos con valor concreto: se guarda antes → después.
CAMPOS_PROYECTO = {
    "nombre", "estado", "prioridad", "area", "lider_id", "archivado",
    "fecha_inicio", "fecha_fin_estimada", "fecha_fin_real",
}
CAMPOS_TAREA = {
    "titulo", "estado", "prioridad", "area", "asignado_a", "avance_pct",
    "fecha_inicio", "fecha_fin",
}

# Campos de texto largo: solo se registra que se modificaron.
CAMPOS_TEXTO_PROYECTO = {"objetivo", "alcance"}
CAMPOS_TEXTO_TAREA = {"descripcion", "riesgos"}

# Campos cuyo valor es un id de usuario: se guarda el nombre para que el
# historial siga leyéndose aunque el usuario se desactive después.
CAMPOS_USUARIO = {"lider_id", "asignado_a"}


def _formatear(db: Session, campo: str, valor) -> str | None:
    if valor is None or valor == "":
        return None
    if campo in CAMPOS_USUARIO:
        usuario = db.get(User, int(valor))
        return usuario.nombre if usuario else f"Usuario #{valor}"
    if isinstance(valor, datetime):
        return valor.isoformat()
    if isinstance(valor, bool):
        return "si" if valor else "no"
    return str(valor)


def _mismo_valor(a, b) -> bool:
    """
    Compara ignorando diferencias que no son cambios reales: None vs "" y
    fechas con o sin microsegundos.
    """
    if a is None and b == "":
        return True
    if b is None and a == "":
        return True
    if isinstance(a, datetime) and isinstance(b, datetime):
        return a.replace(microsecond=0) == b.replace(microsecond=0)
    return a == b


def registrar_cambios(
    db: Session,
    entidad: str,
    entidad_id: int,
    proyecto_id: int,
    antes: dict,
    despues: dict,
    usuario_id: int | None,
    entidad_nombre: str | None = None,
) -> int:
    """
    Compara dos instantáneas del mismo objeto y escribe una fila por cada
    campo auditable que cambió. NO hace commit: lo deja en la sesión para
    que el cambio y su registro entren o fallen juntos.

    Devuelve cuántos cambios se registraron.
    """
    if entidad == "proyecto":
        campos, campos_texto = CAMPOS_PROYECTO, CAMPOS_TEXTO_PROYECTO
    else:
        campos, campos_texto = CAMPOS_TAREA, CAMPOS_TEXTO_TAREA

    registrados = 0
    for campo, valor_nuevo in despues.items():
        if campo not in campos and campo not in campos_texto:
            continue

        valor_anterior = antes.get(campo)
        if _mismo_valor(valor_anterior, valor_nuevo):
            continue

        if campo in campos_texto:
            # Sin volcar el texto: el frontend lo muestra como "se modificó X".
            anterior, nuevo = None, None
        else:
            anterior = _formatear(db, campo, valor_anterior)
            nuevo = _formatear(db, campo, valor_nuevo)

        db.add(HistorialCambio(
            entidad=entidad,
            entidad_id=entidad_id,
            entidad_nombre=entidad_nombre,
            proyecto_id=proyecto_id,
            campo=campo,
            valor_anterior=anterior,
            valor_nuevo=nuevo,
            usuario_id=usuario_id,
        ))
        registrados += 1

    return registrados


def instantanea(obj, entidad: str) -> dict:
    """Copia de los campos auditables de un objeto, para comparar antes/después."""
    campos = (CAMPOS_PROYECTO | CAMPOS_TEXTO_PROYECTO) if entidad == "proyecto" \
        else (CAMPOS_TAREA | CAMPOS_TEXTO_TAREA)
    return {campo: getattr(obj, campo, None) for campo in campos}


def registrar_evento(
    db: Session,
    entidad: str,
    entidad_id: int,
    proyecto_id: int,
    campo: str,
    usuario_id: int | None,
    valor_anterior: str | None = None,
    valor_nuevo: str | None = None,
    entidad_nombre: str | None = None,
) -> None:
    """
    Registra algo que no es el cambio de un campo del objeto, como agregar o
    quitar un ítem de presupuesto. Mismo formato para que el historial se lea
    en una sola línea de tiempo.
    """
    db.add(HistorialCambio(
        entidad=entidad,
        entidad_id=entidad_id,
        entidad_nombre=entidad_nombre,
        proyecto_id=proyecto_id,
        campo=campo,
        valor_anterior=valor_anterior,
        valor_nuevo=valor_nuevo,
        usuario_id=usuario_id,
    ))
