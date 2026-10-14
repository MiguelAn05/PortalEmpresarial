"""catalogo: busqueda sin tildes, grupo, ultima venta y huellas de clientes

- `cat_productos` gana `grupo`, `fecha_ultima_venta` y `texto_busqueda`
  (minúscula y sin tildes), con índice de trigramas en Postgres.
- `cat_clientes_huella`: el HMAC de cada NIT de cliente del ERP. Responde
  «¿es cliente nuestro?» sin copiar ningún dato del cliente.
- `cat_sincronizaciones`: cuándo mandó algo el ERP y qué pasó.

Los productos que ya estaban se quedarían sin `texto_busqueda` hasta la
siguiente sincronización —y el buscador no los encontraría—, así que la
migración también lo rellena.

Revision ID: b7d41e9a2c63
Revises: e2c7a4f9b136
Create Date: 2026-10-14 10:00:00.000000

"""
import unicodedata

from alembic import op
import sqlalchemy as sa


revision = 'b7d41e9a2c63'
down_revision = 'e2c7a4f9b136'
branch_labels = None
depends_on = None


def _texto_de_busqueda(*partes):
    # Copia de `catalogo.service.texto_de_busqueda`: una migración no importa
    # código de la aplicación, que mañana puede cambiar o dejar de existir.
    texto = " ".join(p for p in partes if p)
    sin_tildes = unicodedata.normalize("NFKD", texto)
    sin_tildes = "".join(c for c in sin_tildes if not unicodedata.combining(c))
    return " ".join(sin_tildes.lower().split())[:500]


def upgrade() -> None:
    op.add_column('cat_productos', sa.Column('grupo', sa.String(length=60), nullable=True))
    op.add_column('cat_productos', sa.Column('fecha_ultima_venta', sa.Date(), nullable=True))
    op.add_column('cat_productos', sa.Column('texto_busqueda', sa.String(length=500), nullable=True))

    conexion = op.get_bind()
    filas = conexion.execute(
        sa.text("SELECT id, codigo, nombre, presentacion FROM cat_productos")
    ).fetchall()
    for fila in filas:
        conexion.execute(
            sa.text("UPDATE cat_productos SET texto_busqueda = :t WHERE id = :id"),
            {"t": _texto_de_busqueda(fila.codigo, fila.nombre, fila.presentacion), "id": fila.id},
        )

    if conexion.dialect.name == "postgresql":
        # pg_trgm viene con la imagen oficial de Postgres. Con el índice, un
        # LIKE '%texto%' no recorre la tabla entera.
        op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
        op.execute(
            "CREATE INDEX ix_cat_productos_busqueda ON cat_productos "
            "USING gin (texto_busqueda gin_trgm_ops)"
        )

    op.create_table(
        'cat_clientes_huella',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('huella', sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'huella', name='uq_cliente_huella'),
    )
    op.create_index('ix_cat_clientes_huella_tenant_id', 'cat_clientes_huella', ['tenant_id'])

    op.create_table(
        'cat_sincronizaciones',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('tipo', sa.String(length=20), nullable=False),
        sa.Column('fecha', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('exitosa', sa.Boolean(), nullable=False),
        sa.Column('resumen', sa.JSON(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_cat_sincronizaciones_tenant_id', 'cat_sincronizaciones', ['tenant_id'])


def downgrade() -> None:
    op.drop_table('cat_sincronizaciones')
    op.drop_table('cat_clientes_huella')
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_cat_productos_busqueda")
    op.drop_column('cat_productos', 'texto_busqueda')
    op.drop_column('cat_productos', 'fecha_ultima_venta')
    op.drop_column('cat_productos', 'grupo')
