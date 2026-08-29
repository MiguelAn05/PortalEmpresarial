"""
Lo que ve el cliente cuando consulta su PQRS.

La regla que se prueba aquí es una sola: el cliente ve el MOVIMIENTO, nunca
lo que el área escribió por dentro. Los comentarios de los seguimientos son
notas de trabajo ("falta que bodega confirme"), y salir del portal con eso
es una fuga de información interna además de verse mal.
"""
from datetime import datetime, timezone

from app.models.pqrs import PQRSSolicitud, PQRSSeguimiento
from app.modules.pqrs.historial_publico import construir


class SeguimientoFalso:
    def __init__(self, tipo_evento, comentario=None, estado_nuevo=None, fecha=None):
        self.tipo_evento = tipo_evento
        self.comentario = comentario
        self.estado_nuevo = estado_nuevo
        self.fecha = fecha or datetime.now(timezone.utc)


def test_el_comentario_interno_no_sale_nunca(v):
    seguimientos = [SeguimientoFalso(
        "cambio_estado",
        comentario="OJO: el cliente ya llamó tres veces, revisar con bodega",
        estado_nuevo="en_proceso",
    )]
    movimientos = construir(seguimientos)

    v.check("hay un movimiento", len(movimientos) == 1, movimientos)
    v.check("el texto es el redactado, no el interno",
            movimientos[0]["movimiento"] == "Estamos trabajando en tu solicitud",
            movimientos[0])
    v.check("la nota interna no viaja",
            "bodega" not in str(movimientos[0]), movimientos[0])
    v.check("ni siquiera existe el campo comentario",
            "comentario" not in movimientos[0], movimientos[0].keys())


def test_las_notas_internas_no_aparecen_como_movimiento(v):
    """Un comentario suelto del área no es un movimiento de la solicitud."""
    seguimientos = [
        SeguimientoFalso("comentario", comentario="Llamé al cliente, no contesta"),
        SeguimientoFalso("cambio_estado", estado_nuevo="asignado"),
        SeguimientoFalso("reasignacion", comentario="Pasa de Juan a Pedro"),
    ]
    movimientos = construir(seguimientos)

    v.check("solo sale el cambio de estado", len(movimientos) == 1, movimientos)
    v.check("y es el de asignación",
            movimientos[0]["movimiento"] == "Tu solicitud fue asignada al área encargada",
            movimientos[0])


def test_cada_estado_tiene_su_texto(v):
    esperados = {
        "recibido": "Recibimos tu solicitud",
        "asignado": "Tu solicitud fue asignada al área encargada",
        "en_proceso": "Estamos trabajando en tu solicitud",
        "resuelto": "Tu solicitud fue resuelta",
        "cerrado": "Tu solicitud fue cerrada",
    }
    for estado, texto in esperados.items():
        m = construir([SeguimientoFalso("cambio_estado", estado_nuevo=estado)])
        v.check(f"'{estado}' se le explica al cliente",
                m[0]["movimiento"] == texto, m[0])


def test_un_seguimiento_viejo_sin_estado_no_revienta(v):
    """
    Los seguimientos anteriores a la migración no tienen estado guardado.
    Antes que adivinarlo leyendo el texto libre, se muestra un rótulo neutro.
    """
    m = construir([SeguimientoFalso(
        "cambio_estado", comentario="Estado actualizado a 'en_proceso'.",
    )])
    v.check("muestra un rótulo genérico",
            m[0]["movimiento"] == "Actualización de tu solicitud", m[0])
    v.check("y tampoco filtra el texto viejo",
            "en_proceso" not in m[0]["movimiento"], m[0])


def test_los_movimientos_van_en_orden(v):
    viejo = datetime(2026, 1, 1, tzinfo=timezone.utc)
    nuevo = datetime(2026, 6, 1, tzinfo=timezone.utc)
    m = construir([
        SeguimientoFalso("cambio_estado", estado_nuevo="cerrado", fecha=nuevo),
        SeguimientoFalso("cambio_estado", estado_nuevo="recibido", fecha=viejo),
    ])
    v.check("del más antiguo al más reciente",
            m[0]["movimiento"] == "Recibimos tu solicitud", m)


# ── Contra la API real ───────────────────────────────────────────────────

def test_la_consulta_publica_no_expone_notas_internas(entorno, v):
    portal = entorno
    db = portal.Session()
    solicitud = PQRSSolicitud(
        tenant_id=portal.tenant_id, tipo="reclamo", cliente_nombre="Cliente",
        descripcion="algo", estado="en_proceso", prioridad="media",
        origen_publico="publico", codigo_seguimiento="PK-2026-0001",
    )
    db.add(solicitud)
    db.commit()

    db.add(PQRSSeguimiento(
        pqrs_id=solicitud.id, tipo_evento="cambio_estado",
        estado_nuevo="en_proceso",
        comentario="El cliente es complicado, escalar con el jefe",
    ))
    db.commit()
    db.close()

    r = portal.get("/public/pqrs/PK-2026-0001")
    v.check("responde 200", r.status_code == 200, r.text[:200])

    cuerpo = r.text
    v.check("la nota interna no está en la respuesta",
            "complicado" not in cuerpo and "escalar" not in cuerpo, cuerpo[:400])
    v.check("sí está el movimiento redactado",
            "Estamos trabajando en tu solicitud" in cuerpo, cuerpo[:400])
