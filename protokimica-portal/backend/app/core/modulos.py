"""
Qué módulos puede abrir cada quien.

Hasta ahora el portal solo controlaba la ESCRITURA (`solo_lectura_no`) y la
visibilidad por área dentro de Master Planner. Cualquier usuario autenticado
podía leer cualquier módulo — un agente de Logística veía todos los
indicadores de la empresa.

Esto se aplica en el backend, no escondiendo el menú: esconder un botón no
impide escribir la URL a mano.

Regla general: **el rol decide a qué módulo entras, el área decide qué ves
dentro.** Un líder entra a Indicadores, pero solo ve los de su área.

**Y antes que el rol, el contrato.** El portal se vende por módulos: una
empresa abre solo los que tiene en `tenant_modulos` (ver `CONTRATABLES`), y
para un módulo que no contrató nadie entra, ni siquiera `admin`. La base
—Inicio y Administración— viene con cualquier portal.
"""
from fastapi import Depends, HTTPException, status

from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.models.tenant import Tenant, TenantModulo
from app.models.user import User

# modulo -> roles que pueden abrirlo. `admin` va en todos por definición.
ACCESO_POR_MODULO: dict[str, set[str]] = {
    "inicio": {"admin", "gerencia", "lider", "agente", "lectura"},
    "pqrs": {"admin", "gerencia", "lider", "agente", "lectura"},
    # Entra cualquiera: qué puede hacer adentro lo deciden las capacidades
    # (`core/capacidades.py`), no el rol.
    "notas_credito": {"admin", "gerencia", "lider", "agente", "lectura"},
    "master_planner": {"admin", "gerencia", "lider", "agente", "lectura"},
    # Un agente organiza su trabajo en PQRS y Master Planner; los indicadores
    # son de quien responde por ellos. El líder entra porque le toca registrar
    # los de su área cada mes.
    "indicadores": {"admin", "gerencia", "lider"},
    # La mejora es trabajo de los líderes de área: son quienes responden por
    # que un indicador vuelva a su meta. Gerencia queda fuera a propósito —
    # el avance de las oportunidades se le reporta, no se le deja abierto
    # como un tablero más que mirar. `admin` entra porque administra el
    # portal, no porque gestione mejoras.
    "mejora": {"admin", "lider"},
    # Las encuestas quedan abiertas como PQRS: la satisfacción del cliente la
    # consulta cualquiera que atienda. Si un día hay que cerrarlas, se cambia
    # aquí y no en veinte endpoints.
    "encuestas": {"admin", "gerencia", "lider", "agente", "lectura"},
    "admin": {"admin"},
}

ETIQUETAS = {
    "inicio": "Inicio",
    "pqrs": "PQRS",
    "notas_credito": "Notas crédito",
    "master_planner": "Master Planner",
    "indicadores": "Indicadores",
    "mejora": "Oportunidades de Mejora",
    "encuestas": "Encuestas",
    "admin": "Administración",
}


# ── Lo que se vende ───────────────────────────────────────────
#
# Cada módulo contratable trae los paquetes de `app/modules` que lo componen
# (`core/registro.py` reúne sus piezas solo si están contratados) y los que
# necesita para funcionar. Las dependencias son las mismas que declara
# `tests/test_modularidad.py`: si una cambia allá, cambia aquí.

BASE = ("inicio", "admin")

CONTRATABLES: dict[str, dict] = {
    "pqrs": {
        "nombre": "PQRS y atención al cliente",
        # Una autorización se pide sobre una PQRS, y el producto de una PQRS
        # se confirma contra el catálogo: se venden juntos.
        "paquetes": ("pqrs", "autorizaciones", "catalogo"),
        "requiere": (),
    },
    "notas_credito": {
        "nombre": "Notas crédito",
        "paquetes": ("notas_credito",),
        "requiere": (),
    },
    "master_planner": {
        "nombre": "Master Planner (proyectos y actividades)",
        "paquetes": ("master_planner",),
        "requiere": (),
    },
    "indicadores": {
        "nombre": "Indicadores de gestión",
        "paquetes": ("indicadores",),
        "requiere": (),
    },
    "mejora": {
        "nombre": "Oportunidades de mejora (OMP)",
        "paquetes": ("mejora",),
        # Una OMP nace de un indicador y se verifica contra su medición.
        "requiere": ("indicadores",),
    },
    "encuestas": {
        "nombre": "Encuestas",
        "paquetes": ("encuestas",),
        "requiere": (),
    },
}

