"""
El informe gerencial de PQRS (`pqrs/informe.py`).

Lo que se prueba: el periodo es por fecha de radicación en la hora de la
empresa, los porcentajes salen del servidor, la causa se mide sobre las que
tienen causa, «quién radicó» distingue al cliente del área interna, se
compara con el periodo anterior, y cada quien ve el informe de lo que puede
ver.
"""
from datetime import datetime, timedelta, timezone

from app.models.pqrs import PQRSSeguimiento, PQRSSolicitud
from app.models.user import User
from app.modules.pqrs import asociados

# 15 de septiembre de 2026, a mediodía en Colombia (17:00 UTC).
SEP = datetime(2026, 9, 15, 17, 0, tzinfo=timezone.utc)
AGO = datetime(2026, 8, 15, 17, 0, tzinfo=timezone.utc)


def _pqrs(entorno, tipo="reclamo", fecha=SEP, canal=None, origen="publico", estado="en_proceso",
          asociado=None, area_causante=None, creador=None, limite_dias=8, resuelta_dias=None):
    db = entorno.Session()
    p = PQRSSolicitud(
        tenant_id=entorno.tenant_id, tipo=tipo, cliente_nombre="C", descripcion="x",
        estado=estado, prioridad="media", origen_publico=origen, canal_atencion=canal,
        fecha_creacion=fecha, fecha_limite_sla=fecha + timedelta(days=limite_dias),
        fecha_resuelto=fecha + timedelta(days=resuelta_dias) if resuelta_dias is not None else None,
        asociado_id=asociado, area_causante=area_causante,
    )
    db.add(p)
    db.flush()
    db.add(PQRSSeguimiento(pqrs_id=p.id, usuario_id=creador, tipo_evento="cambio_estado",
                           comentario="Radicada.", estado_nuevo="recibido"))
    db.commit()
    pid = p.id
    db.close()
    return pid


def _informe(entorno, desde="2026-09-01", hasta="2026-09-30"):
    r = entorno.get("/pqrs/informe", params={"desde": desde, "hasta": hasta})
    assert r.status_code == 200, r.text
    return r.json()


def _fila(filas, etiqueta):
    return next((f for f in filas if f["etiqueta"] == etiqueta), None)


def test_cuenta_por_tipo_con_porcentaje_del_servidor(entorno, v):
    for tipo in ("reclamo", "reclamo", "queja", "peticion"):
        _pqrs(entorno, tipo=tipo)
    _pqrs(entorno, fecha=AGO)  # de agosto: no cuenta en septiembre

    inf = _informe(entorno)
    v.check("cuatro en septiembre", inf["resumen"]["total"] == 4, inf["resumen"])
    reclamo = _fila(inf["por_tipo"], "Reclamo")
    v.check("los reclamos primero, con su porcentaje", inf["por_tipo"][0] == reclamo
            and reclamo["n"] == 2 and reclamo["pct"] == 50.0, inf["por_tipo"])
    v.check("compara con agosto", inf["resumen"]["total_anterior"] == 1, inf["resumen"])
    v.check("y dice cuánto subió", inf["resumen"]["variacion_pct"] == 300.0, inf["resumen"])
    v.check("con el nombre del periodo", inf["periodo"]["etiqueta"] == "Septiembre de 2026", inf["periodo"])


def test_el_dia_empieza_a_medianoche_en_colombia(entorno, v):
    # 1 de octubre a las 2 a. m. UTC = 30 de septiembre, 9 p. m. en Colombia.
    _pqrs(entorno, fecha=datetime(2026, 10, 1, 2, 0, tzinfo=timezone.utc))
    v.check("cuenta para septiembre", _informe(entorno)["resumen"]["total"] == 1)
    v.check("y no para octubre",
            _informe(entorno, "2026-10-01", "2026-10-31")["resumen"]["total"] == 0)


