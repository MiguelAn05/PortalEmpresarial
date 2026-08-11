"""
Qué alcance de indicadores puede ver cada quien.

Una sola función decide esto para todo el módulo. Si la regla quedara
repartida entre el router, las consultas y el frontend, el día que se agregue
un rol habría que acordarse de tres sitios — y el que se olvide es el que
termina mostrándole a alguien números que no le corresponden.

El frontend no decide nada: pregunta al backend si puede cambiar de alcance
y pinta el interruptor solo si la respuesta es que sí.
"""
from app.models.user import User

# Ven TODAS las áreas. `gerencia` está aquí porque su trabajo es mirar la
# empresa completa; que no pueda modificar nada se resuelve aparte, con
# solo_lectura_no en los endpoints de escritura.
ROLES_QUE_VEN_LA_EMPRESA = {"admin", "gerencia"}

EMPRESA = "empresa"
AREA = "area"


def puede_ver_la_empresa(usuario: User) -> bool:
    return usuario.rol in ROLES_QUE_VEN_LA_EMPRESA


def resolver_alcance(usuario: User, pedido: str | None) -> str:
    """
    El alcance que de verdad se va a aplicar.

    A quien solo le corresponde su área se le devuelve "area" aunque pida
    "empresa": se ignora en silencio en vez de responder un error, porque
    no es un intento de saltarse nada — es un enlace guardado, un refresco
    con la URL vieja o el interruptor de alguien que cambió de rol.

    Sin área asignada y sin permiso de empresa no hay nada que mostrar; eso
    lo resuelve `area_a_filtrar` devolviendo un filtro que no trae nada.
    """
    if not puede_ver_la_empresa(usuario):
        return AREA
    return AREA if pedido == AREA else EMPRESA


def area_a_filtrar(usuario: User, alcance: str) -> str | None:
    """
    El área por la que hay que filtrar, o None para no filtrar (toda la
    empresa). Se pasa tal cual a `construir_tablero`.
    """
    return None if alcance == EMPRESA else usuario.area
