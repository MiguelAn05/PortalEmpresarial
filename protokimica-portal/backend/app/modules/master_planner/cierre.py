"""
Cierre de proyectos: finalizar, cancelar y retomar.

Un proyecto sin cierre formal nunca se sabe si terminó o si todos se
olvidaron de él. Aquí se resuelve qué queda registrado cuando pasa una de
las dos cosas, y qué números se congelan en el acta.

Finalizar y cancelar son operaciones distintas a propósito: la primera dice
"se cumplió", la segunda "se abandona". Guardarlas como el mismo estado haría
que un proyecto que nadie sacó adelante contara igual que uno cumplido.
"""
from datetime import datetime, timezone

from app.models.master_planner import CierreProyecto, Proyecto
from app.models.user import User

FINALIZADO = "finalizado"
CANCELADO = "cancelado"
TIPOS = {FINALIZADO, CANCELADO}

# En qué estado queda el proyecto según cómo se cerró.
ESTADO_SEGUN_TIPO = {FINALIZADO: "cerrado", CANCELADO: "cancelado"}


def _aware(f):
    """Postgres devuelve fechas con zona y SQLite sin ella; restarlas revienta."""
    if f is None:
        return None
    return f if f.tzinfo else f.replace(tzinfo=timezone.utc)


def _dias_de_duracion(proyecto: Proyecto, cierre: datetime) -> int | None:
    inicio = _aware(proyecto.fecha_inicio)
    if not inicio:
        return None
    return max(0, (_aware(cierre) - inicio).days)


def foto_de_los_numeros(proyecto: Proyecto, momento: datetime) -> dict:
    """
    Los números tal como están AHORA, para congelarlos en el acta.

    Se guardan en vez de calcularse al abrir el acta porque un acta dice lo
    que era verdad el día que se firmó. Si alguien corrige un pago viejo el
    año entrante, el acta no puede cambiar sola.
    """
    return {
        "tareas_total": proyecto.total_tareas,
        "tareas_completadas": proyecto.tareas_completadas,
        "presupuesto_planeado": proyecto.presupuesto_total,
        "presupuesto_aprobado": proyecto.presupuesto_aprobado,
        "presupuesto_pagado": proyecto.presupuesto_pagado,
        "dias_de_duracion": _dias_de_duracion(proyecto, momento),
    }


def validar(tipo: str, motivo: str | None, proyecto: Proyecto) -> None:
    """Lo que no se puede dejar pasar. Los mensajes dicen qué hacer."""
    if tipo not in TIPOS:
        raise ValueError(
            f"Tipo de cierre inválido: «{tipo}». Usa «{FINALIZADO}» o «{CANCELADO}»."
        )

    if tipo == CANCELADO and not (motivo or "").strip():
        raise ValueError(
            "Para cancelar un proyecto hay que explicar por qué. "
            "Ese texto es lo único que va a quedar para entender la decisión."
        )

    if proyecto.cierre_vigente is not None:
        estado = "finalizado" if proyecto.cierre_vigente.tipo == FINALIZADO else "cancelado"
        raise ValueError(
            f"Este proyecto ya está {estado}. Si hay que volver a trabajarlo, "
            "usa «Retomar proyecto» y ciérralo de nuevo cuando corresponda."
        )


def cerrar(proyecto: Proyecto, usuario: User, tipo: str,
           entregables: str | None = None, motivo: str | None = None,
           observaciones: str | None = None, evidencia: str | None = None
           ) -> CierreProyecto:
    """Crea el acta y deja el proyecto en el estado que corresponde."""
    validar(tipo, motivo, proyecto)

    ahora = datetime.now(timezone.utc)
    acta = CierreProyecto(
        proyecto_id=proyecto.id,
        tipo=tipo,
        entregables=(entregables or "").strip() or None,
        motivo=(motivo or "").strip() or None,
        observaciones=(observaciones or "").strip() or None,
        evidencia=evidencia,
        cerrado_por=usuario.id,
        cerrado_en=ahora,
        **foto_de_los_numeros(proyecto, ahora),
    )

    proyecto.estado = ESTADO_SEGUN_TIPO[tipo]
    # La fecha de fin real es cuándo dejó de trabajarse, sin importar si
    # terminó bien o se abandonó: en los dos casos el proyecto paró ese día.
    proyecto.fecha_fin_real = ahora
    # Sale de las vistas del día a día, pero no se borra nada. Es el mismo
    # mecanismo que ya existía para archivar.
    proyecto.archivado = True

    return acta


def retomar(proyecto: Proyecto, usuario: User) -> CierreProyecto:
    """
    Devuelve el proyecto a ejecución y ANULA su acta, sin borrarla.

    El rastro de que estuvo cancelado y por qué es justo lo que alguien busca
    cuando pregunta "¿este proyecto no se había caído?".
    """
    acta = proyecto.cierre_vigente
    if acta is None:
        raise ValueError(
            "Este proyecto no está cerrado ni cancelado, así que no hay nada que retomar."
        )

    acta.anulado_en = datetime.now(timezone.utc)
    acta.anulado_por = usuario.id

    proyecto.estado = "en_ejecucion"
    proyecto.fecha_fin_real = None
    proyecto.archivado = False

    return acta


def acta_a_dict(acta: CierreProyecto) -> dict:
    return {
        "id": acta.id,
        "tipo": acta.tipo,
        "entregables": acta.entregables,
        "motivo": acta.motivo,
        "observaciones": acta.observaciones,
        "evidencia": acta.evidencia,
        "resumen": {
            "tareas_total": acta.tareas_total,
            "tareas_completadas": acta.tareas_completadas,
            "presupuesto_planeado": float(acta.presupuesto_planeado or 0),
            "presupuesto_aprobado": float(acta.presupuesto_aprobado or 0),
            "presupuesto_pagado": float(acta.presupuesto_pagado or 0),
            "dias_de_duracion": acta.dias_de_duracion,
        },
        "cerrado_por_nombre": acta.cerrado_por_nombre,
        "cerrado_en": acta.cerrado_en,
        "anulado_en": acta.anulado_en,
        "anulado_por_nombre": acta.anulado_por_nombre,
        "vigente": acta.vigente,
    }
