"""
Lo que un módulo le aporta a la página de Inicio.

Inicio arma una sola respuesta con piezas de varios módulos: los pendientes
de la persona, las cifras de titular de la empresa y el estado del área de
un líder. Antes las calculaba todas él mismo leyendo las tablas de PQRS,
Master Planner e Indicadores, así que no podía instalarse sin los tres.

Ahora cada módulo declara `APORTE = AporteInicio(...)` en su `inicio.py` y
Inicio solo los reúne (ver `core/registro.py`). Un módulo que no está
instalado no aporta, y su tarjeta no llega.

Aquí viven también las reglas que comparten todas las piezas —cuándo algo
«está por vencer», cuántos se listan—, para que la misma tarea no salga
urgente en una tarjeta y tranquila en otra.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.models.user import User

# Cuántos días antes se considera que algo "está por vencer". Igual que en
# Master Planner, para que la misma tarea no salga como urgente en un sitio
# y tranquila en otro.
DIAS_AVISO = 3

# Cuántos elementos se listan por tarjeta. El inicio es un titular con
# enlaces, no la vista completa: para eso está cada módulo.
TOPE_LISTA = 5

MESES_CORTOS = [
    "Ene", "Feb", "Mar", "Abr", "May", "Jun",
    "Jul", "Ago", "Sep", "Oct", "Nov", "Dic",
]


def ahora() -> datetime:
    return datetime.now(timezone.utc)


def meses_hacia_atras(cuantos: int) -> list[tuple[int, int]]:
    """Los últimos N periodos (año, mes), del más viejo al más nuevo."""
    hoy = ahora()
    anio, mes = hoy.year, hoy.month
    periodos = []
    for _ in range(cuantos):
        periodos.append((anio, mes))
        mes -= 1
        if mes == 0:
            mes, anio = 12, anio - 1
    return list(reversed(periodos))


def inicio_del_mes(momento: datetime) -> datetime:
    return momento.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


@dataclass(frozen=True)
class Pendientes:
    """
    Una tarjeta de la bandeja de la persona.

    `urgentes` y `por_atender` cuentan lo que esa tarjeta suma a los totales
    de arriba: el primero decide si la bandeja sale en rojo, el segundo es el
    total de cosas que reclaman atención.
    """
    clave: str
    calcular: Callable[[Session, User], Any]
    urgentes: Callable[[Any], int] = lambda valor: 0
    por_atender: Callable[[Any], int] = lambda valor: 0


@dataclass(frozen=True)
class AporteInicio:
    # Tarjetas de la bandeja personal.
    pendientes: tuple[Pendientes, ...] = field(default_factory=tuple)
    # Cifras del titular de la empresa (admin, gerencia, líderes). Recibe el
    # momento de la consulta para que todas las piezas corten el mes igual.
    titular: Callable[[Session, User, datetime], dict] | None = None
    # Lo que el módulo dice del área de un líder. Recibe los ids de su equipo.
    mi_area: Callable[[Session, User, list[int], datetime], dict] | None = None


def bandeja(vencidas: list, por_vencer: list, abiertas: int) -> dict:
    """La forma común de una tarjeta de pendientes con plazo."""
    return {
        "abiertas": abiertas,
        "vencidas": len(vencidas),
        "por_vencer": len(por_vencer),
        "lista": (vencidas + por_vencer)[:TOPE_LISTA],
    }


def urgentes_de_bandeja(valor: dict) -> int:
    return valor["vencidas"]


def por_atender_de_bandeja(valor: dict) -> int:
    return valor["vencidas"] + valor["por_vencer"]
