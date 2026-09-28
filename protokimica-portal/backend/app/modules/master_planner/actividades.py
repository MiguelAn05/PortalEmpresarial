"""
Qué se esperaba de cada día, y qué se hizo.

**Las ocurrencias no se guardan: se deducen.** La actividad dice con qué
frecuencia toca; de ahí sale qué días se esperaba, y lo único escrito en la
base es lo que de verdad se hizo (`mp_actividad_registros`). Materializar un
pendiente por día obligaría a un proceso programado corriendo cada
madrugada, y el día que no corriera la gente entraría a una pantalla vacía
sin que nadie supiera por qué — un módulo que depende de un `cron` para
mostrar lo de hoy está roto la primera vez que ese `cron` falla.

El precio, dicho de frente: cambiarle la frecuencia a una actividad cambia
también lo que se esperaba ANTES. Se acota con dos cosas — `desde` marca
desde cuándo aplica, y el indicador del mes guarda su medición al
calcularse, igual que todos los demás, así que un mes ya cerrado no se
reescribe.

Todo lo de aquí trabaja con `date` y no con `datetime`: «el martes» no tiene
hora, y mezclar los dos tipos es cómo se terminan restando fechas con y sin
zona horaria.
"""
from calendar import monthrange
from datetime import date, timedelta

from app.core.dias_habiles import es_habil
from app.models.master_planner import ActividadDiaria, ActividadRegistro

# Los días de la semana como los escribe la gente, en el orden en que se
# leen. La clave es el número ISO (1 = lunes), que es el que devuelve
# `date.isoweekday()`.
DIAS_SEMANA = {
    1: "Lunes", 2: "Martes", 3: "Miércoles", 4: "Jueves",
    5: "Viernes", 6: "Sábado", 7: "Domingo",
}


def leer_dias(texto: str | None) -> list[int]:
    """«1,3,5» → [1, 3, 5]. Lo que no sea un día válido se descarta."""
    if not texto:
        return []
    dias = []
    for parte in str(texto).split(","):
        parte = parte.strip()
        if parte.isdigit() and 1 <= int(parte) <= 7 and int(parte) not in dias:
            dias.append(int(parte))
    return sorted(dias)


def escribir_dias(dias: list[int] | None) -> str | None:
    """La lista de vuelta a texto, ya limpia y ordenada."""
    limpios = leer_dias(",".join(str(d) for d in (dias or [])))
    return ",".join(str(d) for d in limpios) or None


def _dia_del_mes_que_aplica(dia_mes: int, cuando: date) -> int:
    """
    Qué día cae realmente una actividad «cada 31» en un mes de 30.

    Se espera el ÚLTIMO día del mes, no se salta el mes. Saltarlo haría que
    una actividad mensual desapareciera en febrero y en los cuatro meses de
    treinta días, y nadie lo notaría hasta que el indicador diera de más.
    """
    ultimo = monthrange(cuando.year, cuando.month)[1]
    return min(dia_mes, ultimo)


def se_espera_el(actividad: ActividadDiaria, dia: date) -> bool:
    """¿Esta actividad tocaba ese día?"""
    if actividad.desde and dia < actividad.desde:
        return False
    # `hasta` se llena al desactivarla: desde ese día ya no se espera nada.
    if actividad.hasta and dia > actividad.hasta:
        return False

    if actividad.frecuencia == "semanal":
        return dia.isoweekday() in leer_dias(actividad.dias_semana)

    if actividad.frecuencia == "mensual":
        if not actividad.dia_mes:
            return False
        return dia.day == _dia_del_mes_que_aplica(actividad.dia_mes, dia)

    # Diaria. Lo normal en una oficina es que el fin de semana y los festivos
    # no cuenten; `core/dias_habiles.py` ya sabe cuáles son los de Colombia.
    if actividad.solo_dias_habiles:
        return es_habil(dia)
    return True


def dias_esperados(actividad: ActividadDiaria, desde: date, hasta: date) -> list[date]:
    """Los días en que tocaba, dentro del rango pedido."""
    if hasta < desde:
        return []
    dias, cursor = [], desde
    while cursor <= hasta:
        if se_espera_el(actividad, cursor):
            dias.append(cursor)
        cursor += timedelta(days=1)
    return dias


def descripcion_frecuencia(actividad: ActividadDiaria) -> str:
    """
    La frecuencia en palabras, para la pantalla y para el correo.

    La arma el SERVIDOR y no la pantalla por lo mismo que todo lo demás: si
    el frontend la redactara, el día que se agregue una frecuencia nueva
    habría un sitio más que actualizar — y el que se olvide muestra «undefined».
    """
    if actividad.frecuencia == "semanal":
        dias = [DIAS_SEMANA[d] for d in leer_dias(actividad.dias_semana)]
        if not dias:
            return "Semanal, sin días marcados"
        if len(dias) == 1:
            return f"Cada {dias[0].lower()}"
        return "Cada " + ", ".join(d.lower() for d in dias[:-1]) + f" y {dias[-1].lower()}"

    if actividad.frecuencia == "mensual":
        if not actividad.dia_mes:
            return "Mensual, sin día definido"
        return f"Cada mes, el día {actividad.dia_mes}"

    return "Todos los días hábiles" if actividad.solo_dias_habiles else "Todos los días"


