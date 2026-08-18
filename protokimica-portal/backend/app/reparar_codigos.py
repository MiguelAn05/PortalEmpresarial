"""
Le pone código de seguimiento a las PQRS que quedaron sin él.

Mientras el consecutivo se calculó contando (y no tomando el más alto), una
PQRS radicada podía chocar contra el índice único justo al guardar su código.
La solicitud quedaba guardada —el commit anterior ya había pasado— pero sin
código: el cliente no puede consultarla y nadie recibió el aviso.

Este script las busca y les asigna el siguiente código libre de su canal,
respetando los consecutivos que ya existen. No toca ninguna que ya tenga
código.

    docker exec protokimica_backend python -m app.reparar_codigos          # ver
    docker exec protokimica_backend python -m app.reparar_codigos --aplicar

Sin `--aplicar` solo enseña lo que haría. Es a propósito: en producción se
mira antes de escribir.
"""
import sys

import app.main  # noqa: F401  — registra todos los modelos
from app.core.database import SessionLocal
from app.models.pqrs import PQRSSolicitud
from app.modules.pqrs.service import asignar_codigo_seguimiento


def main(aplicar: bool) -> int:
    db = SessionLocal()
    try:
        huerfanas = (
            db.query(PQRSSolicitud)
            .filter(
                (PQRSSolicitud.codigo_seguimiento.is_(None))
                | (PQRSSolicitud.codigo_seguimiento == "")
            )
            .order_by(PQRSSolicitud.id)
            .all()
        )

        if not huerfanas:
            print("Ninguna PQRS quedó sin código. No hay nada que reparar.")
            return 0

        print(f"PQRS sin código de seguimiento: {len(huerfanas)}\n")
        for p in huerfanas:
            fecha = p.fecha_creacion.strftime("%Y-%m-%d %H:%M") if p.fecha_creacion else "?"
            print(f"  #{p.id}  {fecha}  {p.tipo:12} {(p.cliente_nombre or '')[:28]:28} "
                  f"canal={p.canal_atencion or '—'}")

        if not aplicar:
            print("\nEsto es solo la vista previa. Para asignarlos de verdad:")
            print("  docker exec protokimica_backend python -m app.reparar_codigos --aplicar")
            return 0

        print()
        for p in huerfanas:
            codigo = asignar_codigo_seguimiento(db, p, p.tenant_id, p.canal_atencion)
            print(f"  #{p.id} -> {codigo}")

        print(f"\nListo: {len(huerfanas)} PQRS reparadas.")
        print("Avísale el código a cada cliente si te escribió preguntando por su")
        print("solicitud: para él, hasta ahora, no existía.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main(aplicar="--aplicar" in sys.argv))
