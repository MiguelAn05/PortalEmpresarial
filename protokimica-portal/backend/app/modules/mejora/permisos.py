"""
Quién ve y quién mueve una OMP.

Mismo criterio que el resto del portal: **el rol decide a qué módulo entras;
el área decide qué ves dentro.** Un líder de Logística no tiene por qué ver
las oportunidades de Calidad, igual que no ve sus indicadores.
"""
from fastapi import HTTPException

from app.models.user import User

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
