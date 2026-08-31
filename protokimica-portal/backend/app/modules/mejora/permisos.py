"""
Quién ve y quién mueve una OMP.

Mismo criterio que el resto del portal: **el rol decide a qué módulo entras;
el área decide qué ves dentro.** Un líder de Logística no tiene por qué ver
las oportunidades de Calidad, igual que no ve sus indicadores.
"""
from fastapi import HTTPException

from app.core.areas import AREAS
from app.models.user import User

# Quién valida un cierre. En el formato del SGC los cierres reales dicen «se
# validó con el SGC y se puede dar por cerrada»: es un paso de aprobación,
# no un campo de texto, y por eso queda con nombre y fecha.
#
# Va por ÁREA y no por rol, como el cierre de PQRS: Calidad ya existe como
# área y se administra desde Admin › Usuarios, sin un rol paralelo que pueda
# contradecirla. Se toma de la lista y no se escribe a mano — si cambia cómo
# se escribe el área, esto tiene que moverse con ella o nadie podrá validar.
AREA_SGC = "Calidad"
assert AREA_SGC in AREAS, (
    f"'{AREA_SGC}' ya no está en app/core/areas.py. Actualiza esta constante "
    "o nadie podrá validar el cierre de una oportunidad de mejora."
)

# Gerencia ve todo el portal sin límite de área, pero no modifica nada: solo
# lee y comenta. Es la misma regla que en Indicadores y Master Planner.
ROLES_QUE_VEN_TODO = ("admin", "gerencia")

# Quién puede abrir, mover y cerrar una OMP. Los líderes manejan la mejora de
# su área — hoy lo hacen en un Excel, así que el portal no puede pedir menos
# autonomía de la que ya tienen.
ROLES_QUE_GESTIONAN = ("admin", "lider")


def ve_todas(usuario: User) -> bool:
    return usuario.rol in ROLES_QUE_VEN_TODO


def puede_gestionar(usuario: User) -> bool:
    return usuario.rol in ROLES_QUE_GESTIONAN


def aplicar_filtro_area(query, usuario: User, modelo):
    """
    Recorta la consulta a lo que esta persona puede ver.

    Las que no tienen área asignada las ve todo el mundo: son de la empresa,
    no de un área, y esconderlas haría que nadie las trabajara.
    """
    if ve_todas(usuario):
        return query
    return query.filter(
        (modelo.area == usuario.area) | (modelo.area.is_(None))
    )


def es_sgc(usuario: User) -> bool:
    """Admin siempre puede: es quien destraba cuando Calidad está de vacaciones."""
    return usuario.rol == "admin" or usuario.area == AREA_SGC


def exigir_sgc(usuario: User) -> None:
    if not es_sgc(usuario):
        raise HTTPException(
            status_code=403,
            detail=(
                f"Solo el área de {AREA_SGC} valida el cierre de una oportunidad. "
                "Cuando el plan esté cumplido y verificado, pídele a Calidad que "
                "la revise para poderla cerrar."
            ),
        )


def exigir_puede_gestionar(usuario: User) -> None:
    if not puede_gestionar(usuario):
        raise HTTPException(
            status_code=403,
            detail=(
                "Solo los líderes de área y los administradores manejan las "
                "oportunidades de mejora. Si necesitas abrir una, pídeselo al "
                "líder de tu área."
            ),
        )


def exigir_acceso(oportunidad, usuario: User):
    """
    Devuelve la OMP si esta persona puede verla, o 404 si no.

    Se responde **404 y no 403**, igual que en Master Planner: un 403
    confirmaría que existe una oportunidad de otra área y con qué número.
    """
    if oportunidad is None:
        raise HTTPException(status_code=404, detail="Oportunidad de mejora no encontrada.")

    if ve_todas(usuario) or oportunidad.area is None or oportunidad.area == usuario.area:
        return oportunidad

    raise HTTPException(status_code=404, detail="Oportunidad de mejora no encontrada.")
