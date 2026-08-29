"""
Quién puede responder una autorización.

**Manda el ÁREA, no el rol.** Quien trabaja en Aseguramiento sabe autorizar
lo de Aseguramiento, sea líder o agente; y un líder de otra área no tiene por
qué opinar sobre eso. Amarrarlo al cargo dejaba fuera a la gente que hace el
trabajo y obligaba a cambiarle el rol a alguien solo para que pudiera firmar.

Es el mismo criterio que ya rige en el resto del portal: cerrar y reclasificar
una PQRS es del área Servicio al Cliente, aprobar presupuesto es de
Administración y pagar es de Tesorería. Todos por área.

Quién NO puede, aunque el área coincida: `lectura` y `gerencia`. Eso no se
decide aquí sino con `solo_lectura_no` en el endpoint, que es la dependencia
que protege toda escritura del portal.
"""
from app.models.user import User


def puede_responder(usuario: User, area_autorizadora: str | None) -> bool:
    """
    ¿Esta persona puede aprobar o rechazar una autorización de esa área?

    `admin` siempre puede: es quien destraba las cosas cuando el responsable
    está de vacaciones o alguien quedó mal configurado.
    """
    if usuario.rol == "admin":
        return True
    if not area_autorizadora:
        # Un tipo de autorización sin área definida no lo puede responder
        # nadie más que un admin: sería una firma sin dueño.
        return False
    return usuario.area == area_autorizadora
