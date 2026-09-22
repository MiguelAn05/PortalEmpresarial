"""
Cuánto aguanta la lista de PQRS: siembra N solicitudes, mide y las borra.

Existe porque «hoy funciona muy bien» es cierto y no dice nada sobre mañana:
el histórico no se borra y la lista crece con él. Esto responde con números
—milisegundos y megabytes por respuesta— en vez de con impresiones, y sirve
para decidir CUÁNDO toca paginar en el servidor y no antes.

    docker exec protokimica_backend python -m app.medir_lista_pqrs
    docker exec protokimica_backend python -m app.medir_lista_pqrs --filas 20000

**Va contra la base de DESARROLLO.** Se niega a correr si la base ya tiene
más PQRS de las que se van a sembrar, que es la señal más barata de estar en
producción por error. Las filas de prueba se marcan y se borran al final,
incluso si la medición falla.
"""
import argparse
import json
import time

from sqlalchemy.orm import load_only

import app.main  # noqa: F401  — registra todos los modelos
from app.core.database import SessionLocal
from app.models.pqrs import PQRSProducto, PQRSSolicitud
from app.models.tenant import Tenant
from app.modules.pqrs.schemas import PQRSResumenOut

# Va en la descripción de cada fila sembrada: es lo que permite borrarlas
# después sin tocar una sola PQRS de verdad.
MARCA = "MEDICION-TEMPORAL-BORRAR"

# Tope de cordura: más PQRS de estas en la base significa que no es la de
# desarrollo. Mejor parar que sembrar cinco mil filas en producción.
MAXIMO_EXISTENTES = 500


def _sembrar(db, tenant_id: int, filas: int) -> None:
    lote = []
    for i in range(filas):
        solicitud = PQRSSolicitud(
            tenant_id=tenant_id, tipo="reclamo", estado="recibido", prioridad="media",
            cliente_nombre=f"Cliente {i}", empresa=f"Empresa {i} S.A.S.",
            area_responsable="Calidad",
            # Una descripción larga como las reales: es lo que más pesa.
            descripcion=("x" * 1800) + MARCA,
            codigo_seguimiento=f"MED{i:07d}",
        )
        solicitud.productos = [
            PQRSProducto(orden=0, producto_nombre="Hipoclorito 13%", lote="L-1"),
            PQRSProducto(orden=1, producto_nombre="Soda cáustica", lote="L-2"),
        ]
        lote.append(solicitud)
    db.add_all(lote)
    db.commit()


def _borrar(db) -> int:
    ids = db.query(PQRSSolicitud.id).filter(PQRSSolicitud.descripcion.like(f"%{MARCA}"))
    db.query(PQRSProducto).filter(PQRSProducto.pqrs_id.in_(ids)).delete(
        synchronize_session=False)
    borradas = db.query(PQRSSolicitud).filter(
        PQRSSolicitud.descripcion.like(f"%{MARCA}")).delete(synchronize_session=False)
    db.commit()
    return borradas


def _medir(db, tenant_id: int) -> None:
    """Lo mismo que hace el endpoint: consultar, serializar, volverlo JSON."""
    db.expire_all()
    inicio = time.perf_counter()
    objetos = (
        db.query(PQRSSolicitud)
        .options(load_only(*(getattr(PQRSSolicitud, c) for c in PQRSResumenOut.model_fields)))
        .filter(PQRSSolicitud.tenant_id == tenant_id)
        .order_by(PQRSSolicitud.fecha_creacion.desc())
        .all()
    )
    cuerpo = json.dumps([
        PQRSResumenOut.model_validate(o, from_attributes=True).model_dump(mode="json")
        for o in objetos
    ])
    ms = (time.perf_counter() - inicio) * 1000

    print(f"  {len(objetos):>7} filas · {ms:>7.0f} ms · "
          f"{len(cuerpo) / 1_048_576:>6.2f} MB · "
          f"{len(cuerpo) // max(len(objetos), 1)} bytes por fila")
    print("\n  El servidor es solo una parte: a esto hay que sumarle la red y,")
    print("  sobre todo, lo que tarda el navegador en pintar esas filas.")


def main(filas: int) -> int:
    db = SessionLocal()
    try:
        tenant = db.query(Tenant).first()
        if tenant is None:
            print("No hay ningún tenant: ¿la base está vacía?")
            return 1

        existentes = db.query(PQRSSolicitud).filter(
            PQRSSolicitud.tenant_id == tenant.id).count()
        if existentes > MAXIMO_EXISTENTES:
            print(f"La base tiene {existentes} PQRS. Esto siembra y borra filas de")
            print("prueba, así que solo corre contra la base de desarrollo.")
            return 1

        print(f"PQRS antes de medir: {existentes}")
        print(f"Sembrando {filas}…")
        _sembrar(db, tenant.id, filas)
        _medir(db, tenant.id)
    finally:
        print(f"\nBorradas {_borrar(db)} filas de prueba.")
        db.close()
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--filas", type=int, default=5000,
                        help="cuántas PQRS sembrar para la medición (por defecto 5000)")
    raise SystemExit(main(parser.parse_args().filas))
