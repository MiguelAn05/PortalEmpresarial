"""
El indicador «Gestión de OMP»: qué tan al día lleva cada área sus
oportunidades de mejora.

Una OMP es texto —análisis, avances, verificación—, y el texto no se puede
calificar solo. Lo que sí se puede contar son los HECHOS que deja la
gestión: si los compromisos se cumplen en su fecha, si alguien reporta
avances, si la OMP se pasa del plazo que se puso. Eso es lo que se mide.

**Se mide cada OMP viva, todos los meses que está abierta.** Medir solo las
acciones que vencen en el mes dejaba ciega a una OMP de un año con una
acción al final: once meses sin dato mientras podía estar abandonada. Así,
una OMP de doce meses cuenta doce veces, y en cada una tiene que estar al día.

Una OMP está **al día** en un mes si cumple las tres cosas:

1. **Plan**: ninguna acción está vencida sin cumplir al corte, y ninguna se
   cumplió ese mes después de su fecha. Se mide contra la fecha ORIGINAL:
   aplazar se permite, pero no mejora el indicador.
2. **Avances**: en el mes hubo al menos un movimiento real —un seguimiento,
   un cambio de etapa, una acción cumplida o una acción nueva en el plan—.
   Una OMP registrada en los últimos días del mes queda eximida: no ha
   tenido tiempo de moverse.
3. **Plazo**: no pasó su «fecha estimada de solución» estando abierta.

Valor = OMP al día ÷ OMP vivas en el mes × 100. Se guardan los dos números,
así el acumulado del año suma y no promedia. Un área sin OMP vivas en el mes
queda «sin dato»: no tener OMP no es gestionarlas bien ni mal.

El detalle dice qué OMP quedaron atrasadas y por qué. Es lo que permite
revisar el número OMP por OMP en vez de creerle a ciegas.
"""
from calendar import monthrange
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy.orm import Session, selectinload

from app.models.mejora import (
    ESTADO_DESCARTADA, CambioMejora, Oportunidad, SeguimientoMejora,
)

TERMINALES = {"cerrada", ESTADO_DESCARTADA}

# Una OMP registrada a menos de esto del corte no tiene que mostrar avances
# ese mes: no tuvo tiempo de moverse.
DIAS_GRACIA_AVANCES = 15

# Cuántas OMP atrasadas se nombran en el detalle antes de resumir el resto.
MAX_EN_DETALLE = 10


@dataclass
class EvaluacionOMP:
    id: int
    codigo: str | None
    titulo: str
    motivos: list[str] = field(default_factory=list)

    @property
    def al_dia(self) -> bool:
        return not self.motivos


def _aware(valor) -> datetime | None:
    """Postgres devuelve fechas con zona y SQLite sin ella; aquí todo lleva zona."""
    if valor is None:
        return None
    if isinstance(valor, datetime):
        return valor if valor.tzinfo else valor.replace(tzinfo=timezone.utc)
    return datetime.combine(valor, time.min, tzinfo=timezone.utc)


def _tramos_abierta(omp: Oportunidad, cambios: list[CambioMejora]) -> list[tuple[datetime, datetime | None]]:
    """
    Los periodos en que la OMP estuvo abierta (no cerrada ni descartada).

    Sale del historial de estados y no solo de `fecha_cierre`, porque una
    descartada se puede retomar: si solo se mirara el estado de hoy, los
    meses en que estuvo descartada contarían como meses sin avances.
    """
    inicio = _aware(omp.creado_en) or _aware(omp.fecha_registro)
    estados = sorted(
        ((_aware(c.fecha), c.valor_nuevo) for c in cambios if c.fecha),
        key=lambda x: x[0],
    )
    if not estados:
        if omp.estado in TERMINALES:
            fin = _aware(omp.fecha_cierre) or inicio
            return [(inicio, fin)]
        return [(inicio, None)]

    tramos, desde, abierta = [], inicio, True
    for cuando, nuevo in estados:
        if abierta and nuevo in TERMINALES:
            tramos.append((desde, cuando))
            abierta = False
        elif not abierta and nuevo not in TERMINALES:
            desde, abierta = cuando, True
    if abierta:
        tramos.append((desde, None))
    return tramos


