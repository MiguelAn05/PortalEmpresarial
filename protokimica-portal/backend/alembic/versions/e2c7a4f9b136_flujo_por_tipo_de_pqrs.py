"""Flujos de PQRS: la plantilla también depende del tipo (reclamo, queja…)

Revision ID: e2c7a4f9b136
Revises: d5a2e7c1b839
Create Date: 2026-10-10

Hasta aquí la plantilla se escogía solo por el canal, así que una queja o una
felicitación de venta institucional recibía la cadena de un reclamo por
producto (bodega → técnico → Financiera → Contable → Cartera).

1. `pqrs_flujos.tipos_pqrs`: para qué tipos sirve; vacío, cualquiera.
2. Las plantillas que ya existen salieron del análisis de los reclamos, así
   que quedan para reclamos. Los demás tipos se quedan sin plantilla hasta
   que se defina la suya en Administración › Flujos de PQRS; mientras tanto
   sus pasos se arman a mano.
"""
from alembic import op
import sqlalchemy as sa

revision = "e2c7a4f9b136"
down_revision = "d5a2e7c1b839"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("pqrs_flujos", sa.Column("tipos_pqrs", sa.String(100), nullable=True))
    op.execute("UPDATE pqrs_flujos SET tipos_pqrs = 'reclamo' WHERE tipos_pqrs IS NULL")


def downgrade():
    op.drop_column("pqrs_flujos", "tipos_pqrs")
