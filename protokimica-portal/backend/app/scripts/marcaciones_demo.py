"""
Datos de ejemplo para ver Marcaciones en un portal LOCAL, sin el reloj.

    docker exec protokimica_backend python -m app.scripts.marcaciones_demo protokimica
    docker exec protokimica_backend python -m app.scripts.marcaciones_demo protokimica --quitar

Crea unas personas «DEMO» con marcaciones de hoy y de los últimos días
(llegada tarde, ausencia, exceso de almuerzo, turno por confirmar…) pasando
por el mismo `service.sincronizar` que usa el script real. `--quitar` borra
solo lo que creó (los códigos que empiezan por `DEMO`).

**Se niega a correr si `ENVIRONMENT=production`**: son datos inventados y no
deben mezclarse con las marcaciones de verdad.
"""
import argparse
import sys
from datetime import datetime, timedelta

from app.core.config import settings
from app.core.database import SessionLocal
from app.main import app  # noqa: F401  (carga todos los modelos)
from app.models.marcaciones import MarEmpleado, MarMarcacion
from app.models.tenant import Tenant
from app.modules.marcaciones import service

LABORAL = {"lun": "07:00-17:00", "mar": "07:00-17:00", "mie": "07:00-17:00", "jue": "07:00-17:00",
           "vie": "07:00-17:00", "sab": "", "dom": ""}
PERSONAS = [
    ("DEMO01", "Ana Puntual", "TICS", LABORAL),
    ("DEMO02", "Beto Tarde", "TICS", LABORAL),
    ("DEMO03", "Carla Ausente", "Logística", LABORAL),
    ("DEMO04", "Luis Almuerzo", "Logística", LABORAL),
    ("DEMO05", "Elena Break", "Gestión Humana", LABORAL),
    ("DEMO06", "Mario Turnos", "Producción", {**LABORAL, **{d: "06:00-14:00/14:00-22:00" for d in ("lun", "mar", "mie", "jue", "vie")}}),
    ("DEMO07", "Sofía Salida", "Producción", LABORAL),
]


def _m(codigo, dia, hm, estado):
    return {"emp_code": codigo, "momento": datetime.fromisoformat(f"{dia.isoformat()} {hm}:00"), "estado": estado}


def _marcas_de(dia, hoy):
    """Un día de marcaciones con las historias de cada persona."""
    m = [
        _m("DEMO01", dia, "06:57", "0"), _m("DEMO01", dia, "17:02", "1"),
        _m("DEMO02", dia, "07:35", "0"),
        _m("DEMO04", dia, "06:55", "0"), _m("DEMO04", dia, "12:00", "2"), _m("DEMO04", dia, "13:05", "3"),
        _m("DEMO05", dia, "06:58", "0"), _m("DEMO05", dia, "09:30", "2"), _m("DEMO05", dia, "09:52", "3"),
        _m("DEMO06", dia, "13:50", "0"),
        _m("DEMO07", dia, "07:00", "0"), _m("DEMO07", dia, "15:30", "1"),
    ]
    if dia == hoy:   # hoy solo lo que ya pasó, para que se vea «en vivo»
        ahora = service.ahora_local().strftime("%H:%M")
        m = [x for x in m if x["momento"].strftime("%H:%M") <= ahora]
    return m


def main() -> None:
    parser = argparse.ArgumentParser(description="Datos de ejemplo de Marcaciones (solo local).")
    parser.add_argument("slug")
    parser.add_argument("--quitar", action="store_true")
    args = parser.parse_args()
    if settings.ENVIRONMENT == "production":
        sys.exit("Se niega a correr en producción: son datos inventados.")

    db = SessionLocal()
    try:
        tenant = db.query(Tenant).filter(Tenant.slug == args.slug).first()
        if not tenant:
            sys.exit(f"No existe la empresa «{args.slug}».")
        if args.quitar:
            n = db.query(MarMarcacion).filter(MarMarcacion.tenant_id == tenant.id, MarMarcacion.emp_code.like("DEMO%")).delete(synchronize_session=False)
            e = db.query(MarEmpleado).filter(MarEmpleado.tenant_id == tenant.id, MarEmpleado.emp_code.like("DEMO%")).delete(synchronize_session=False)
            db.commit()
            print(f"Quitados {e} empleados y {n} marcaciones de ejemplo.")
            return
        if db.query(MarEmpleado).filter(MarEmpleado.tenant_id == tenant.id, ~MarEmpleado.emp_code.like("DEMO%")).count():
            sys.exit("Ya hay personas reales en la malla: no se mezclan con las de ejemplo. Usa --quitar si sobran.")

        hoy = service.ahora_local().date()   # la hora de la empresa, no la del contenedor (UTC)
        empleados = [{"emp_code": c, "nombre": n, "area": a, "correo": None, **t} for c, n, a, t in PERSONAS]
        marcaciones = []
        for atras in range(0, 6):
            dia = hoy - timedelta(days=atras)
            if dia.weekday() < 5:
                marcaciones += _marcas_de(dia, hoy)
        resumen = service.sincronizar(db, tenant.id, {"empleados": empleados, "marcaciones": marcaciones})
        service.registrar(db, tenant.id, resumen=resumen)
        db.commit()
        print(f"Listo: {len(empleados)} personas y {resumen['marcaciones_nuevas']} marcaciones de ejemplo.")
        print("Abre Marcaciones y recarga. Para borrarlas: --quitar")
    finally:
        db.close()


if __name__ == "__main__":
    main()
