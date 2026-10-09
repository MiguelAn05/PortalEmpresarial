"""Bodegas: una sola lista para todo el portal, con sus responsables

Revision ID: d5a2e7c1b839
Revises: c3f8d1a6e924
Create Date: 2026-10-09

Había dos listas que no se conocían: la de Notas crédito, fija en el código
(Guayabal, La 65) con el responsable marcado en cada usuario
(`users.bodega`), y la de despacho de PQRS (`pqrs_bodegas_despacho`). Ver
`models/bodega.py`.

1. `bodegas` + `bodega_responsables`, por empresa. Se crean con CD, La 65 y
   Guayabal, más cualquier nombre que ya esté en uso en PQRS, en un usuario o
   en una nota crédito — nada queda apuntando a una bodega que no existe.
2. Quien tenía `users.bodega` queda como RESPONSABLE de esa bodega. Lo que
   cambia: quien NO la tenía y confirmaba producto respondía por todas; ahora
   eso solo pasa en las bodegas que no tienen responsables. Un coordinador de
   varias se nombra responsable de cada una en Administración › Bodegas.
3. El concepto de cada bodega de despacho pasa a `pqrs_conceptos_bodega`, y
   `pqrs_solicitudes.bodega_despacho_id` apunta a la lista común.
4. «Otro» de Notas crédito pasa a traer producto: el usuario pidió que se
   pregunte la bodega en todo lo que tenga que ver con producto, incluido
   «Otro».
5. Se quitan `pqrs_bodegas_despacho` y `users.bodega`.
"""
from alembic import op
import sqlalchemy as sa

revision = "d5a2e7c1b839"
down_revision = "c3f8d1a6e924"
branch_labels = None
depends_on = None

INICIALES = ["CD", "La 65", "Guayabal"]


