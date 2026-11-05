"""
Quién ve qué en Marcaciones.

**El rol decide si entra al módulo; el alcance decide qué marcaciones ve.**
Entran admin, gerencia, líder y agente; `lectura` no (ver `core/modulos.py`).
Dentro, hay tres alcances, de mayor a menor:

- `todo`: admin, gerencia y quien tenga la capacidad `marcaciones.ver_todo`
  (Gestión Humana y TIC la traen de la migración). Ven todas las áreas.
- `areas`: el líder ve las de su área y las que supervisa
  (`core/supervision.areas_visibles`), igual que en Indicadores o Mejora.
- `propio`: el agente ve SOLO sus marcaciones. Se le reconoce por el correo:
  el de su usuario del portal es el mismo `correo` de la malla. Si no hay
  una persona de la malla con su correo, no ve nada —nunca «todo» por
  descarte—.

Nadie escribe desde la pantalla: las marcaciones y la malla llegan del script
del servidor de ZKBio, así que aquí no hay reglas de escritura que cuidar.
Esta es la ÚNICA fuente de la regla: el servicio la aplica antes de leer, no
después de traer todo.
"""
from dataclasses import dataclass, field

from app.core import capacidades
from app.core.deps import ROLES_VISION_TOTAL
from app.core.supervision import areas_visibles
from app.models.user import User

CAPACIDAD_VER_TODO = "marcaciones.ver_todo"


@dataclass(frozen=True)
class Alcance:
    tipo: str                      # "todo" | "areas" | "propio"
    areas: tuple[str, ...] = field(default_factory=tuple)
    correo: str | None = None

    def permite(self, area: str | None, correo: str | None = None) -> bool:
        if self.tipo == "todo":
            return True
        if self.tipo == "areas":
            return bool(area) and area in self.areas
        return bool(self.correo) and (correo or "").strip().lower() == self.correo


def alcance_de(usuario: User) -> Alcance:
    if usuario.rol in ROLES_VISION_TOTAL or capacidades.del_usuario(usuario, CAPACIDAD_VER_TODO):
        return Alcance("todo")
    if usuario.rol == "lider":
        return Alcance("areas", areas=tuple(areas_visibles(usuario)))
    return Alcance("propio", correo=(usuario.email or "").strip().lower())
