"""
Las reglas del ciclo de una OMP.

Aquí vive lo que hace que el módulo sirva para una auditoría y no sea una
lista de tareas con otro nombre: no se avanza sin causa raíz, y no se cierra
sin comparar el indicador contra el periodo que disparó la oportunidad.
"""
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.indicadores import Indicador, Medicion
from app.models.mejora import ESTADO_DESCARTADA, ESTADOS, Oportunidad

INTENTOS_CODIGO = 5


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


# ── Consecutivo ──────────────────────────────────────────────────────

def generar_codigo(db: Session, tenant_id: int) -> str:
    """
    OMP-{año}-{consecutivo}.

    Sale del MÁXIMO ya usado, nunca de un conteo: con OMP-2026-0001 y
    OMP-2026-0003 en la tabla —porque alguien borró la del medio— contar da 2
    y el siguiente saldría repetido, reventando contra el índice único. Es
    exactamente lo que pasó con los códigos de PQRS.
    """
    prefijo = f"OMP-{_ahora().year}-"
    codigos = (
        db.query(Oportunidad.codigo)
        .filter(Oportunidad.tenant_id == tenant_id,
                Oportunidad.codigo.isnot(None),
                Oportunidad.codigo.like(f"{prefijo}%"))
        .all()
    )
    mayor = 0
    for (codigo,) in codigos:
        sufijo = (codigo or "")[len(prefijo):]
        if sufijo.isdigit():
            mayor = max(mayor, int(sufijo))
    return f"{prefijo}{mayor + 1:04d}"


def asignar_codigo(db: Session, oportunidad: Oportunidad, tenant_id: int) -> str:
    """Le pone el código y reintenta si dos personas abrieron una a la vez."""
    for _ in range(INTENTOS_CODIGO):
        oportunidad.codigo = generar_codigo(db, tenant_id)
        try:
            db.commit()
            db.refresh(oportunidad)
            return oportunidad.codigo
        except IntegrityError:
            db.rollback()
            db.refresh(oportunidad)

    raise HTTPException(
        status_code=500,
        detail=("La oportunidad quedó registrada pero sin código. Avísale a un "
                "administrador; no la vuelvas a crear."),
    )


# ── El ciclo ─────────────────────────────────────────────────────────

def validar_transicion(oportunidad: Oportunidad, nuevo: str) -> None:
    """
    Deja pasar solo los cambios de estado que tienen sentido.

    No es burocracia: cada guarda evita un caso real. Sin causa raíz las
    acciones atacan el síntoma; sin verificación se cierra sin saber si
    funcionó, que es la observación clásica de una auditoría.
    """
    if nuevo == ESTADO_DESCARTADA:
        if oportunidad.estado == "cerrada":
            raise HTTPException(
                status_code=400,
                detail="Una oportunidad ya cerrada no se puede descartar.",
            )
        return

    if nuevo not in ESTADOS:
        raise HTTPException(
            status_code=400,
            detail=f"Estado inválido. Usa uno de: {', '.join(ESTADOS)}.",
        )

    if oportunidad.estado == "cerrada":
        raise HTTPException(
            status_code=400,
            detail=("Esta oportunidad ya está cerrada. Si el problema volvió, "
                    "abre una nueva: el historial de la anterior no se toca."),
        )

    if nuevo == "ejecucion" and not (oportunidad.causa_raiz or "").strip():
        raise HTTPException(
            status_code=400,
            detail=("Falta la causa raíz. Escríbela antes de pasar a ejecución: "
                    "sin ella las acciones atacan el síntoma y el indicador "
                    "vuelve a caer el mes siguiente."),
        )

    if nuevo == "verificacion" and not oportunidad.acciones:
        raise HTTPException(
            status_code=400,
            detail=("No hay acciones registradas. Agrega al menos una antes de "
                    "verificar: no hay nada cuya eficacia se pueda medir."),
        )

    if nuevo == "cerrada" and oportunidad.eficaz is None:
        raise HTTPException(
            status_code=400,
            detail=("Antes de cerrar hay que verificar si funcionó. Registra la "
                    "verificación de eficacia con el resultado del indicador."),
        )


def cambiar_estado(db: Session, oportunidad: Oportunidad, nuevo: str) -> Oportunidad:
    validar_transicion(oportunidad, nuevo)

    oportunidad.estado = nuevo
    if nuevo in ("cerrada", ESTADO_DESCARTADA):
        oportunidad.fecha_cierre = _ahora()
    else:
        oportunidad.fecha_cierre = None

    db.commit()
    db.refresh(oportunidad)
    return oportunidad


# ── Verificación de eficacia ─────────────────────────────────────────