def _evaluar(omp: Oportunidad, cambios: list[CambioMejora], fechas_seguimiento: list[date],
             inicio: datetime, corte: datetime, mes_completo: bool) -> EvaluacionOMP | None:
    """La OMP en el mes, o None si no estuvo abierta en ningún momento del mes."""
    activos = [
        (max(desde, inicio), min(hasta or corte, corte))
        for desde, hasta in _tramos_abierta(omp, cambios)
        if desde <= corte and (hasta is None or hasta >= inicio)
    ]
    if not activos:
        return None

    # Hasta dónde se le pide cuentas este mes: el corte, o el momento en que
    # se cerró si fue dentro del mes.
    corte_omp = max(hasta for _desde, hasta in activos)
    evaluacion = EvaluacionOMP(id=omp.id, codigo=omp.codigo, titulo=omp.titulo)

    # 1. Plan de acción, contra la fecha original.
    vencidas = tarde = 0
    for accion in omp.acciones:
        limite = _aware(accion.fecha_limite_original or accion.fecha_limite)
        if limite is None:
            continue
        hecha = _aware(accion.fecha_completada) if accion.estado == "cumplida" else None
        if hecha and inicio <= hecha <= corte_omp and hecha.date() > limite.date():
            tarde += 1
        elif limite.date() < corte_omp.date() and (hecha is None or hecha > corte_omp):
            vencidas += 1
    if vencidas:
        evaluacion.motivos.append(
            f"{vencidas} acción vencida" if vencidas == 1 else f"{vencidas} acciones vencidas")
    if tarde:
        evaluacion.motivos.append(
            f"{tarde} acción cumplida tarde" if tarde == 1 else f"{tarde} acciones cumplidas tarde")

    # 2. Avances. Solo se exige con el mes terminado: a mitad de mes todavía
    # hay tiempo, y medir antes castigaría lo que aún no pasa.
    if mes_completo:
        registrada = _aware(omp.creado_en) or inicio
        recien_registrada = registrada > corte_omp - timedelta(days=DIAS_GRACIA_AVANCES)
        hubo_seguimiento = any(inicio.date() <= f <= corte_omp.date() for f in fechas_seguimiento)
        hubo_cambio_estado = any(
            c.fecha and inicio <= _aware(c.fecha) <= corte_omp for c in cambios)
        hubo_movimiento_plan = any(
            (a.fecha_completada and inicio <= _aware(a.fecha_completada) <= corte_omp)
            or (a.creado_en and inicio <= _aware(a.creado_en) <= corte_omp)
            for a in omp.acciones
        )
        if not (recien_registrada or hubo_seguimiento or hubo_cambio_estado or hubo_movimiento_plan):
            evaluacion.motivos.append("sin avances en el mes")

    # 3. Plazo general: se pasó de la fecha estimada estando abierta.
    limite_omp = _aware(omp.fecha_limite)
    if limite_omp and limite_omp.date() < corte_omp.date():
        evaluacion.motivos.append("pasó su fecha estimada de solución")

    return evaluacion


def evaluar_mes(db: Session, tenant_id: int, area: str, anio: int, mes: int,
                ahora: datetime | None = None) -> list[EvaluacionOMP]:
    """Cada OMP del área que estuvo abierta en el mes, con si quedó al día y por qué no."""
    ahora = _aware(ahora) or datetime.now(timezone.utc)
    inicio = datetime(anio, mes, 1, tzinfo=timezone.utc)
    fin = datetime(anio, mes, monthrange(anio, mes)[1], 23, 59, 59, tzinfo=timezone.utc)
    if inicio > ahora:
        return []
    corte = min(fin, ahora)
    mes_completo = fin <= ahora

    omps = (
        db.query(Oportunidad)
        .options(selectinload(Oportunidad.acciones))
        .filter(Oportunidad.tenant_id == tenant_id, Oportunidad.area == area)
        .all()
    )
    if not omps:
        return []
    ids = [o.id for o in omps]

    cambios: dict[int, list[CambioMejora]] = {}
    for c in (db.query(CambioMejora)
              .filter(CambioMejora.omp_id.in_(ids), CambioMejora.campo == "Estado").all()):
        cambios.setdefault(c.omp_id, []).append(c)

    seguimientos: dict[int, list[date]] = {}
    for omp_id, fecha in (db.query(SeguimientoMejora.omp_id, SeguimientoMejora.fecha)
                          .filter(SeguimientoMejora.omp_id.in_(ids)).all()):
        seguimientos.setdefault(omp_id, []).append(fecha)

    evaluaciones = []
    for omp in omps:
        resultado = _evaluar(omp, cambios.get(omp.id, []), seguimientos.get(omp.id, []),
                             inicio, corte, mes_completo)
        if resultado:
            evaluaciones.append(resultado)
    return sorted(evaluaciones, key=lambda e: (e.al_dia, e.codigo or ""))


def resumir(evaluaciones: list[EvaluacionOMP]) -> tuple[int, int, str]:
    """(al día, vivas, detalle legible) para guardar en la medición."""
    total = len(evaluaciones)
    al_dia = sum(1 for e in evaluaciones if e.al_dia)
    if not total:
        return 0, 0, "Sin OMP abiertas en el periodo"

    detalle = f"{al_dia} de {total} OMP al día."
    atrasadas = [e for e in evaluaciones if not e.al_dia]
    if atrasadas:
        nombradas = [
            f"{e.codigo or e.titulo} ({', '.join(e.motivos)})"
            for e in atrasadas[:MAX_EN_DETALLE]
        ]
        resto = len(atrasadas) - MAX_EN_DETALLE
        detalle += " Atrasadas: " + "; ".join(nombradas)
        detalle += f"; y {resto} más." if resto > 0 else "."
    return al_dia, total, detalle