def upgrade() -> None:
    bind = op.get_bind()

    op.create_table(
        "bodegas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("nombre", sa.String(40), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("orden", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("creada_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "nombre", name="uq_bodega_tenant_nombre"),
    )
    op.create_index("ix_bodegas_id", "bodegas", ["id"])
    op.create_index("ix_bodegas_tenant_id", "bodegas", ["tenant_id"])
    op.create_table(
        "bodega_responsables",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("bodega_id", sa.Integer(), sa.ForeignKey("bodegas.id", ondelete="CASCADE"), nullable=False),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.UniqueConstraint("bodega_id", "usuario_id", name="uq_bodega_responsable"),
    )
    op.create_index("ix_bodega_responsables_bodega_id", "bodega_responsables", ["bodega_id"])
    op.create_index("ix_bodega_responsables_usuario_id", "bodega_responsables", ["usuario_id"])

    # 1. La lista común de cada empresa, con todo nombre que ya esté en uso.
    for (tenant_id,) in bind.execute(sa.text("SELECT id FROM tenants")).fetchall():
        nombres, activas = list(INICIALES), {}
        for nombre, activo in bind.execute(sa.text(
            "SELECT nombre, activo FROM pqrs_bodegas_despacho WHERE tenant_id = :t ORDER BY orden, nombre"
        ), {"t": tenant_id}):
            activas[nombre] = activo
            if nombre not in nombres:
                nombres.append(nombre)
        for consulta in (
            "SELECT DISTINCT bodega FROM users WHERE tenant_id = :t AND bodega IS NOT NULL",
            "SELECT DISTINCT bodega FROM nc_solicitudes WHERE tenant_id = :t AND bodega IS NOT NULL",
        ):
            for (nombre,) in bind.execute(sa.text(consulta), {"t": tenant_id}):
                nombre = " ".join((nombre or "").split())
                if nombre and nombre not in nombres:
                    nombres.append(nombre)
        for orden, nombre in enumerate(nombres):
            bind.execute(sa.text(
                "INSERT INTO bodegas (tenant_id, nombre, activo, orden) VALUES (:t, :n, :a, :o)"
            ), {"t": tenant_id, "n": nombre, "a": activas.get(nombre, True), "o": orden})

    # 2. Quien tenía bodega marcada queda como su responsable.
    bind.execute(sa.text("""
        INSERT INTO bodega_responsables (bodega_id, usuario_id)
        SELECT b.id, u.id FROM users u
        JOIN bodegas b ON b.tenant_id = u.tenant_id AND b.nombre = TRIM(u.bodega)
        WHERE u.bodega IS NOT NULL
    """))

    # 3. Los conceptos de PQRS, y las PQRS apuntando a la lista común.
    op.create_table(
        "pqrs_conceptos_bodega",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("bodega_id", sa.Integer(), sa.ForeignKey("bodegas.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tipo_autorizacion_id", sa.Integer(), sa.ForeignKey("tipos_autorizacion.id"), nullable=True),
        sa.UniqueConstraint("bodega_id", name="uq_pqrs_concepto_bodega"),
    )
    op.create_index("ix_pqrs_conceptos_bodega_id", "pqrs_conceptos_bodega", ["id"])
    op.create_index("ix_pqrs_conceptos_bodega_tenant_id", "pqrs_conceptos_bodega", ["tenant_id"])
    bind.execute(sa.text("""
        INSERT INTO pqrs_conceptos_bodega (tenant_id, bodega_id, tipo_autorizacion_id)
        SELECT d.tenant_id, b.id, d.tipo_autorizacion_id FROM pqrs_bodegas_despacho d
        JOIN bodegas b ON b.tenant_id = d.tenant_id AND b.nombre = d.nombre
        WHERE d.tipo_autorizacion_id IS NOT NULL
    """))

    for fk in sa.inspect(bind).get_foreign_keys("pqrs_solicitudes"):
        if fk["referred_table"] == "pqrs_bodegas_despacho":
            op.drop_constraint(fk["name"], "pqrs_solicitudes", type_="foreignkey")
    bind.execute(sa.text("""
        UPDATE pqrs_solicitudes s SET bodega_despacho_id = b.id
        FROM pqrs_bodegas_despacho d
        JOIN bodegas b ON b.tenant_id = d.tenant_id AND b.nombre = d.nombre
        WHERE s.bodega_despacho_id = d.id
    """))
    op.create_foreign_key("fk_pqrs_solicitudes_bodega_despacho", "pqrs_solicitudes", "bodegas",
                          ["bodega_despacho_id"], ["id"])
    op.drop_index("ix_pqrs_bodegas_despacho_tenant_id", table_name="pqrs_bodegas_despacho")
    op.drop_index("ix_pqrs_bodegas_despacho_id", table_name="pqrs_bodegas_despacho")
    op.drop_table("pqrs_bodegas_despacho")

    # 4. «Otro» también trae producto.
    bind.execute(sa.text("UPDATE nc_motivos SET requiere_bodega = TRUE WHERE LOWER(TRIM(nombre)) = 'otro'"))

    # 5. La bodega ya no se marca en el usuario.
    op.drop_column("users", "bodega")


def downgrade() -> None:
    bind = op.get_bind()
    op.add_column("users", sa.Column("bodega", sa.String(40), nullable=True))
    bind.execute(sa.text("""
        UPDATE users u SET bodega = b.nombre FROM bodega_responsables r
        JOIN bodegas b ON b.id = r.bodega_id WHERE r.usuario_id = u.id
    """))
    op.create_table(
        "pqrs_bodegas_despacho",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("nombre", sa.String(150), nullable=False),
        sa.Column("tipo_autorizacion_id", sa.Integer(), sa.ForeignKey("tipos_autorizacion.id"), nullable=True),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("orden", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("tenant_id", "nombre", name="uq_pqrs_bodega_despacho_nombre"),
    )
    op.create_index("ix_pqrs_bodegas_despacho_id", "pqrs_bodegas_despacho", ["id"])
    op.create_index("ix_pqrs_bodegas_despacho_tenant_id", "pqrs_bodegas_despacho", ["tenant_id"])
    bind.execute(sa.text("""
        INSERT INTO pqrs_bodegas_despacho (id, tenant_id, nombre, tipo_autorizacion_id, activo, orden)
        SELECT b.id, b.tenant_id, b.nombre, c.tipo_autorizacion_id, b.activo, b.orden
        FROM bodegas b LEFT JOIN pqrs_conceptos_bodega c ON c.bodega_id = b.id
    """))
    op.drop_constraint("fk_pqrs_solicitudes_bodega_despacho", "pqrs_solicitudes", type_="foreignkey")
    op.create_foreign_key(None, "pqrs_solicitudes", "pqrs_bodegas_despacho", ["bodega_despacho_id"], ["id"])
    op.drop_index("ix_pqrs_conceptos_bodega_tenant_id", table_name="pqrs_conceptos_bodega")
    op.drop_index("ix_pqrs_conceptos_bodega_id", table_name="pqrs_conceptos_bodega")
    op.drop_table("pqrs_conceptos_bodega")
    op.drop_index("ix_bodega_responsables_usuario_id", table_name="bodega_responsables")
    op.drop_index("ix_bodega_responsables_bodega_id", table_name="bodega_responsables")
    op.drop_table("bodega_responsables")
    op.drop_index("ix_bodegas_tenant_id", table_name="bodegas")
    op.drop_index("ix_bodegas_id", table_name="bodegas")
    op.drop_table("bodegas")
