"""
Las reglas de asistencia de Protokimica, en un solo sitio.

Son las MISMAS que aplica `integraciones/marcaciones/alertas_zkteco.py` en el
servidor de ZKBio para los correos: si una cambia aquí y allá no, la pantalla
dice una cosa y el correo otra. El portal calcula (el backend calcula, el
frontend presenta); el script de alertas sigue siendo independiente a
propósito, porque tiene que funcionar aunque el portal esté caído.
"""

# ── Llegada, salida y ausencia ────────────────────────────────
ANTICIPACION_LLEGADA_MIN = 10    # hay que marcar entrada 10 min ANTES del inicio del turno
TOLERANCIA_LLEGADA_MIN = 0       # gracia después de esa hora límite (inicio − 10 min) antes de contar llegada tarde
TOLERANCIA_SALIDA_MIN = 0        # salida más de 0 min antes del fin = salida anticipada
AUSENCIA_HORAS = 3               # sin marcar 3 h después del inicio de su turno más tardío
AUSENCIA_HORAS_SABADO = 1.5      # el sábado la ventana es menor

# ── Cómo se reconoce el turno de quien tiene varias opciones ──
# La malla dice los turnos POSIBLES de cada persona ese día, no el que hizo:
# en la práctica cambian por razones logísticas. El turno se deduce de la
# primera entrada.
VENTANA_ANTES_MIN = 45           # llegar hasta 45 min antes del inicio sigue siendo ese turno
VENTANA_DESPUES_MIN = 10         # y hasta 10 min después
DIAS_HISTORIAL_TURNO = 21        # cuánto se mira atrás para saber el turno habitual
MAX_HISTORIAL = 10               # cuántos días recientes cuentan para elegir

# ── Descansos (botones de salida/regreso a descanso del reloj) ─
ALMUERZO_MIN = 45
BREAK_MIN = 15
TOLERANCIA_DESCANSO_MIN = 0
# Con un solo descanso en el día, es «break» si salió antes de estas horas
# desde el inicio de su turno, y «almuerzo» si no. Con dos, el primero es el
# break y el segundo el almuerzo.
CORTE_BREAK_HORAS = 4

# ── Estados de una marcación en ZKBio ─────────────────────────
ENTRADA, SALIDA, SALIDA_DESCANSO, REGRESO_DESCANSO = "0", "1", "2", "3"
ESTADOS_VALIDOS = {"0", "1", "2", "3", "4", "5"}   # 4 y 5 son horas extra: se guardan, no se evalúan

# ── Presencia (dónde está la persona AHORA) ───────────────────
PRESENCIAS = {
    "adentro": "En la empresa",
    "en_descanso": "En descanso",
    "salio": "Ya salió",
    "pendiente": "Aún no marca",
    "ausente": "Ausente",
    "justificado": "Justificado",
    "sin_turno": "Sin turno hoy",
}

# ── Novedades ────────────────────────────────────────────────
# clave -> etiqueta. La clave no cambia nunca: va en enlaces y en el CSV.
NOVEDADES = {
    "llegada_tarde": "Llegada tarde",
    "salida_anticipada": "Salida anticipada",
    "ausencia": "Ausencia",
    "exceso_almuerzo": "Exceso de almuerzo",
    "exceso_break": "Exceso de break",
    "turno_por_confirmar": "Turno por confirmar",
}

# ── Sincronización ───────────────────────────────────────────
# Si el script no ha mandado nada en tanto tiempo, la pantalla avisa que lo
# que se ve puede estar atrasado: un tablero «en vivo» que dejó de estarlo y
# no lo dice es peor que no tenerlo.
MINUTOS_DATOS_ATRASADOS = 10
MAX_MARCACIONES_POR_ENVIO = 20000
MAX_DIAS_INFORME = 93
