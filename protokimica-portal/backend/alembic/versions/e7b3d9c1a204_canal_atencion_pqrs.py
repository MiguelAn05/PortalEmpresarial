"""canal de atencion en pqrs

El campo canal_atencion existía en el modelo PQRSSolicitud y lo usan el
router, el generador de código de seguimiento y las notificaciones, pero
nunca se generó su migración. Resultado: en cualquier equipo con la base
creada solo desde Alembic, GET /pqrs reventaba con
"column pqrs_solicitudes.canal_atencion does not exist".

Se usa ADD COLUMN IF NOT EXISTS a propósito: en el equipo donde se
desarrolló el campo la columna ya fue creada a mano, y con un
op.add_column normal esta migración fallaría ahí.

Revision ID: e7b3d9c1a204
Revises: c3f9b0a2e847
Create Date: 2026-08-03 08:05:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e7b3d9c1a204'
down_revision = 'c3f9b0a2e847'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE pqrs_solicitudes "
        "ADD COLUMN IF NOT EXISTS canal_atencion VARCHAR(50)"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE pqrs_solicitudes "
        "DROP COLUMN IF EXISTS canal_atencion"
    )
