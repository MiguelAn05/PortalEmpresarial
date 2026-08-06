"""
Días hábiles y festivos colombianos.

De esto dependen todos los plazos de PQRS y el indicador de oportunidad, así
que las fechas se comprueban contra festivos reales conocidos, no contra lo
que devuelva el propio código.
"""
from datetime import date, datetime, timezone

from app.core.dias_habiles import (
    contar_habiles, es_habil, festivos, limite_en_habiles,
    siguiente_habil, sumar_habiles,
)


def test_festivos_fijos_que_no_se_mueven():
    f2026 = festivos(2026)
    for esperado in [date(2026, 1, 1), date(2026, 5, 1), date(2026, 7, 20),
                     date(2026, 8, 7), date(2026, 12, 8), date(2026, 12, 25)]:
        assert esperado in f2026, f"Falta el festivo fijo {esperado}"


def test_ley_emiliani_corre_al_lunes():
    # Reyes 2026: el 6 de enero cae martes, así que el festivo es el lunes 12.
    f = festivos(2026)
    assert date(2026, 1, 12) in f, "Reyes 2026 debería correrse al lunes 12"
    assert date(2026, 1, 6) not in f, "El 6 de enero de 2026 (martes) no es festivo"


def test_emiliani_no_mueve_lo_que_ya_cae_lunes():
    # San José 2029: el 19 de marzo cae lunes, se queda donde está.
    assert date(2029, 3, 19) in festivos(2029)


def test_festivos_de_semana_santa():
    # Pascua 2026 = 5 de abril. Jueves Santo 2, Viernes Santo 3.
    f = festivos(2026)
    assert date(2026, 4, 2) in f, "Jueves Santo 2026"
    assert date(2026, 4, 3) in f, "Viernes Santo 2026"


def test_pascua_correcta_en_varios_anios():
    from datetime import timedelta
    # Domingos de Pascua verificables en cualquier calendario.
    casos = {2024: date(2024, 3, 31), 2025: date(2025, 4, 20), 2026: date(2026, 4, 5)}
    for anio, domingo in casos.items():
        f = festivos(anio)
        assert (domingo - timedelta(days=3)) in f, f"Jueves Santo de {anio}"
        assert (domingo - timedelta(days=2)) in f, f"Viernes Santo de {anio}"
        assert domingo not in f, "El Domingo de Pascua no es festivo laboral"


def test_cantidad_de_festivos_por_anio():
    """
    Colombia celebra 18 festivos, pero dos pueden caer en la misma fecha y
    entonces son 17 días distintos. Pasa en 2025: San Pedro y San Pablo
    (29 jun, domingo) y Sagrado Corazón (27 jun, viernes) se corren los dos
    al lunes 30 de junio.
    """
    for anio in (2024, 2025, 2026, 2027, 2028):
        cantidad = len(festivos(anio))
        assert 17 <= cantidad <= 18, f"{anio} dio {cantidad} festivos"

    assert len(festivos(2025)) == 17, "En 2025 dos festivos coinciden el 30 de junio"
    assert date(2025, 6, 30) in festivos(2025)
    assert len(festivos(2026)) == 18


def test_es_habil():
    assert es_habil(date(2026, 8, 5)), "Miércoles normal"
    assert not es_habil(date(2026, 8, 8)), "Sábado no es hábil"
    assert not es_habil(date(2026, 8, 9)), "Domingo no es hábil"
    assert not es_habil(date(2026, 8, 7)), "Batalla de Boyacá"
    assert not es_habil(date(2026, 8, 17)), "Asunción, corrida al lunes"


def test_el_sabado_no_cuenta():
    # Decisión del negocio: la semana hábil es de lunes a viernes.
    assert not es_habil(date(2026, 8, 1))   # sábado
    assert not es_habil(date(2026, 8, 15))  # sábado


def test_siguiente_habil_salta_el_fin_de_semana():
    # Viernes 7 de agosto de 2026 es festivo (Boyacá); el jueves 6 salta al lunes 10.
    assert siguiente_habil(date(2026, 8, 6)) == date(2026, 8, 10)


