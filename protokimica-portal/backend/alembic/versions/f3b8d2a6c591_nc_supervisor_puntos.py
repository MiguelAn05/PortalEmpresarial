"""notas crédito: las del mostrador con producto pasan primero por el supervisor

`nc_solicitudes.por_producto`: si el motivo traía producto al radicarla. Hasta
aquí la cadena lo deducía de `bodega`, que solo se llena en la institucional;
el mostrador no tiene bodega, y ahora también cambia de cadena con producto
(supervisor de los puntos → Comercial → el punto emite).

Se llena así:
- institucional: con bodega, que es exactamente lo que se miraba antes;
- mostrador: por la marca del motivo. Las que ya pasaron el primer turno no
  se devuelven al supervisor —su estado sigue estando en la cadena nueva—;
  solo las devueltas que se reenvíen empezarán por él, que es lo correcto.

La capacidad `notas_credito.supervisar_punto` NO se siembra: es de una
persona, y se otorga en Administración › Capacidades.

Revision ID: f3b8d2a6c591
Revises: e5a9c3d7b104
Create Date: 2026-11-03 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'f3b8d2a6c591'
down_revision = 'e5a9c3d7b104'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('nc_solicitudes', sa.Column(
        'por_producto', sa.Boolean(), nullable=False, server_default=sa.false(),
    ))
    op.execute("""
        UPDATE nc_solicitudes SET por_producto = TRUE
        WHERE (institucional AND bodega IS NOT NULL)
           OR (NOT institucional AND motivo_id IN (
                SELECT id FROM nc_motivos WHERE requiere_bodega))
    """)


def downgrade() -> None:
    # Las que esperan al supervisor no tienen turno en la cadena vieja:
    # vuelven a Comercial, que es donde la vieja las habría puesto.
    op.execute("UPDATE nc_solicitudes SET estado = 'en_comercial' WHERE estado = 'en_supervision'")
    op.drop_column('nc_solicitudes', 'por_producto')