def test_la_causa_se_mide_sobre_las_que_tienen_causa(entorno, v):
    db = entorno.Session()
    catalogo = {a.nombre: a.id for a in asociados.del_tenant(db, entorno.tenant_id)}
    db.close()
    me = catalogo["Mala Entrega (CEDI)"]
    _pqrs(entorno, asociado=me, area_causante="Logística")
    _pqrs(entorno, asociado=me, area_causante="Logística")
    _pqrs(entorno, asociado=catalogo["Fecha de vencimiento"], area_causante="Producción")
    _pqrs(entorno)  # sin causa

    inf = _informe(entorno)
    v.check("tres con causa, una sin", inf["resumen"]["con_causa"] == 3 and inf["resumen"]["sin_causa"] == 1,
            inf["resumen"])
    fila = _fila(inf["por_asociado"], "(ME) Mala Entrega (CEDI)")
    v.check("la mala entrega pesa dos de tres, no dos de cuatro",
            fila and fila["n"] == 2 and fila["pct"] == 66.7, inf["por_asociado"])
    v.check("con su grupo", fila["grupo"] == "Entrega")
    v.check("y por grupo también", _fila(inf["por_grupo_causa"], "Entrega")["n"] == 2)
    v.check("área causante", _fila(inf["por_area_causante"], "Logística")["n"] == 2, inf["por_area_causante"])


def test_quien_radico_y_por_que_canal(entorno, v):
    db = entorno.Session()
    db.get(User, entorno.ids["calidad"]).area = "Servicio al Cliente"
    db.commit()
    db.close()
    _pqrs(entorno, origen="publico", canal="WhatsApp")
    _pqrs(entorno, origen="publico", canal="WhatsApp")
    _pqrs(entorno, origen="interno", creador=entorno.ids["calidad"], canal="Línea telefónica")

    inf = _informe(entorno)
    v.check("el cliente por el formulario", _fila(inf["por_origen"], "Cliente (formulario web)")["n"] == 2,
            inf["por_origen"])
    v.check("y por dentro, el área de quien la registró",
            _fila(inf["por_origen"], "Interno · Servicio al Cliente")["n"] == 1, inf["por_origen"])
    v.check("por canal", _fila(inf["por_canal"], "WhatsApp")["n"] == 2, inf["por_canal"])


def test_tiempos_de_respuesta(entorno, v):
    _pqrs(entorno, resuelta_dias=2, estado="resuelto")             # a tiempo
    _pqrs(entorno, resuelta_dias=20, estado="resuelto")            # tarde
    _pqrs(entorno, fecha=SEP, limite_dias=1, estado="en_proceso")  # abierta y vencida

    r = _informe(entorno)["resumen"]
    v.check("dos respondidas", r["respondidas"] == 2, r)
    v.check("una a tiempo: 50%", r["a_tiempo"] == 1 and r["pct_a_tiempo"] == 50.0, r)
    v.check("una abierta y vencida", r["abiertas"] == 1 and r["vencidas"] == 1, r)
    v.check("promedio en días hábiles", r["dias_respuesta_promedio"] is not None, r)


def test_tendencia_por_dia_en_un_mes(entorno, v):
    _pqrs(entorno)
    t = _informe(entorno)["tendencia"]
    v.check("día por día", t["escala"] == "dia" and len(t["puntos"]) == 30, (t["escala"], len(t["puntos"])))
    v.check("con el día 15 marcado", t["puntos"][14]["n"] == 1, t["puntos"][14])
    largo = _informe(entorno, "2026-01-01", "2026-09-30")["tendencia"]
    v.check("en un periodo largo, por mes", largo["escala"] == "mes" and len(largo["puntos"]) == 9,
            (largo["escala"], len(largo["puntos"])))


def test_un_periodo_invalido_dice_que_corregir(entorno, v):
    r = entorno.get("/pqrs/informe", params={"desde": "2026-09-30", "hasta": "2026-09-01"})
    v.check("al revés -> 400", r.status_code == 400 and "posterior" in r.json()["detail"], r.text[:200])
    r = entorno.get("/pqrs/informe", params={"desde": "2020-01-01", "hasta": "2026-09-01"})
    v.check("demasiado largo -> 400", r.status_code == 400 and "por partes" in r.json()["detail"], r.text[:200])


def test_sin_fechas_es_el_mes_en_curso(entorno, v):
    r = entorno.get("/pqrs/informe")
    v.check("responde", r.status_code == 200, r.text[:200])
    v.check("desde el primero del mes", r.json()["periodo"]["desde"].endswith("-01"), r.json()["periodo"])


def test_lectura_tambien_lo_ve(entorno, v):
    """Leer un informe no escribe nada: lo ve cualquiera que vea PQRS."""
    entorno.como("lectura")
    r = entorno.get("/pqrs/informe")
    v.check("lectura -> 200", r.status_code == 200, r.status_code)
