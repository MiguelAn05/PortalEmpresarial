"""
Qué pasó con cada persona un día: llegó tarde, no vino, se pasó del almuerzo.

Funciones puras, sin base de datos ni red: reciben listas y devuelven
diccionarios, y por eso se prueban con datos inventados (`tests/test_marcaciones.py`).
Todas las horas son «de pared» —la hora local de la empresa, sin zona—: lo que
dice el reloj de la pared, que es lo que dice la malla de turnos.

Las reglas están en `constants.py`; el porqué de las no obvias, aquí:

- **El turno se deduce de la primera entrada.** La malla da los turnos
  POSIBLES, no el que se hizo. Si la persona tiene uno solo, es ese. Si tiene
  varios, vale el que empieza entre 45 min antes y 10 min después de su
  entrada. Si entra más tarde que eso —que es justo cuando hay que alertar—,
  tomar «el más cercano» la pasaría al turno siguiente y la dejaría sin
  novedad, así que se usa el turno que esa persona suele hacer (su historial)
  y, sin historial, NO se acusa: se pide confirmarlo.
- **Ausencia = nada de nada pasadas 3 h del inicio de su turno MÁS TARDÍO.**
  Sin marcación no hay forma de saber cuál le tocaba, así que no se avisa
  antes de que todos sus turnos posibles hayan empezado y pasado la ventana.
- **Un descanso abierto no es un exceso si ya se fue**: quien marcó la salida
  del día después de salir a descanso simplemente olvidó el regreso.
"""
import collections
import datetime as dt

from app.modules.marcaciones import constants as C

DIAS = ["lun", "mar", "mie", "jue", "vie", "sab", "dom"]


# ── Turnos ────────────────────────────────────────────────────

def _hm(texto: str) -> dt.time:
    h, m = str(texto).strip().split(":")[:2]
    return dt.time(int(h), int(m))


def opciones_de(emp: dict, dia: dt.date) -> str:
    """El texto de turnos posibles de esa persona ese día de la semana."""
    return (emp.get(DIAS[dia.weekday()]) or "").strip()


def turnos_del_dia(opciones: str, dia: dt.date) -> list[tuple[dt.datetime, dt.datetime]]:
    """
    «06:00-14:30/07:00-15:30» -> [(inicio, fin), ...] ese día.

    El que termina antes de empezar acaba al día siguiente (turno de noche).
    Una opción mal escrita se ignora en vez de tumbar la pantalla: el envío
    ya la rechaza al validar, esto es el último cinturón.
    """
    turnos = []
    for opcion in (opciones or "").split("/"):
        opcion = opcion.strip()
        if not opcion:
            continue
        try:
            a, b = opcion.split("-")
            ini, fin = dt.datetime.combine(dia, _hm(a)), dt.datetime.combine(dia, _hm(b))
        except (ValueError, TypeError):
            continue
        turnos.append((ini, fin if fin > ini else fin + dt.timedelta(days=1)))
    return turnos


def detectar_turno(turnos, t0: dt.datetime, historial: list[str]):
    """
    (inicio, fin, confianza) del turno que hizo la persona, por su primera entrada.

    - `unica`: solo tiene un turno ese día.
    - `alta`: la entrada cae en la ventana de uno de sus turnos.
    - `historial`: cayó fuera de todas; se usa el que más ha hecho (y, a
      igualdad, el más reciente). `historial` va del día más reciente al más viejo.
    - `revisar`: fuera de todas y sin historial útil. No se adivina.
    """
    if len(turnos) == 1:
        return turnos[0][0], turnos[0][1], "unica"
    antes = dt.timedelta(minutes=C.VENTANA_ANTES_MIN)
    despues = dt.timedelta(minutes=C.VENTANA_DESPUES_MIN)
    candidatos = [t for t in turnos if t[0] - antes <= t0 <= t[0] + despues]
    if candidatos:
        t = min(candidatos, key=lambda x: (abs((t0 - x[0]).total_seconds()), x[0]))
        return t[0], t[1], "alta"
    if historial:
        cuenta = collections.Counter(historial)
        mejor = None
        for t in turnos:
            hhmm = t[0].strftime("%H:%M")
            if cuenta.get(hhmm):
                clave = (-cuenta[hhmm], historial.index(hhmm))
                if mejor is None or clave < mejor[0]:
                    mejor = (clave, t)
        if mejor:
            return mejor[1][0], mejor[1][1], "historial"
    return None, None, "revisar"


def turno_de_ese_dia(opciones: str, dia: dt.date, marcas: list) -> str | None:
    """
    El inicio («HH:MM») del turno que la persona hizo ese día, SOLO si se
    reconoce con certeza (varias opciones y la entrada cae en una ventana).
    Es lo que alimenta el historial: un día dudoso no enseña nada.
    """
    turnos = turnos_del_dia(opciones, dia)
    if len(turnos) < 2 or not marcas:
        return None
    entradas = [m[0] for m in marcas if m[1] == C.ENTRADA] or [marcas[0][0]]
    inicio, _, confianza = detectar_turno(turnos, entradas[0], [])
    return inicio.strftime("%H:%M") if confianza == "alta" else None


