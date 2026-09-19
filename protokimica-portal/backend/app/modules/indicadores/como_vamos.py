"""
La portada gerencial: "¿cómo vamos?" en una pantalla.

Responde cuatro preguntas, en este orden:
  1. ¿Cómo está la empresa este mes?   → resumen (con el delta del mes pasado)
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
    areas_a_filtrar, puede_ver_la_empresa, resolver_alcance,
)
from app.modules.indicadores.service import MESES, construir_tablero

# Peor primero. Es el orden en que hay que leer un tablero: lo que arde
# arriba, y "sin datos" antes que lo que está bien, porque un indicador que
# nadie reportó es un problema aunque no sea un incumplimiento.
GRAVEDAD = {"rojo": 0, "sin_datos": 1, "amarillo": 2, "verde": 3}


def _empeoro(semaforo_antes: str, semaforo_ahora: str) -> bool:
    return GRAVEDAD[semaforo_ahora] < GRAVEDAD[semaforo_antes]


def cumplimiento_del_mes_anterior(fichas: list[dict]) -> float | None:
    """
    El mismo porcentaje del mes pasado, para poder decir si subió o bajó.

    Un cumplimiento suelto no se interpreta: un 92,9% puede ser una buena
    noticia o el cuarto mes cayendo, y desde la cifra sola no hay manera de
    saberlo. Se resuelve aquí, como todo lo demás: si el frontend restara
    los dos números, tarde o temprano diría algo distinto del reporte.

    Sale de `semaforo_mes_anterior`, que cada ficha ya trae, así que no
    cuesta ni una consulta más. La regla es la MISMA del mes actual —solo
    cuentan los que tienen juicio posible— porque comparar dos porcentajes
    calculados distinto no compara nada.
    """
    verde = sum(1 for f in fichas if f["semaforo_mes_anterior"] == "verde")
    con_juicio = sum(
        1 for f in fichas
        if f["semaforo_mes_anterior"] in ("verde", "amarillo", "rojo")
    )
    return round((verde / con_juicio) * 100, 1) if con_juicio else None


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

    Cada fila lleva además su RESPONSABLE y su FUENTE. El responsable, para
    poder buscar por persona —«qué le falta a Hoover» es la pregunta que se
    hace al cerrar el mes, y sin el dato habría que abrir uno por uno—. La
    fuente, para poder agrupar: los «Gestión de OMP» son uno por área y
    ocupan veinte filas que nadie lee de a una; con la fuente, la pantalla
    las pliega en un solo renglón.
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
            "responsable_nombre": f.get("responsable_nombre"),
            "fuente_automatica": f.get("fuente_automatica"),
            # Una fila sin un solo mes reportado en todo el año no es lo
            # mismo que una con huecos: o el indicador se dejó de medir, o
            # nadie lo reclamó nunca. La pantalla las agrupa aparte y lo
            # dice, en vez de dejar veinte renglones de guiones.
            "sin_registros": all(m["valor"] is None for m in meses),
            "meses": meses,
        })
    return filas


def construir_como_vamos(db: Session, tenant_id: int, anio: int, mes: int,
                         usuario: User, alcance_pedido: str | None = None,
                         area: str | None = None) -> dict:
    """La portada completa, lista para pintar sin que el frontend calcule nada."""
    alcance = resolver_alcance(usuario, alcance_pedido)

    # El alcance es el LÍMITE y el área es la elección. Se intersecan, nunca
    # se reemplazan: mandar un `?area=` ajeno no abre nada que el alcance no
    # permitiera ya, que es la misma regla del tablero.
    permitidas = areas_a_filtrar(usuario, alcance)
    if area:
        permitidas = [area] if permitidas is None or area in permitidas else []

    tablero = construir_tablero(db, tenant_id, anio, mes, areas=permitidas)
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
        "resumen": {
            **tablero["resumen"],
            "cumplimiento_pct_anterior": (anterior := cumplimiento_del_mes_anterior(fichas)),
            "delta_cumplimiento": (
                None if anterior is None or tablero["resumen"]["cumplimiento_pct"] is None
                else round(tablero["resumen"]["cumplimiento_pct"] - anterior, 1)
            ),
            "mes_anterior_nombre": MESES[(mes + 10) % 12],
        },
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
        # El catálogo del selector sale de aquí y no de una segunda petición:
        # una pantalla que tiene que pedir dos cosas para pintar una barra de
        # filtros muestra la barra a medias mientras llega la otra.
        "areas_disponibles": tablero["areas_disponibles"],
    }
