"""Usuarios: el punto de venta en el que trabaja cada persona

Revision ID: c7d2e9a41f58
Revises: b8d4f21a6c93
Create Date: 2026-09-14

Hasta ahora todo el que entraba a PQRS veía las de toda la empresa. Para un
punto de venta eso es ruido: a Guayabal le importan las PQRS de Guayabal, no
las de Belén ni las de Venta institucional.

El área «Puntos de Venta» es una sola para las seis sedes, así que el área
no alcanza para saber de cuál es cada quien. Esta columna lo dice, con el
PREFIJO del canal (`PVG`, `PVC`…), que es lo que no cambia: va impreso en el
QR del mostrador y es el comienzo del radicado.

Nace vacía para todo el mundo. Alguien de «Puntos de Venta» sin punto
asignado ve las PQRS de TODOS los puntos (el coordinador); no hay que
rellenar nada para que el cambio arranque sin dejar a nadie a ciegas.
"""
from alembic import op
import sqlalchemy as sa

revision = "c7d2e9a41f58"
down_revision = "b8d4f21a6c93"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("punto_venta", sa.String(length=10), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "punto_venta")