def test_siguiente_habil_salta_un_festivo_que_cae_lunes():
    # Del viernes 14: sábado y domingo no cuentan, y el lunes 17 es festivo
    # (Asunción corrida). Cae en el martes 18.
    assert siguiente_habil(date(2026, 8, 14)) == date(2026, 8, 18)


def test_sumar_habiles_no_cuenta_el_dia_de_radicacion():
    # Lunes 3 + 1 hábil = martes 4, no lunes 3.
    assert sumar_habiles(date(2026, 8, 3), 1) == date(2026, 8, 4)


def test_sumar_habiles_atraviesa_fin_de_semana_y_festivo():
    # Queja radicada el viernes 14 de agosto de 2026, SLA 5 hábiles:
    #   mar 18 · mié 19 · jue 20 · vie 21 · lun 24
    # (el lunes 17 es festivo y no cuenta)
    assert sumar_habiles(date(2026, 8, 14), 5) == date(2026, 8, 24)


def test_sumar_habiles_salta_festivos():
    # Del jueves 6 de agosto: viernes 7 es festivo, así que el día 1 es el
    # lunes 10 y el día 5 el viernes 14.
    assert sumar_habiles(date(2026, 8, 6), 5) == date(2026, 8, 14)


def test_los_15_dias_de_una_peticion():
    # Radicada el lunes 3 de agosto de 2026. En el camino hay dos festivos
    # (viernes 7 y lunes 17), asi que los 15 habiles caen el miercoles 26.
    assert sumar_habiles(date(2026, 8, 3), 15) == date(2026, 8, 26)

    # En dias calendario habria vencido el 18: doce dias antes.
    from datetime import timedelta
    assert date(2026, 8, 3) + timedelta(days=15) == date(2026, 8, 18)


def test_dias_habiles_dan_mas_plazo_que_calendario():
    from datetime import timedelta
    radicacion = date(2026, 8, 14)  # viernes
    habil = sumar_habiles(radicacion, 5)
    calendario = radicacion + timedelta(days=5)
    assert habil > calendario, (
        "Contar en hábiles siempre da igual o más plazo que en calendario; "
        "si no, el sistema estaría siendo más estricto que la norma"
    )


def test_sumar_cero_no_mueve_la_fecha():
    assert sumar_habiles(date(2026, 8, 3), 0) == date(2026, 8, 3)


def test_contar_habiles():
    # Del lunes 10 al viernes 14 de agosto de 2026: 4 días hábiles después del 10.
    assert contar_habiles(date(2026, 8, 10), date(2026, 8, 14)) == 4
    # Un fin de semana entero no suma nada.
    assert contar_habiles(date(2026, 8, 15), date(2026, 8, 16)) == 0
    # Hacia atrás no cuenta.
    assert contar_habiles(date(2026, 8, 14), date(2026, 8, 10)) == 0


def test_el_limite_vence_al_cierre_del_dia():
    # Un plazo que vence "el martes" no puede estar vencido a las 00:00 de ese día.
    limite = limite_en_habiles(datetime(2026, 8, 3, 9, 0, tzinfo=timezone.utc), 1)
    assert limite.date() == date(2026, 8, 4)
    assert limite.hour == 23 and limite.minute == 59


def test_el_limite_sale_con_zona_horaria():
    # Sin zona, compararlo contra fechas de Postgres revienta.
    limite = limite_en_habiles(datetime(2026, 8, 3, 9, 0, tzinfo=timezone.utc), 5)
    assert limite.tzinfo is not None


def test_la_hora_de_radicacion_no_gasta_un_dia():
    # Radicar a las 8 a.m. o a las 5 p.m. del mismo día da el mismo límite:
    # el plazo arranca al día hábil siguiente.
    temprano = limite_en_habiles(datetime(2026, 8, 3, 8, 0, tzinfo=timezone.utc), 5)
    tarde = limite_en_habiles(datetime(2026, 8, 3, 17, 50, tzinfo=timezone.utc), 5)
    assert temprano == tarde
