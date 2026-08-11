"""
La portada gerencial: "¿cómo vamos?" en una pantalla.

Responde cuatro preguntas, en este orden:
  1. ¿Cómo está la empresa este mes?   → resumen
  2. ¿Qué cambió?                       → movimientos
  3. ¿Qué área está peor?               → por_area
  4. ¿Y a lo largo del año?             → matriz

Se construye ENCIMA de `construir_tablero`, no en paralelo. Los conteos, el
cumplimiento por área y los pendientes salen de la misma función que alimenta
el tablero, así que las dos pantallas no pueden mostrar números distintos
para el mismo periodo. Lo único que se agrega aquí es lo que el tablero no
calculaba: qué cambió de semáforo y la vista del año en matriz.
"""
from datetime import date

from sqlalchemy.orm import Session

from app.models.user import User
from app.modules.indicadores.permisos import (
    area_a_filtrar, puede_ver_la_empresa, resolver_alcance,
)
from app.modules.indicadores.service import MESES, construir_tablero

# Peor primero. Es el orden en que hay que leer un tablero: lo que arde
# arriba, y "sin datos" antes que lo que está bien, porque un indicador que
# nadie reportó es un problema aunque no sea un incumplimiento.
GRAVEDAD = {"rojo": 0, "sin_datos": 1, "amarillo": 2, "verde": 3}


def _empeoro(semaforo_antes: str, semaforo_ahora: str) -> bool:
    return GRAVEDAD[semaforo_ahora] < GRAVEDAD[semaforo_antes]


def calcular_movimientos(fichas: list[dict]) -> list[dict]:
    """
    Los indicadores que CAMBIARON de semáforo contra el mes anterior.

    Es la sección más útil del tablero y la que casi ningún reporte trae:
    nadie necesita revisar los cuarenta indicadores cada mes, necesita ver
    los tres que se movieron. Lo que sigue igual no ocupa espacio.

    Se omiten los que no tenían dato antes y siguen sin tenerlo: eso no es
    un movimiento, es un pendiente de registro, y ya se reporta aparte.
    """
    movimientos = []
    for f in fichas:
        antes, ahora = f["semaforo_mes_anterior"], f["semaforo"]
        if antes == ahora:
            continue
        if antes == "sin_datos" and ahora == "sin_datos":
            continue

        movimientos.append({
            "id": f["id"],
            "nombre": f["nombre"],
            "area": f["area"],
            "unidad": f["unidad"],
            "semaforo": ahora,
            "semaforo_anterior": antes,
            "valor": f["valor"],
            "valor_anterior": f["valor_mes_anterior"],
            "variacion": f["variacion_mes"],
            "empeoro": _empeoro(antes, ahora),
        })

    # Lo que empeoró primero, y dentro de eso lo más grave.
    movimientos.sort(key=lambda m: (not m["empeoro"], GRAVEDAD[m["semaforo"]]))
    return movimientos


def construir_matriz(fichas: list[dict], anio: int, mes_corte: int) -> list[dict]:
    """
    Un año completo: indicadores en filas, meses en columnas.

    Muestra lo que ninguna gráfica de líneas deja ver de un vistazo — qué
    indicador lleva cuatro meses en rojo, o qué mes fue malo para todas las
    áreas a la vez.

    Distingue un mes SIN REPORTAR de uno que aún NO HA LLEGADO. Meterlos en
    la misma bolsa haría ver la empresa peor de lo que está: nadie incumplió
    por no haber reportado noviembre en agosto.
    """
    hoy = date.today()
    filas = []
    for f in fichas:
        meses = []
        for punto in f["serie"]:
            futuro = (anio > hoy.year) or (anio == hoy.year and punto["mes"] > mes_corte)
            meses.append({
                "mes": punto["mes"],
                "etiqueta": punto["etiqueta"],
                "valor": punto["valor"],
                "semaforo": "futuro" if futuro else punto["semaforo"],
            })
        filas.append({
            "id": f["id"],
            "nombre": f["nombre"],
            "area": f["area"],
            "unidad": f["unidad"],
            "meta": f["meta"],
            "direccion": f["direccion"],
            "meses": meses,
        })
    return filas


def construir_como_vamos(db: Session, tenant_id: int, anio: int, mes: int,
                         usuario: User, alcance_pedido: str | None = None) -> dict:
    """La portada completa, lista para pintar sin que el frontend calcule nada."""
    alcance = resolver_alcance(usuario, alcance_pedido)
    tablero = construir_tablero(
        db, tenant_id, anio, mes, area=area_a_filtrar(usuario, alcance),
    )
    fichas = tablero["indicadores"]

    return {
        "anio": anio,
        "mes": mes,
        "mes_nombre": MESES[mes - 1],
        "alcance": {
            "actual": alcance,
            # El frontend no decide quién ve qué: pinta el interruptor solo
            # si el backend dice que esta persona puede cambiarlo.
            "puede_cambiar": puede_ver_la_empresa(usuario),
            "area": usuario.area,
        },
        "resumen": tablero["resumen"],
        "movimientos": calcular_movimientos(fichas),
        "por_area": sorted(
            tablero["por_area"],
            # Lo que necesita atención primero: por rojos, luego por peor
            # cumplimiento. Un área al 80% con algo crítico pesa más que una
            # al 75% con todo en amarillo.
            key=lambda a: (-a["rojo"], a["cumplimiento_pct"] if a["cumplimiento_pct"] is not None else 101),
        ),
        "matriz": construir_matriz(fichas, anio, mes),
        "pendientes": tablero["pendientes"],
    }
