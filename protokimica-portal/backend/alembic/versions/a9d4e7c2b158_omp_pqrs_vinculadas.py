"""OMP: varias PQRS por la misma causa en una sola OMP

Revision ID: a9d4e7c2b158
Revises: f3b8d2a6c591
Create Date: 2026-11-04

Cada PQRS por la misma causa abría su propia OMP. Ahora la OMP guarda de
qué causa nació (`clave_causa`) y las PQRS siguientes se le vinculan en
`omp_pqrs_vinculadas`.

Las OMP que ya nacieron de una PQRS toman la causa que esa PQRS tiene hoy:
es la única que se conoce. La forma de la clave es la de
`pqrs/origen_omp.py` («pqrs_asociado:<id>»).
"""
from alembic import op
import sqlalchemy as sa

revision = "a9d4e7c2b158"
down_revision = "f3b8d2a6c591"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "omp_oportunidades", sa.Column("clave_causa", sa.String(60), nullable=True),
    )
    op.create_index(
        "ix_omp_oportunidades_clave_causa", "omp_oportunidades", ["clave_causa"],
    )
    op.execute("""
        UPDATE omp_oportunidades o
        SET clave_causa = 'pqrs_asociado:' || p.asociado_id
        FROM pqrs_solicitudes p
        WHERE o.pqrs_id = p.id AND p.asociado_id IS NOT NULL
    """)

    op.create_table(
        "omp_pqrs_vinculadas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("omp_id", sa.Integer(),
                  sa.ForeignKey("omp_oportunidades.id", ondelete="CASCADE"), nullable=False),
        sa.Column("pqrs_id", sa.Integer(),
                  sa.ForeignKey("pqrs_solicitudes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("referencia", sa.String(60), nullable=False),
        sa.Column("vinculado_por", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("vinculado_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("omp_id", "pqrs_id", name="uq_omp_pqrs_vinculada"),
    )
    op.create_index("ix_omp_pqrs_vinculadas_id", "omp_pqrs_vinculadas", ["id"])
    op.create_index("ix_omp_pqrs_vinculadas_omp_id", "omp_pqrs_vinculadas", ["omp_id"])
    op.create_index("ix_omp_pqrs_vinculadas_pqrs_id", "omp_pqrs_vinculadas", ["pqrs_id"])


def downgrade() -> None:
    op.drop_table("omp_pqrs_vinculadas")
    op.drop_index("ix_omp_oportunidades_clave_causa", table_name="omp_oportunidades")
    op.drop_column("omp_oportunidades", "clave_causa")
