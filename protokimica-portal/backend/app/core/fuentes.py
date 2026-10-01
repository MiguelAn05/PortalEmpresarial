"""
El contrato de una fuente automática de indicador.

Cada módulo declara las suyas en `modules/<modulo>/fuentes_indicador.py` y
el módulo de Indicadores las reúne (ver `core/registro.py`). Aquí vive solo
lo que todas comparten: qué devuelve un cálculo y cómo se arma una
proporción, para que una fuente de PQRS y una del Master Planner digan «sin
datos» de la misma manera.

Un módulo declara:

- `FUENTES`: `{clave: {"nombre", "modulo", "descripcion", "formula",
  "unidad", "direccion", "fn", ...}}`. Opcionales: `"por_area": True` (exige
  el área del indicador), `"acepta_area": True` (la usa si la hay) y
  `"una_por_area": {...}` (se crea en todas las áreas con un botón; lleva
  el nombre y la meta sugerida).
- `DINAMICAS` (opcional): fuentes que dependen de lo que exista en la base
  —las encuestas que alguien creó— y por eso no se pueden escribir de
  antemano. Ver `FuentesDinamicas`.
"""
from calendar import monthrange
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from sqlalchemy.orm import Session


@dataclass
class Resultado:
    """
    Un cálculo automático. `denominador` en 0 significa que en ese mes no hubo
    nada que medir — no es lo mismo que un cero real, y el tablero lo muestra
    como "sin datos" en vez de como un incumplimiento.
    """
    valor: float | None
    numerador: float | None = None
    denominador: float | None = None
    detalle: str | None = None


def rango_mes(anio: int, mes: int) -> tuple[datetime, datetime]:
    ultimo_dia = monthrange(anio, mes)[1]
    return (
        datetime(anio, mes, 1, tzinfo=timezone.utc),
        datetime(anio, mes, ultimo_dia, 23, 59, 59, tzinfo=timezone.utc),
    )


def proporcion(numerador: int, denominador: int, detalle: str) -> Resultado:
    if not denominador:
        return Resultado(valor=None, numerador=0, denominador=0, detalle="Sin datos en el periodo")
    return Resultado(
        valor=round((numerador / denominador) * 100, 2),
        numerador=numerador, denominador=denominador, detalle=detalle,
    )


@dataclass(frozen=True)
class FuentesDinamicas:
    """
    Fuentes cuyas claves empiezan por `prefijo + ":"` y que el módulo resuelve
    consultando la base, no un diccionario escrito a mano.
    """
    prefijo: str
    # (db, tenant_id) -> las fuentes disponibles, ya en forma pública
    listar: Callable[[Session, int], list[dict]]
    # (clave, db, tenant_id, anio, mes) -> Resultado; ValueError si no existe
    calcular: Callable[[str, Session, int, int, int], Resultado]
    # (clave, db, tenant_id) -> ¿se puede calcular?
    existe: Callable[[str, Session, int], bool]

    def es_suya(self, clave: str) -> bool:
        return clave.startswith(self.prefijo + ":")
