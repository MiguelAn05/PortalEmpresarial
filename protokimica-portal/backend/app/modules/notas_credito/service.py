"""
Lo que calcula el servidor para las notas crédito: el consecutivo y la
semilla del catálogo de motivos.
"""
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.nota_credito import MotivoNotaCredito, SolicitudNotaCredito

# Con qué motivos arranca la lista. Son un punto de partida sacado de los
# correos que hoy se mandan, NO la lista definitiva: Contabilidad la ajusta
# desde Administración sin pedir un despliegue, que es justamente para lo que
# esto es una tabla y no un enum.
SEMILLA_MOTIVOS = [
    "Error de digitación en la factura",
    "Cambio de producto",
    "Devolución de mercancía",
    "Cobro de más al cliente",
    "Producto en mal estado",
    "Otro",
]


def sembrar_motivos(db: Session, tenant_id: int) -> None:
    """
    Deja el catálogo listo para esta empresa.

    Solo agrega lo que falta: nunca reescribe ni reactiva. Una siembra que
    pisara los cambios le devolvería a Contabilidad, en cada arranque, los
    motivos que ya había desactivado.
    """
    existentes = {
        nombre for (nombre,) in db.query(MotivoNotaCredito.nombre)
        .filter(MotivoNotaCredito.tenant_id == tenant_id).all()
    }
    nuevos = [
        MotivoNotaCredito(tenant_id=tenant_id, nombre=nombre, activo=True)
        for nombre in SEMILLA_MOTIVOS if nombre not in existentes
    ]
    if nuevos:
        db.add_all(nuevos)
        db.commit()


def generar_codigo(db: Session, tenant_id: int) -> str:
    """
    NC-2026-0001, y el siguiente sale del MÁXIMO.

    Nunca de un `count()`. Ese error ya mordió dos veces en este portal —el
    código de seguimiento y el radicado de Calidad—: con NC-2026-0001 y
    NC-2026-0003 en la tabla, contar da 2 y el siguiente sale NC-2026-0003,
    que ya existe.
    """
    anio = datetime.now().year
    prefijo = f"NC-{anio}-"
    codigos = (
        db.query(SolicitudNotaCredito.codigo)
        .filter(
            SolicitudNotaCredito.tenant_id == tenant_id,
            SolicitudNotaCredito.codigo.isnot(None),
            SolicitudNotaCredito.codigo.like(f"{prefijo}%"),
        )
        .all()
    )

    # El máximo se saca del número, no del texto: pasado el 9999, el orden
    # alfabético pondría "10000" antes que "9999".
    mayor = 0
    for (codigo,) in codigos:
        sufijo = (codigo or "")[len(prefijo):]
        if sufijo.isdigit():
            mayor = max(mayor, int(sufijo))

    return f"{prefijo}{mayor + 1:04d}"