# paquete de app/modules -> módulo contratable al que pertenece
CONTRATABLE_DE_PAQUETE = {
    paquete: clave for clave, cfg in CONTRATABLES.items() for paquete in cfg["paquetes"]
}


def contratados_de(tenant: Tenant | None) -> set[str]:
    """
    Los módulos que la empresa puede abrir: la base más los contratados.

    Un contratado cuya dependencia no está contratada no cuenta: Mejora sin
    Indicadores tendría el botón de verificar contra un indicador que no
    existe. `contratar()` no deja llegar a ese estado, pero apagar
    Indicadores a mano en la base sí, y entonces vale lo que diga aquí.
    """
    tenant_mods = tenant.modulos_contratados if tenant else set()
    activos = {
        m for m in tenant_mods
        if m in CONTRATABLES and all(r in tenant_mods for r in CONTRATABLES[m]["requiere"])
    }
    return set(BASE) | activos


def paquete_contratado(tenant: Tenant | None, paquete: str) -> bool:
    """¿Este paquete de `app/modules` está contratado? Los de plataforma siempre."""
    clave = CONTRATABLE_DE_PAQUETE.get(paquete)
    return clave is None or clave in contratados_de(tenant)


def esta_contratado(usuario: User, modulo: str) -> bool:
    return modulo in contratados_de(usuario.tenant)


def contratar(db: Session, tenant_id: int, modulos: list[str] | tuple[str, ...]) -> list[str]:
    """
    Le activa módulos a una empresa, con lo que requieran. Devuelve los que
    quedaron activos de nuevo. No hace commit: lo decide quien llama.
    """
    pendientes = list(modulos)
    activados: list[str] = []
    while pendientes:
        clave = pendientes.pop(0)
        if clave not in CONTRATABLES:
            raise ValueError(
                f"«{clave}» no es un módulo que se pueda contratar. "
                f"Los que hay: {', '.join(CONTRATABLES)}."
            )
        pendientes.extend(r for r in CONTRATABLES[clave]["requiere"] if r not in activados)
        fila = db.query(TenantModulo).filter_by(tenant_id=tenant_id, modulo=clave).first()
        if fila is None:
            db.add(TenantModulo(tenant_id=tenant_id, modulo=clave, activo=True))
            activados.append(clave)
        elif not fila.activo:
            fila.activo = True
            activados.append(clave)
    db.flush()
    return activados


def puede_ver_modulo(usuario: User, modulo: str) -> bool:
    permitidos = ACCESO_POR_MODULO.get(modulo)
    if permitidos is None:
        raise ValueError(f"Módulo desconocido: '{modulo}'")
    return usuario.rol in permitidos and esta_contratado(usuario, modulo)


def _no_contratado(modulo: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=(
            f"Tu empresa no tiene contratado el módulo de {ETIQUETAS.get(modulo, modulo)}. "
            "Si lo necesitan, pídanlo a quien administra el portal."
        ),
    )


def contratado(modulo: str):
    """
    Dependencia de FastAPI que corta un router entero si la empresa del
    usuario no tiene el módulo. Va en el `APIRouter(dependencies=[...])` de
    cada router del módulo, para que un endpoint nuevo quede cubierto el día
    que se escribe sin que nadie tenga que acordarse.

    Solo mira el contrato; el rol lo sigue mirando `requiere_modulo`.
    """
    def verificar(current_user: User = Depends(get_current_user)) -> None:
        if not esta_contratado(current_user, modulo):
            raise _no_contratado(modulo)
    return verificar


def modulos_de(usuario: User) -> list[str]:
    """Los módulos que este usuario puede abrir, en orden de menú."""
    return [m for m in ACCESO_POR_MODULO if puede_ver_modulo(usuario, m)]


def requiere_modulo(modulo: str):
    """
    Dependencia de FastAPI: corta el acceso a un módulo completo.

    Uso:  _: User = Depends(requiere_modulo("indicadores"))
    """
    def verificar(current_user: User = Depends(get_current_user)) -> User:
        if not esta_contratado(current_user, modulo):
            raise _no_contratado(modulo)
        if not puede_ver_modulo(current_user, modulo):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Tu rol no tiene acceso al módulo de {ETIQUETAS.get(modulo, modulo)}. "
                    "Si necesitas entrar, solicítalo a un administrador."
                ),
            )
        return current_user
    return verificar


# ── Alcance dentro de Indicadores ─────────────────────────────

def ve_todos_los_indicadores(usuario: User) -> bool:
    """
    Gerencia y admin ven la empresa completa. Un líder ve los indicadores de
    su área: son los que le toca responder y registrar.
    """
    return usuario.rol in ("admin", "gerencia")
