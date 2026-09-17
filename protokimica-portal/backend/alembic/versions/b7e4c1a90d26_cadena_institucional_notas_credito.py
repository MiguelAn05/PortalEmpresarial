"""Cadena institucional de las notas crédito: bodega, comercial y DIAN

Una nota crédito de Ventas Institucionales ya no la autoriza Contabilidad de
una: pasa por Coordinación Comercial y después por la verificación ante la
DIAN, y si el motivo implica producto devuelto, antes que nadie la bodega
confirma que llegó. Esto agrega lo que esa cadena necesita:

- `nc_motivos.requiere_bodega` — qué motivos mueven producto. Se marcan de una
  vez los tres de la semilla que obviamente lo hacen; sin eso la función
  quedaría instalada y apagada, y parecería que no sirve.
- `nc_solicitudes.bodega` y `users.bodega` — a qué bodega entró y quién
  responde por ella.
- `nc_historial` — la cadena de manos. Con una sola firma bastaban tres
  columnas; con cuatro etapas y la posibilidad de devolver para corregir, una
  solicitud puede pasar dos veces por la misma etapa y eso no cabe en
  columnas.
- Las tres capacidades nuevas, otorgadas a las áreas que hoy hacen ese
  trabajo. **Se siembran aquí y no solo en `sembrar_capacidades_iniciales`**
  porque esa siembra corre cuando alguien abre Administración › Capacidades:
  si nadie la abre, la primera solicitud institucional se quedaría esperando
  a que la atienda alguien que todavía no tiene el permiso.

Los estados nuevos no necesitan migración: `estado` ya es un `String` y los
cuatro de siempre significan exactamente lo que significaban, así que las
solicitudes que ya existen no se mueven de sitio.

Revision ID: b7e4c1a90d26
Revises: a3f9b7c2d514
"""
import sqlalchemy as sa
from alembic import op

revision = "b7e4c1a90d26"
down_revision = "a3f9b7c2d514"
branch_labels = None
depends_on = None

# Los motivos de la semilla que sí traen producto de vuelta. Se comparan por
# nombre porque es lo único estable entre empresas; los que Contabilidad haya
# agregado a mano se quedan sin marcar, que es el valor seguro: marcar de más
# metería una confirmación de bodega donde no hay nada que confirmar.
MOTIVOS_CON_PRODUCTO = (
    "Devolución de mercancía",
    "Cambio de producto",
    "Producto en mal estado",
)

CAPACIDADES_NUEVAS = (
    ("notas_credito.confirmar_producto", "Logística"),
    ("notas_credito.confirmar_producto", "Producción"),
    ("notas_credito.aprobar_comercial", "Comercial"),
    ("notas_credito.verificar_dian", "Contabilidad"),
)


def upgrade():
    op.add_column("nc_motivos", sa.Column(
        "requiere_bodega", sa.Boolean(), nullable=False, server_default=sa.false(),
    ))
    op.add_column("nc_solicitudes", sa.Column("bodega", sa.String(length=40), nullable=True))
    op.add_column("users", sa.Column("bodega", sa.String(length=40), nullable=True))

    op.create_table(
        "nc_historial",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column(
            "solicitud_id", sa.Integer(),
            sa.ForeignKey("nc_solicitudes.id", ondelete="CASCADE"),
            nullable=False, index=True,
        ),
        sa.Column("etapa", sa.String(length=20), nullable=False),
        sa.Column("accion", sa.String(length=20), nullable=False),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("usuario_nombre", sa.String(length=150), nullable=True),
        sa.Column("comentario", sa.Text(), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    conexion = op.get_bind()
    for nombre in MOTIVOS_CON_PRODUCTO:
        conexion.execute(
            sa.text("UPDATE nc_motivos SET requiere_bodega = true WHERE nombre = :nombre"),
            {"nombre": nombre},
        )

    # Un otorgamiento necesita quién lo otorgó. Se usa el admin más antiguo de
    # cada empresa: es quien habría entrado a darlo a mano.
    tenants = conexion.execute(sa.text("SELECT id FROM tenants")).fetchall()
    for (tenant_id,) in tenants:
        admin = conexion.execute(sa.text(
            "SELECT id FROM users WHERE tenant_id = :t AND rol = 'admin' "
            "ORDER BY id LIMIT 1"
        ), {"t": tenant_id}).fetchone()
        if not admin:
            continue
        for capacidad, area in CAPACIDADES_NUEVAS:
            ya = conexion.execute(sa.text(
                "SELECT 1 FROM capacidades_otorgadas WHERE tenant_id = :t "
                "AND capacidad = :c AND area = :a"
            ), {"t": tenant_id, "c": capacidad, "a": area}).fetchone()
            if ya:
                continue
            conexion.execute(sa.text(
                "INSERT INTO capacidades_otorgadas "
                "(tenant_id, capacidad, area, otorgada_por) "
                "VALUES (:t, :c, :a, :por)"
            ), {"t": tenant_id, "c": capacidad, "a": area, "por": admin[0]})


def downgrade():
    conexion = op.get_bind()
    for capacidad, area in CAPACIDADES_NUEVAS:
        conexion.execute(sa.text(
            "DELETE FROM capacidades_otorgadas WHERE capacidad = :c AND area = :a"
        ), {"c": capacidad, "a": area})

    op.drop_table("nc_historial")
    op.drop_column("users", "bodega")
    op.drop_column("nc_solicitudes", "bodega")
    op.drop_column("nc_motivos", "requiere_bodega")