# ── Cumplimiento ─────────────────────────────────────────────────────

def _registros_por_fecha(db, actividad_id: int, desde: date, hasta: date) -> set[date]:
    filas = (
        db.query(ActividadRegistro.fecha)
        .filter(
            ActividadRegistro.actividad_id == actividad_id,
            ActividadRegistro.fecha >= desde,
            ActividadRegistro.fecha <= hasta,
        )
        .all()
    )
    return {f[0] for f in filas}


def cumplimiento(db, actividad: ActividadDiaria, desde: date, hasta: date) -> dict:
    """
    Cuántas veces tocaba en el rango y cuántas se registró.

    `esperados` en cero significa «no había nada que hacer», que **no es lo
    mismo que incumplir**: una actividad creada ayer no arrastra en rojo todo
    el mes anterior. Por eso el porcentaje es `None` y no 0.
    """
    esperados = dias_esperados(actividad, desde, hasta)
    hechos = _registros_por_fecha(db, actividad.id, desde, hasta)
    cumplidos = [d for d in esperados if d in hechos]

    return {
        "esperados": len(esperados),
        "cumplidos": len(cumplidos),
        "pendientes": [d for d in esperados if d not in hechos],
        "pct": round(len(cumplidos) / len(esperados) * 100, 1) if esperados else None,
    }


def corte_del_mes(anio: int, mes: int, hoy: date) -> tuple[date, date]:
    """
    Qué parte del mes se mide.

    **El mes en curso se mide hasta AYER.** Lo de hoy todavía se puede hacer,
    así que contarlo como incumplido sería cobrarle a alguien un día que no
    ha terminado — y el indicador estaría en rojo cada mañana.
    """
    primero = date(anio, mes, 1)
    ultimo = date(anio, mes, monthrange(anio, mes)[1])
    if (anio, mes) == (hoy.year, hoy.month):
        return primero, hoy - timedelta(days=1)
    return primero, ultimo


def mapa_del_mes(db, actividad: ActividadDiaria, anio: int, mes: int, hoy: date) -> dict:
    """
    El mes entero, día por día: cuáles tocaban, cuáles se registraron.

    Reemplaza la lista de días registrados, que crecía sin final. Una lista
    de trescientas filas iguales no responde la pregunta que uno tiene —«¿voy
    al día?»— y con el tiempo se vuelve imposible de leer. Un mes cabe en un
    bloque, se compara de un vistazo y **no crece nunca**: siempre son treinta
    y un cuadros como mucho.

    Cada día viene con su estado ya resuelto, y son cuatro, no dos:

      - `no_aplica` — ese día no tocaba. Es la mayoría en una actividad
        semanal, y pintarlos como incumplidos sería mentir.
      - `cumplido`  — tocaba y se registró.
      - `pendiente` — tocaba, es HOY y todavía se puede hacer.
      - `sin_registrar` — tocaba, ya pasó y no se hizo.

    La diferencia entre los dos últimos es la misma regla del corte del mes:
    lo de hoy no se cobra hasta que el día termine.
    """
    ultimo = monthrange(anio, mes)[1]
    primero = date(anio, mes, 1)
    registros = {
        r.fecha: r
        for r in db.query(ActividadRegistro).filter(
            ActividadRegistro.actividad_id == actividad.id,
            ActividadRegistro.fecha >= primero,
            ActividadRegistro.fecha <= date(anio, mes, ultimo),
        ).all()
    }

    dias, esperados, cumplidos = [], 0, 0
    for numero in range(1, ultimo + 1):
        dia = date(anio, mes, numero)
        toca = se_espera_el(actividad, dia)
        registro = registros.get(dia)

        if not toca:
            estado = "no_aplica"
        elif registro:
            estado = "cumplido"
        elif dia >= hoy:
            # Hoy todavía se puede hacer, y el futuro ni se juzga.
            estado = "pendiente"
        else:
            estado = "sin_registrar"

        if toca:
            esperados += 1
            if registro:
                cumplidos += 1

        dias.append({
            "fecha": dia,
            "estado": estado,
            "usuario_nombre": registro.usuario_nombre if registro else None,
            "comentario": registro.comentario if registro else None,
        })

    # El porcentaje se mide sobre lo que YA se podía haber hecho, no sobre el
    # mes entero: si no, el primer día de octubre toda actividad diaria
    # aparecería con un 5% de cumplimiento por los días que faltan.
    corte_desde, corte_hasta = corte_del_mes(anio, mes, hoy)
    cerrado = cumplimiento(db, actividad, corte_desde, corte_hasta)

    return {
        "anio": anio,
        "mes": mes,
        "dias": dias,
        "esperados": esperados,
        "cumplidos": cumplidos,
        "esperados_hasta_hoy": cerrado["esperados"],
        "cumplidos_hasta_hoy": cerrado["cumplidos"],
        "pct": cerrado["pct"],
    }
