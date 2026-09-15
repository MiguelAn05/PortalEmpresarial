"""Indicadores con fórmula personalizada (80 × A ÷ B)

Revision ID: e1b7c3d9a2f4
Revises: d9e4a7b2c1f3
Create Date: 2026-09-14

Hasta ahora un indicador manual era un valor digitado o numerador ÷
denominador. Los que Calidad define con constantes, restas o tres variables
se calculaban en Excel y se digitaba el resultado, perdiendo los números de
base — y con ellos el acumulado correcto del trimestre.

- `ind_indicadores.formula`: la expresión con letras (`80 * A / B`).
- `ind_variables`: qué significa cada letra en cada indicador.
- `ind_valores_variable`: lo que se digitó de cada variable en cada mes.

Es un tipo de captura nuevo (`formula`). Los indicadores existentes no se
tocan: ninguno tiene fórmula, así que no hay datos que mover.
"""
from alembic import op
import sqlalchemy as sa

revision = "e1b7c3d9a2f4"
down_revision = "d9e4a7b2c1f3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ind_indicadores", sa.Column("formula", sa.Text(), nullable=True))

    op.create_table(
        "ind_variables",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "indicador_id", sa.Integer(),
            sa.ForeignKey("ind_indicadores.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("letra", sa.String(length=1), nullable=False),
        sa.Column("etiqueta", sa.String(length=120), nullable=False),
        sa.UniqueConstraint("indicador_id", "letra", name="uq_variable_letra"),
    )
    op.create_index("ix_ind_variables_indicador_id", "ind_variables", ["indicador_id"])

    op.create_table(
        "ind_valores_variable",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "medicion_id", sa.Integer(),
            sa.ForeignKey("ind_mediciones.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("letra", sa.String(length=1), nullable=False),
        sa.Column("valor", sa.Numeric(16, 4), nullable=False),
        sa.UniqueConstraint("medicion_id", "letra", name="uq_valor_variable_letra"),
    )
    op.create_index("ix_ind_valores_variable_medicion_id", "ind_valores_variable", ["medicion_id"])


def downgrade() -> None:
    op.drop_index("ix_ind_valores_variable_medicion_id", table_name="ind_valores_variable")
    op.drop_table("ind_valores_variable")
    op.drop_index("ix_ind_variables_indicador_id", table_name="ind_variables")
    op.drop_table("ind_variables")
    op.drop_column("ind_indicadores", "formula")
