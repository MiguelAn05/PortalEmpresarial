"""flujo de aprobacion y pago del presupuesto

El dinero de un proyecto pasa por tres etapas: planeado -> aprobado -> pagado.
Administracion aprueba el desembolso y Tesoreria registra los abonos.

Sobre `valor_ejecutado`: era el intento anterior de decir "pagado". No se
borra su contenido — se convierte en un abono inicial por ese valor, para que
lo ya cargado siga contando. Cada item que tenia ejecutado > 0 queda ademas
aprobado por ese mismo monto, porque un pago que ya ocurrio implica que
estaba autorizado.

Revision ID: c5a71e3b9d82
Revises: b9e2f4a17c05
Create Date: 2026-08-07 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'c5a71e3b9d82'
down_revision = 'b9e2f4a17c05'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('mp_items_presupuesto', sa.Column('valor_aprobado', sa.Numeric(14, 2), nullable=True))
    op.add_column('mp_items_presupuesto', sa.Column('aprobado_por', sa.Integer(), nullable=True))
    op.add_column('mp_items_presupuesto', sa.Column('aprobado_en', sa.DateTime(timezone=True), nullable=True))
    op.add_column('mp_items_presupuesto', sa.Column('nota_aprobacion', sa.Text(), nullable=True))
    op.create_foreign_key(
        'fk_mp_items_aprobado_por', 'mp_items_presupuesto', 'users', ['aprobado_por'], ['id'],
    )

    op.create_table(
        'mp_pagos',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('item_id', sa.Integer(), nullable=False),
        sa.Column('valor', sa.Numeric(14, 2), nullable=False),
        sa.Column('fecha', sa.DateTime(timezone=True), nullable=False),
        sa.Column('concepto', sa.String(length=200), nullable=True),
        sa.Column('soporte', sa.String(length=255), nullable=True),
        sa.Column('registrado_por', sa.Integer(), nullable=True),
        sa.Column('registrado_en', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['item_id'], ['mp_items_presupuesto.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['registrado_por'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_mp_pagos_id'), 'mp_pagos', ['id'])
    op.create_index(op.f('ix_mp_pagos_item_id'), 'mp_pagos', ['item_id'])

    # Lo que ya estaba en valor_ejecutado se convierte en un abono, y el item
    # queda aprobado por ese monto: si ya se pago, estaba autorizado.
    conn = op.get_bind()
    ejecutados = conn.execute(sa.text(
        "SELECT id, valor_ejecutado, creado_en FROM mp_items_presupuesto "
        "WHERE valor_ejecutado IS NOT NULL AND valor_ejecutado > 0"
    )).fetchall()

    for fila in ejecutados:
        conn.execute(
            sa.text(
                "INSERT INTO mp_pagos (item_id, valor, fecha, concepto) "
                "VALUES (:item_id, :valor, :fecha, :concepto)"
            ),
            {
                "item_id": fila.id,
                "valor": fila.valor_ejecutado,
                "fecha": fila.creado_en,
                "concepto": "Saldo trasladado del campo 'ejecutado' anterior",
            },
        )
        conn.execute(
            sa.text("UPDATE mp_items_presupuesto SET valor_aprobado = :v WHERE id = :id"),
            {"v": fila.valor_ejecutado, "id": fila.id},
        )

    op.drop_column('mp_items_presupuesto', 'valor_ejecutado')


def downgrade() -> None:
    op.add_column(
        'mp_items_presupuesto',
        sa.Column('valor_ejecutado', sa.Numeric(14, 2), nullable=False, server_default='0'),
    )
    # Se devuelve la suma de los abonos al campo unico. El detalle por abono
    # se pierde: no cabe en una sola columna.
    conn = op.get_bind()
    conn.execute(sa.text(
        "UPDATE mp_items_presupuesto SET valor_ejecutado = COALESCE("
        "  (SELECT SUM(valor) FROM mp_pagos WHERE mp_pagos.item_id = mp_items_presupuesto.id), 0)"
    ))

    op.drop_index(op.f('ix_mp_pagos_item_id'), table_name='mp_pagos')
    op.drop_index(op.f('ix_mp_pagos_id'), table_name='mp_pagos')
    op.drop_table('mp_pagos')

    op.drop_constraint('fk_mp_items_aprobado_por', 'mp_items_presupuesto', type_='foreignkey')
    op.drop_column('mp_items_presupuesto', 'nota_aprobacion')
    op.drop_column('mp_items_presupuesto', 'aprobado_en')
    op.drop_column('mp_items_presupuesto', 'aprobado_por')
    op.drop_column('mp_items_presupuesto', 'valor_aprobado')