def periodo_siguiente(anio: int, mes: int) -> tuple[int, int]:
    return (anio + 1, 1) if mes == 12 else (anio, mes + 1)


def medicion_de_verificacion(db: Session, oportunidad: Oportunidad):
    """
    La medición con la que se juzga si la OMP funcionó: la del mes siguiente
    al que la disparó.

    Devuelve None mientras no exista — y eso no es un error, es que todavía
    no se puede verificar. Es la diferencia entre pedirle a alguien que
    espere y hacerle creer que se le olvidó algo.
    """
    if not oportunidad.indicador_id or not oportunidad.periodo_anio:
        return None

    anio, mes = periodo_siguiente(oportunidad.periodo_anio, oportunidad.periodo_mes)
    return (
        db.query(Medicion)
        .filter(Medicion.indicador_id == oportunidad.indicador_id,
                Medicion.anio == anio, Medicion.mes == mes)
        .first()
    )


def evaluar_mejora(indicador: Indicador, valor_inicial, valor_nuevo) -> bool | None:
    """
    ¿El indicador mejoró?

    Depende de hacia dónde mejora: subir los reprocesos es malo y subir la
    satisfacción es bueno. Es la misma regla que usa el semáforo, no una
    interpretación nueva.
    """
    if valor_inicial is None or valor_nuevo is None or indicador is None:
        return None
    inicial, nuevo = float(valor_inicial), float(valor_nuevo)
    if nuevo == inicial:
        return False
    return nuevo > inicial if indicador.direccion == "arriba" else nuevo < inicial


def sugerir_verificacion(db: Session, oportunidad: Oportunidad) -> dict:
    """
    Lo que la pantalla necesita para proponer la verificación ya resuelta:
    el valor de antes, el de después y si eso es una mejora.

    El backend calcula y el frontend presenta: si la pantalla decidiera sola
    si un valor mejoró, tendría que conocer la dirección del indicador y
    tarde o temprano diría lo contrario que el semáforo.
    """
    medicion = medicion_de_verificacion(db, oportunidad)
    if medicion is None:
        anio = mes = None
        if oportunidad.periodo_anio:
            anio, mes = periodo_siguiente(oportunidad.periodo_anio, oportunidad.periodo_mes)
        return {
            "hay_medicion": False,
            "periodo_esperado": {"anio": anio, "mes": mes},
            "valor_inicial": oportunidad.valor_inicial,
            "valor_nuevo": None,
            "mejoro": None,
        }

    mejoro = evaluar_mejora(oportunidad.indicador, oportunidad.valor_inicial, medicion.valor)
    return {
        "hay_medicion": True,
        "periodo_esperado": {"anio": medicion.anio, "mes": medicion.mes},
        "valor_inicial": oportunidad.valor_inicial,
        "valor_nuevo": medicion.valor,
        "mejoro": mejoro,
    }


def registrar_verificacion(db: Session, oportunidad: Oportunidad,
                           eficaz: bool, nota: str | None,
                           valor_verificado=None) -> Oportunidad:
    """
    Deja constancia de si funcionó.

    Si NO fue eficaz la oportunidad vuelve a análisis en vez de cerrarse: el
    problema sigue ahí, y darlo por cerrado es exactamente lo que un auditor
    busca. Si fue eficaz queda lista para cerrar, pero no se cierra sola —
    cerrar es una decisión de alguien, con nombre.
    """
    oportunidad.eficaz = eficaz
    oportunidad.nota_eficacia = nota
    if valor_verificado is not None:
        oportunidad.valor_verificado = valor_verificado

    if not eficaz:
        oportunidad.estado = "analisis"
    elif oportunidad.estado != "cerrada":
        oportunidad.estado = "verificacion"

    db.commit()
    db.refresh(oportunidad)
    return oportunidad


# ── Lo que se muestra en Indicadores y en el inicio ───────────────────

def indicadores_en_rojo_sin_omp(db: Session, tenant_id: int,
                                ids_en_rojo: list[int]) -> list[int]:
    """
    De los indicadores en rojo, cuáles no tienen ninguna OMP abierta.

    Es el dato que hoy no existe en ninguna parte: un indicador en rojo sin
    oportunidad es un problema que nadie está trabajando.
    """
    if not ids_en_rojo:
        return []

    con_omp = (
        db.query(Oportunidad.indicador_id)
        .filter(Oportunidad.tenant_id == tenant_id,
                Oportunidad.indicador_id.in_(ids_en_rojo),
                Oportunidad.estado.notin_(["cerrada", ESTADO_DESCARTADA]))
        .distinct()
        .all()
    )
    atendidos = {fila[0] for fila in con_omp}
    return [i for i in ids_en_rojo if i not in atendidos]
