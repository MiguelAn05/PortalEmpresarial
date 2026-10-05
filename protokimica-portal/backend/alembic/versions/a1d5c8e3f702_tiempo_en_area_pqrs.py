"""PQRS: cada área tiene máximo 3 días hábiles

Revision ID: a1d5c8e3f702
Revises: f3a9d6b28e51
Create Date: 2026-10-05

Regla de negocio: un área no puede tener una PQRS más de 3 días hábiles, y
el conteo arranca de cero cada vez que el caso llega a un área. Ver
`modules/pqrs/tiempo_en_area.py`.

- `pqrs_solicitudes.area_desde`: desde cuándo la tiene su área actual.
- `pqrs_pasos_area`: los tramos que ya terminaron, para medir después qué
  área se demora.

Las PQRS abiertas que ya existían toman como `area_desde` el último
movimiento de área de su historial (reasignación o autorización); si nunca
se movieron, la radicación. **Eso puede dejar varias pasadas de los 3 días
el primer día**: es lo que de verdad llevan, no un error.
"""
from alembic import op
import sqlalchemy as sa

revision = "a1d5c8e3f702"
down_revision = "f3a9d6b28e51"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("pqrs_solicitudes", sa.Column("area_desde", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "pqrs_pasos_area",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("pqrs_id", sa.Integer(),
                  sa.ForeignKey("pqrs_solicitudes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("area", sa.String(100), nullable=False),
        sa.Column("desde", sa.DateTime(timezone=True), nullable=False),
        sa.Column("hasta", sa.DateTime(timezone=True), nullable=False),
        sa.Column("dias_habiles", sa.Integer(), nullable=False),
        sa.Column("excedio", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_pqrs_pasos_area_tenant_id", "pqrs_pasos_area", ["tenant_id"])
    op.create_index("ix_pqrs_pasos_area_pqrs_id", "pqrs_pasos_area", ["pqrs_id"])
    op.create_index("ix_pqrs_pasos_area_area", "pqrs_pasos_area", ["area"])

    op.execute("""
        UPDATE pqrs_solicitudes s
        SET area_desde = COALESCE(
            (SELECT MAX(g.fecha) FROM pqrs_seguimientos g
             WHERE g.pqrs_id = s.id
               AND (g.tipo_evento IN ('asignacion_area', 'autorizacion_solicitada',
                                      'autorizacion_respondida')
                    OR g.comentario LIKE '%Área:%')),
            s.fecha_creacion)
        WHERE s.estado IN ('recibido', 'asignado', 'en_proceso')
          AND s.area_responsable IS NOT NULL
    """)


def downgrade() -> None:
    op.drop_index("ix_pqrs_pasos_area_area", table_name="pqrs_pasos_area")
    op.drop_index("ix_pqrs_pasos_area_pqrs_id", table_name="pqrs_pasos_area")
    op.drop_index("ix_pqrs_pasos_area_tenant_id", table_name="pqrs_pasos_area")
    op.drop_table("pqrs_pasos_area")
    op.drop_column("pqrs_solicitudes", "area_desde")