# ── Descansos ─────────────────────────────────────────────────

def corregir_descansos(marcas: list) -> list:
    """
    Los botones de descanso se leen por el ORDEN, no por cuál se oprimió.

    La gente oprime cualquiera de los dos: llegaban `3, 3`, `2, 2` o `3, 2`
    para un mismo break, y el par quedaba mal armado —un break de 09:46 a
    13:01 que eran en realidad un break y un almuerzo—. Lo único seguro es que
    salir y volver se alternan: la marca de descanso que llega sin uno abierto
    es la salida, y la que llega con uno abierto es el regreso. Una «Entrada»
    con un descanso abierto también es el regreso. Una «Salida» lo cierra
    (se fue sin marcar el regreso). `marcas` va ordenada.
    """
    descanso = {C.SALIDA_DESCANSO, C.REGRESO_DESCANSO}
    out, abierto = [], False
    for t, estado in marcas:
        if estado in descanso:
            estado = C.REGRESO_DESCANSO if abierto else C.SALIDA_DESCANSO
            abierto = not abierto
        elif estado == C.ENTRADA and abierto:
            estado, abierto = C.REGRESO_DESCANSO, False
        elif estado == C.SALIDA:
            abierto = False
        out.append((t, estado))
    return out


def pares_descanso(marcas: list) -> list[tuple[dt.datetime, dt.datetime | None]]:
    """[(salida, regreso o None si sigue afuera)] con los estados 2 y 3."""
    pares, abierto = [], None
    for t, estado in marcas:
        if estado == C.SALIDA_DESCANSO:
            if abierto is None:
                abierto = t
        elif estado == C.REGRESO_DESCANSO and abierto is not None:
            pares.append((abierto, t))
            abierto = None
    if abierto is not None:
        pares.append((abierto, None))
    return pares


# ── La persona ────────────────────────────────────────────────

def _hhmm(t: dt.datetime) -> str:
    return t.strftime("%H:%M")


def _novedad(clave: str, detalle: str) -> dict:
    return {"tipo": clave, "etiqueta": C.NOVEDADES[clave], "detalle": detalle}


