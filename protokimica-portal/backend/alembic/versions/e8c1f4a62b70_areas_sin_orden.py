"""Las áreas se ordenan alfabéticamente: se quita la columna de orden

Revision ID: e8c1f4a62b70
Revises: d2b7e5a83c19
Create Date: 2026-10-01

Administración › Áreas tenía flechas para subir y bajar un área, que solo
cambiaban su posición en los desplegables. Se leían como si un área tuviera
más nivel que otra, y con más de veinte áreas el orden que la gente sabe
recorrer es el alfabético. Ahora se ordenan solas (`core.areas.nombres`) y la
columna sobra.
"""
from alembic import op
import sqlalchemy as sa

revision = "e8c1f4a62b70"
down_revision = "d2b7e5a83c19"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("areas", "orden")


def downgrade() -> None:
    op.add_column("areas", sa.Column("orden", sa.Integer(), nullable=False, server_default="0"))
