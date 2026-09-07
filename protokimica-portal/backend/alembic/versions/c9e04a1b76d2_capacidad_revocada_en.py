"""Capacidades otorgadas: revocar marca, no borra

Revision ID: c9e04a1b76d2
Revises: b3d81e9f2c47
Create Date: 2026-09-05

`revocar()` hacía DELETE. El problema: un borrado no se distingue de "esto
nunca se otorgó", así que `sembrar_capacidades_iniciales()` —que deja la
tabla al día con las reglas base en cada arranque— le devolvía a un área una
capacidad que un administrador le había quitado a propósito el día antes.
Se detectó con la propia prueba comparativa de esta fase, antes de que
ningún módulo llegara a depender de esto.

`revocada_en` NULL es vigente; con fecha es revocada. `tiene()` y
`quienes_tienen()` ya filtran por esto; la siembra ya cuenta ambas como
"ya existe" para no re-otorgar lo revocado.
"""
from alembic import op
import sqlalchemy as sa

revision = "c9e04a1b76d2"
down_revision = "b3d81e9f2c47"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "capacidades_otorgadas",
        sa.Column("revocada_en", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("capacidades_otorgadas", "revocada_en")