def evaluar_persona(dia: dt.date, ahora: dt.datetime, emp: dict, marcas: list,
                    historial: list[str] | None = None, justificado: str | None = None,
                    festivo: bool = False) -> dict | None:
    """
    Todo lo que se sabe de una persona ese día, o None si hoy no se la espera
    ni marcó (no tiene turno, no es de ese día).

    `ahora` es el «ahora» de la evaluación: la hora real si el día es hoy, el
    final del día si es pasado. `marcas` va ordenada: [(datetime, estado)] o
    [(datetime, estado, dispositivo)]. El dispositivo no entra en ninguna
    regla: solo viaja hasta la fila para decir dónde se marcó.
    """
    opciones = opciones_de(emp, dia)
    turnos = turnos_del_dia(opciones, dia)
    crudas = sorted((m for m in marcas if m[1] in {C.ENTRADA, C.SALIDA, C.SALIDA_DESCANSO, C.REGRESO_DESCANSO}),
                    key=lambda m: (m[0], m[1]))
    equipos = [m[2] if len(m) > 2 else None for m in crudas]
    marcas = corregir_descansos([(m[0], m[1]) for m in crudas])
    fila = {
        "emp_code": emp["emp_code"], "nombre": emp["nombre"], "area": emp.get("area"),
        "turno_opciones": " / ".join(f"{_hhmm(a)}-{_hhmm(b)}" for a, b in turnos),
        "turno": None, "confianza": None, "presencia": None,
        "primera_entrada": None, "ultima_marca": None,
        "marcas": [{"hora": _hhmm(t), "estado": e, "dispositivo": d} for (t, e), d in zip(marcas, equipos)],
        "novedades": [],
    }
    if marcas:
        entradas = [t for t, e in marcas if e == C.ENTRADA] or [marcas[0][0]]
        fila["primera_entrada"] = _hhmm(entradas[0])
        t_ult, e_ult = marcas[-1]
        fila["ultima_marca"] = {"hora": _hhmm(t_ult), "estado": e_ult, "dispositivo": equipos[-1]}

    if justificado is not None:
        fila["presencia"], fila["motivo"] = "justificado", justificado
        return fila
    if festivo:
        if not marcas:
            return None
        fila["turno"], fila["presencia"] = "Festivo", _presencia_por_marcas(marcas)
        return fila
    if not turnos:
        if not marcas:
            return None
        fila["turno"], fila["presencia"] = "Sin turno", _presencia_por_marcas(marcas)
        return fila

    # Sin ninguna marcación: ausente solo cuando TODOS sus turnos posibles
    # llevan tiempo de sobra empezados.
    if not marcas:
        horas = C.AUSENCIA_HORAS_SABADO if dia.weekday() == 5 else C.AUSENCIA_HORAS
        ultimo = max(t[0] for t in turnos)
        if ahora >= ultimo + dt.timedelta(hours=horas):
            fila["presencia"] = "ausente"
            fila["novedades"].append(_novedad(
                "ausencia",
                f"Sin marcaciones. Pasaron {horas:g} h desde el inicio de su turno más tardío ({_hhmm(ultimo)})."))
        else:
            fila["presencia"] = "pendiente"
        return fila

    t0 = entradas[0]
    inicio, fin, confianza = detectar_turno(turnos, t0, historial or [])
    fila["confianza"] = confianza
    fila["presencia"] = _presencia_por_marcas(marcas)

    if confianza == "revisar":
        fila["turno"] = None
        fila["novedades"].append(_novedad(
            "turno_por_confirmar",
            f"Marcó a las {_hhmm(t0)}, fuera de la ventana de todos sus turnos posibles "
            f"({fila['turno_opciones']}). No se puede asegurar su turno; hay que revisarlo."))
    else:
        fila["turno"] = f"{_hhmm(inicio)}-{_hhmm(fin)}"
        nota = " (turno inferido por su historial)" if confianza == "historial" else ""
        if t0 > inicio + dt.timedelta(minutes=C.TOLERANCIA_LLEGADA_MIN) and t0 < fin:
            mins = int((t0 - inicio).total_seconds() // 60)
            fila["novedades"].append(_novedad(
                "llegada_tarde",
                f"Marcó entrada a las {_hhmm(t0)}; su turno empieza a las {_hhmm(inicio)} ({mins} min después).{nota}"))
        for t, e in marcas:
            if e == C.SALIDA and inicio < t < fin - dt.timedelta(minutes=C.TOLERANCIA_SALIDA_MIN):
                mins = int((fin - t).total_seconds() // 60)
                fila["novedades"].append(_novedad(
                    "salida_anticipada",
                    f"Marcó salida a las {_hhmm(t)}, {mins} min antes de que termine su turno ({_hhmm(fin)}).{nota}"))
                break

    fila["novedades"].extend(_excesos_de_descanso(marcas, ahora, inicio))
    return fila


def _presencia_por_marcas(marcas: list) -> str:
    """Dónde está según la ÚLTIMA marcación: 2 = en descanso, 1 = ya salió, el resto adentro."""
    ultimo = marcas[-1][1]
    return {"2": "en_descanso", "1": "salio"}.get(ultimo, "adentro")


def _excesos_de_descanso(marcas, ahora, inicio_turno):
    salidas = [t for t, e in marcas if e == C.SALIDA]
    pares = pares_descanso(marcas)
    out = []
    for i, (a, b) in enumerate(pares):
        if b is None and any(t > a for t in salidas):
            continue  # se fue sin marcar el regreso: no es un exceso
        if len(pares) >= 2:
            tipo = "break" if i == 0 else ("almuerzo" if i == 1 else None)
        elif inicio_turno is not None:
            corte = dt.timedelta(hours=C.CORTE_BREAK_HORAS)
            tipo = "break" if (a - inicio_turno) < corte else "almuerzo"
        else:
            tipo = "break" if a.hour < 11 else "almuerzo"
        if tipo is None:
            continue
        limite = C.ALMUERZO_MIN if tipo == "almuerzo" else C.BREAK_MIN
        duracion = int(((b or ahora) - a).total_seconds() // 60)
        if duracion > limite + C.TOLERANCIA_DESCANSO_MIN:
            if b is None:
                detalle = (f"Salió a {tipo} a las {_hhmm(a)} y aún no marca el regreso "
                           f"({duracion} min hasta ahora; permitido {limite}).")
            else:
                detalle = (f"Salió a {tipo} a las {_hhmm(a)} y volvió a las {_hhmm(b)} "
                           f"({duracion} min; permitido {limite}).")
            out.append(_novedad(f"exceso_{tipo}", detalle))
    return out


# ── El día completo ───────────────────────────────────────────

def evaluar_dia(dia: dt.date, ahora: dt.datetime, empleados: list[dict],
                marcas_por_codigo: dict, historial_por_codigo: dict | None = None,
                justificados: dict | None = None, festivo: bool = False) -> list[dict]:
    """Una fila por persona esperada (o que marcó), ordenada por área y nombre."""
    historial_por_codigo = historial_por_codigo or {}
    justificados = justificados or {}
    filas = []
    for emp in empleados:
        codigo = emp["emp_code"]
        fila = evaluar_persona(
            dia, ahora, emp, marcas_por_codigo.get(codigo, []),
            historial_por_codigo.get(codigo), justificados.get(codigo), festivo)
        if fila is not None:
            filas.append(fila)
    filas.sort(key=lambda f: ((f["area"] or "~").casefold(), f["nombre"].casefold()))
    return filas
