"""
Qué se perdería si se borrara a un usuario.

El borrado por defecto del portal **protege el histórico** (ver «Borrar
cosas»): cuando algo tiene datos asociados no se borra en silencio, se
responde 409 explicando qué se perdería y ofreciendo la salida suave.

Con un usuario esa regla es más estricta que en el resto del portal, y a
propósito: **un usuario que ya trabajó no se borra nunca, ni forzándolo.**
Su id está escrito en quién aprobó un presupuesto, quién autorizó una nota
crédito, quién movió una PQRS y quién firmó el cierre de una OMP. Borrarlo
obligaría a romper esas referencias o a vaciarlas, y entonces el historial
—que es justamente lo que se audita— pasaría a decir «alguien» donde antes
decía un nombre. Para eso está **desactivar**: no puede entrar, y todo lo
suyo queda tal cual.

Lo que sí se borra es el usuario que nunca hizo nada: el que se creó con el
correo mal escrito, o dos veces, o para una persona que al final no entró. Si
no se pudiera, la lista de usuarios de un portal viejo termina siendo un
cementerio de intentos que nadie se atreve a tocar.

**Los rastros se buscan recorriendo el metadato**, no con una lista escrita a
mano: toda columna que apunte a `users.id` cuenta. Una tabla nueva que
referencie usuarios queda cubierta sola el día que se cree, que es justo el
día en que nadie se acordaría de venir a agregarla aquí.
"""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import Base

# Lo que es CONFIGURACIÓN del propio usuario y se va con él: no es trabajo
# suyo, es cómo estaba configurado. Dejar estas filas bloqueando el borrado
# haría que un usuario recién creado —al que alguien alcanzó a marcarle un
# área supervisada— ya no se pudiera eliminar.
COLUMNAS_PROPIAS = {
    ("usuario_areas_supervisadas", "usuario_id"),
    ("capacidades_otorgadas", "usuario_id"),
}

# Cómo se nombra cada tabla en el mensaje. Una que no esté aquí sale con su
# nombre técnico: feo, pero mejor que no avisar. El singular va primero.
NOMBRES = {
    "pqrs_solicitudes":      ("PQRS asignada", "PQRS asignadas"),
    "pqrs_seguimientos":     ("movimiento en una PQRS", "movimientos en PQRS"),
    "mp_proyectos":          ("proyecto que lidera", "proyectos que lidera"),
    "mp_tareas":             ("tarea asignada", "tareas asignadas"),
    "mp_actualizaciones":    ("actualización de tarea", "actualizaciones de tareas"),
    "mp_historial":          ("cambio registrado en un proyecto", "cambios registrados en proyectos"),
    "mp_items_presupuesto":  ("aprobación de presupuesto", "aprobaciones de presupuesto"),
    "mp_pagos":              ("pago registrado", "pagos registrados"),
    "mp_cierres":            ("acta de cierre", "actas de cierre"),
    "nc_solicitudes":        ("nota crédito", "notas crédito"),
    "nc_historial":          ("firma en una nota crédito", "firmas en notas crédito"),
    "omp_oportunidades":     ("oportunidad de mejora", "oportunidades de mejora"),
    "omp_seguimientos":      ("seguimiento de mejora", "seguimientos de mejora"),
    "omp_acciones":          ("acción de mejora", "acciones de mejora"),
    "omp_historial":         ("cambio en una oportunidad", "cambios en oportunidades"),
    "ind_indicadores":       ("indicador a cargo", "indicadores a cargo"),
    "ind_mediciones":        ("medición registrada", "mediciones registradas"),
    "ind_historial":         ("cambio en un indicador", "cambios en indicadores"),
    "autorizaciones":        ("autorización", "autorizaciones"),
    "capacidades_otorgadas": ("permiso que otorgó", "permisos que otorgó"),
}


def _columnas_hacia_usuarios():
    """Toda columna del portal que apunte a `users.id`, sacada del metadato."""
    for tabla in Base.metadata.sorted_tables:
        for columna in tabla.columns:
            for fk in columna.foreign_keys:
                destino = fk.column
                if destino.table.name == "users" and destino.name == "id":
                    yield tabla, columna


def rastros_de(db: Session, usuario_id: int) -> dict[str, int]:
    """
    Cuántas filas de trabajo quedarían apuntando a este usuario, por tabla.

    Vacío significa que no dejó rastro y se puede borrar. La configuración
    propia no cuenta (ver `COLUMNAS_PROPIAS`).
    """
    conteos: dict[str, int] = {}
    for tabla, columna in _columnas_hacia_usuarios():
        if (tabla.name, columna.name) in COLUMNAS_PROPIAS:
            continue
        cuantas = db.execute(
            select(func.count()).select_from(tabla).where(columna == usuario_id)
        ).scalar_one()
        if cuantas:
            conteos[tabla.name] = conteos.get(tabla.name, 0) + cuantas
    return conteos


def _frase(tabla: str, cuantas: int) -> str:
    singular, plural = NOMBRES.get(tabla, (tabla, tabla))
    return f"{cuantas} {singular if cuantas == 1 else plural}"


def explicar(nombre: str, conteos: dict[str, int], tope: int = 3) -> str:
    """
    El mensaje del 409: qué tiene, y qué hacer en vez de borrarlo.

    Se nombran los tres rastros más grandes y el resto se resume. Una lista
    de quince renglones no la lee nadie, y lo que hay que decidir se decide
    con los primeros.
    """
    ordenados = sorted(conteos.items(), key=lambda par: par[1], reverse=True)
    frases = [_frase(tabla, cuantas) for tabla, cuantas in ordenados[:tope]]
    if len(ordenados) > tope:
        frases.append(f"y {len(ordenados) - tope} cosa(s) más")

    return (
        f"No se puede eliminar a {nombre}: tiene {', '.join(frases)}. "
        "Borrarlo dejaría el historial sin el nombre de quien hizo cada cosa. "
        "Desactívalo: no podrá entrar al portal y todo su trabajo queda como está."
    )
