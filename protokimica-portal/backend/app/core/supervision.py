"""
Qué áreas ve cada persona: la suya y las que supervisa.

El portal filtra por área EXACTA en Indicadores, Mejora, Master Planner e
Inicio. Eso funciona mientras cada quien responde por una sola área, y se
rompe con una dirección que responde por varias: el director de Dirección
Técnica no vería nada de IDI ni de Salvak, que es justamente su trabajo.

**La supervisión es de una sola vía.** El jefe ve hacia abajo; el equipo
sigue viendo solo su área, así que la gestión de la dirección no se le
muestra. Quién supervisa qué se administra en Admin › Usuarios y vive en
`usuario_areas_supervisadas` — no en una jerarquía escrita en el código,
para que crear una jefatura no pida un despliegue.

Esta es la ÚNICA fuente de esa regla. Si cada módulo armara su propia lista,
el día que se agregue otro tipo de jefatura habría que acordarse de todos, y
el que se olvide es el que le esconde a alguien lo que le toca ver.
"""
from app.models.user import User


def areas_visibles(usuario: User) -> list[str]:
    """
    El área propia más las supervisadas, sin repetir y sin vacíos.

    Puede venir vacía: alguien sin área y sin supervisión no tiene ámbito, y
    los filtros lo tratan como «no ve nada de área» en vez de «lo ve todo».
    """
    areas = [usuario.area] if usuario.area else []
    for area in usuario.areas_que_supervisa:
        if area and area not in areas:
            areas.append(area)
    return areas


def supervisa(usuario: User, area: str | None) -> bool:
    """¿Esta área le corresponde a esta persona, por propia o por supervisión?"""
    return bool(area) and area in areas_visibles(usuario)


def condicion_area(columna, usuario: User):
    """
    Condición SQLAlchemy para acotar una consulta a sus áreas.

    Se usa `in_` incluso con una sola área: así el mismo código sirve para
    quien supervisa y para quien no, sin dos caminos que puedan divergir.
    """
    return columna.in_(areas_visibles(usuario))
