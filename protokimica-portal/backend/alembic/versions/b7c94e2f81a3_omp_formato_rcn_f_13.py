"""Mejora (OMP): acople al formato RCN-F-13

Revision ID: b7c94e2f81a3
Revises: f3a70c81de95
Create Date: 2026-08-31

El módulo de Mejora se hizo antes de mirar el Excel oficial del SGC
(`RCN-F-13 REPORTE PLAN DE ACCIÓN - OMP`). Esta migración le agrega las
columnas del formato que faltaban y normaliza las tres que el Excel tenía
apretadas dentro de una celda: el plan de acción, los seguimientos y los
responsables.

Dos columnas DESAPARECEN porque se volvieron derivadas, y eso es a propósito:

- `omp_oportunidades.responsable_id` se convierte en filas de
  `omp_responsables`. El formato admite varios responsables de resolver y
  varios de seguimiento, y a veces el que responde es un comité.
- `omp_acciones.completada` pasa a ser `estado` de tres valores. Mantener el
  booleano al lado habría sido un segundo campo diciendo lo mismo, que es
  exactamente cómo `valor_pagado` casi se desincroniza de sus pagos.

Los valores de la hoja `Listado` se siembran aquí y quedan CONGELADOS en la
migración a propósito: son los que Calidad tenía el día del corte. De aquí en
adelante se administran desde el portal, así que copiarlos de
`app/modules/mejora/catalogos.py` en cada arranque volvería a pisarle los
cambios.
"""
from alembic import op
import sqlalchemy as sa

revision = "b7c94e2f81a3"
down_revision = "f3a70c81de95"
branch_labels = None
depends_on = None


# La hoja `Listado` del Excel, tal como estaba al migrar.
SEMILLA = {
    "proceso": [
        (None, "Direccionamiento Estratégico"),
        (None, "Abastecimiento y Negocios Internacionales"),
        (None, "Puntos de Ventas"),
        (None, "Ventas Institucionales"),
        (None, "Producción"),
        (None, "Logística"),
        (None, "Infraestructura"),
        (None, "Aseguramiento de producto"),
        (None, "Mercadeo"),
        (None, "Gestión Administrativa"),
        (None, "TIC's"),
        (None, "Gestión Contable"),
        (None, "Gestión Humana"),
        (None, "Control Interno"),
        (None, "SST"),
        (None, "SGAmbiental"),
        (None, "SGC"),
    ],
    "fuente": [
        (None, "Seguimiento al proceso"),
        (None, "Auditoría interna"),
        (None, "Auditoría externa"),
        (None, "Informes Gerenciales"),
        (None, "Revisión por la dirección"),
        (None, "Salida no conforme"),
        (None, "PQR"),
        (None, "Reunión / Comité"),
        (None, "Análisis de contexto"),
    ],
    "tratamiento": [
        ("OMP", "Oportunidad de Mejora"),
        ("AC", "Acción Correctiva"),
        ("AM", "Acción de Mejora"),
    ],
}

# Con qué proceso del SGC se rotulan las OMP que ya existían, según el área
# que tienen. Las áreas que no aparecen no tienen equivalente en el listado
# (Servicio al Cliente, Facturación, Controlados, Tesorería, Comercial):
# esas quedan sin proceso y alguien lo elige. Adivinar mal es peor que no
# adivinar — el proceso decide en qué reporte cae la acción.
PROCESO_SEGUN_AREA = {
    "TICS": "TIC's",
    "Calidad": "SGC",
    "SST": "SST",
    "Ventas Institucionales": "Ventas Institucionales",
    "Mercadeo": "Mercadeo",
    "Infraestructura": "Infraestructura",
    "Logística": "Logística",
    "Gestión Humana": "Gestión Humana",
    "Contabilidad": "Gestión Contable",
    "Producción": "Producción",
    "Control Interno": "Control Interno",
    "Aseguramiento": "Aseguramiento de producto",
    "Abastecimiento": "Abastecimiento y Negocios Internacionales",
    "Administración": "Gestión Administrativa",
}

FUENTE_SEGUN_ORIGEN = {
    "indicador": "Seguimiento al proceso",
    "pqrs": "PQR",
    "auditoria": "Auditoría interna",
    "sugerencia": "Reunión / Comité",
}


def upgrade() -> None:
    # ── Catálogos del formato ────────────────────────────────────────
    op.create_table(
        "omp_catalogos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("tipo", sa.String(length=20), nullable=False),
        sa.Column("codigo", sa.String(length=20), nullable=True),
        sa.Column("nombre", sa.String(length=120), nullable=False),
        sa.Column("orden", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default="true"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "tipo", "nombre", name="uq_omp_catalogo"),
    )
    op.create_index("ix_omp_catalogos_tenant_id", "omp_catalogos", ["tenant_id"])
    op.create_index("ix_omp_catalogos_tipo", "omp_catalogos", ["tipo"])

    conexion = op.get_bind()
    tenants = [fila[0] for fila in conexion.execute(sa.text("SELECT id FROM tenants"))]
    for tenant_id in tenants:
        for tipo, valores in SEMILLA.items():
            for orden, (codigo, nombre) in enumerate(valores):
                conexion.execute(
                    sa.text(
                        "INSERT INTO omp_catalogos "
                        "(tenant_id, tipo, codigo, nombre, orden, activo) "
                        "VALUES (:t, :tipo, :codigo, :nombre, :orden, true)"
                    ),
                    {"t": tenant_id, "tipo": tipo, "codigo": codigo,
                     "nombre": nombre, "orden": orden},
                )

    # ── Columnas nuevas de la ficha ──────────────────────────────────
    with op.batch_alter_table("omp_oportunidades") as lote:
        lote.add_column(sa.Column("consecutivo", sa.Integer(), nullable=True))
        lote.add_column(sa.Column("fecha_registro", sa.Date(), nullable=True))
        lote.add_column(sa.Column("proceso_id", sa.Integer(), nullable=True))
        lote.add_column(sa.Column("fuente_id", sa.Integer(), nullable=True))
        lote.add_column(sa.Column("tratamiento_id", sa.Integer(), nullable=True))
        lote.add_column(sa.Column("clasificacion", sa.String(length=20), nullable=True))
        lote.add_column(sa.Column(
            "hallazgos_similares", sa.Boolean(), nullable=False, server_default="false",
        ))
        lote.add_column(sa.Column("causa_efecto", sa.Text(), nullable=True))
        lote.add_column(sa.Column("causa_metodo", sa.Text(), nullable=True))
        lote.add_column(sa.Column("causa_mano_obra", sa.Text(), nullable=True))
        lote.add_column(sa.Column("causa_maquinaria", sa.Text(), nullable=True))
        lote.add_column(sa.Column("causa_material", sa.Text(), nullable=True))
        lote.add_column(sa.Column("causa_medidas", sa.Text(), nullable=True))
        lote.add_column(sa.Column("causa_medio_ambiente", sa.Text(), nullable=True))
        lote.add_column(sa.Column("correccion", sa.Text(), nullable=True))
        lote.add_column(sa.Column("beneficio_mejora", sa.Text(), nullable=True))
        lote.add_column(sa.Column("verificacion_planeada", sa.Text(), nullable=True))
        lote.add_column(sa.Column("nota_cierre", sa.Text(), nullable=True))
        lote.add_column(sa.Column("validado_sgc_por", sa.Integer(), nullable=True))
        lote.add_column(sa.Column(
            "validado_sgc_en", sa.DateTime(timezone=True), nullable=True,
        ))
        lote.add_column(sa.Column("nota_sgc", sa.Text(), nullable=True))
        lote.add_column(sa.Column("reportado_por_texto", sa.String(length=150), nullable=True))
        lote.add_column(sa.Column(
            "requiere_revision", sa.Boolean(), nullable=False, server_default="false",
        ))

    op.create_index("ix_omp_oportunidades_proceso_id", "omp_oportunidades", ["proceso_id"])
    op.create_foreign_key(
        "fk_omp_proceso", "omp_oportunidades", "omp_catalogos",
        ["proceso_id"], ["id"], ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_omp_fuente", "omp_oportunidades", "omp_catalogos",
        ["fuente_id"], ["id"], ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_omp_tratamiento", "omp_oportunidades", "omp_catalogos",
        ["tratamiento_id"], ["id"], ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_omp_validado_sgc", "omp_oportunidades", "users",
        ["validado_sgc_por"], ["id"],
    )

    # ── Tablas hijas ─────────────────────────────────────────────────
    op.create_table(
        "omp_responsables",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("omp_id", sa.Integer(), nullable=False),
        sa.Column("tipo", sa.String(length=20), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=True),
        sa.Column("nombre_texto", sa.String(length=150), nullable=True),
        sa.ForeignKeyConstraint(["omp_id"], ["omp_oportunidades.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["usuario_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_omp_responsables_omp_id", "omp_responsables", ["omp_id"])

    op.create_table(
        "omp_seguimientos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("omp_id", sa.Integer(), nullable=False),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("autor_id", sa.Integer(), nullable=True),
        sa.Column("autor_texto", sa.String(length=150), nullable=True),
        sa.Column("contenido", sa.Text(), nullable=False),
        sa.Column("adjunto", sa.String(length=255), nullable=True),
        sa.Column("requiere_revision", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["omp_id"], ["omp_oportunidades.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["autor_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_omp_seguimientos_omp_id", "omp_seguimientos", ["omp_id"])

    op.create_table(
        "omp_relaciones",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("omp_id", sa.Integer(), nullable=False),
        sa.Column("relacionada_id", sa.Integer(), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["omp_id"], ["omp_oportunidades.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["relacionada_id"], ["omp_oportunidades.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("omp_id", "relacionada_id", name="uq_omp_relacion"),
    )
    op.create_index("ix_omp_relaciones_omp_id", "omp_relaciones", ["omp_id"])
    op.create_index("ix_omp_relaciones_relacionada_id", "omp_relaciones", ["relacionada_id"])

    op.create_table(
        "omp_historial",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("omp_id", sa.Integer(), nullable=False),
        sa.Column("campo", sa.String(length=50), nullable=False),
        sa.Column("valor_anterior", sa.Text(), nullable=True),
        sa.Column("valor_nuevo", sa.Text(), nullable=True),
        sa.Column("usuario_id", sa.Integer(), nullable=True),
        sa.Column("fecha", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["omp_id"], ["omp_oportunidades.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["usuario_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_omp_historial_omp_id", "omp_historial", ["omp_id"])

    # ── Plan de acción: booleano → estado de tres valores ────────────
    with op.batch_alter_table("omp_acciones") as lote:
        lote.add_column(sa.Column("orden", sa.Integer(), nullable=False, server_default="0"))
        lote.add_column(sa.Column(
            "estado", sa.String(length=20), nullable=False, server_default="pendiente",
        ))
    op.execute("UPDATE omp_acciones SET estado = 'cumplida' WHERE completada = true")
    op.drop_column("omp_acciones", "completada")

    # El orden que tenían por id: es el que la gente venía viendo.
    op.execute(
        "UPDATE omp_acciones a SET orden = n.fila FROM ("
        "  SELECT id, ROW_NUMBER() OVER (PARTITION BY omp_id ORDER BY id) AS fila"
        "  FROM omp_acciones"
        ") n WHERE a.id = n.id"
    )

    # ── Responsable único → tabla de responsables ────────────────────
    op.execute(
        "INSERT INTO omp_responsables (omp_id, tipo, usuario_id) "
        "SELECT id, 'resolucion', responsable_id FROM omp_oportunidades "
        "WHERE responsable_id IS NOT NULL"
    )
    op.drop_column("omp_oportunidades", "responsable_id")

    # ── Rellenar lo que el formato exige y ya se puede deducir ───────
    # La fecha de registro es la de creación: es lo que era verdad.
    op.execute("UPDATE omp_oportunidades SET fecha_registro = creado_en::date "
               "WHERE fecha_registro IS NULL")

    for area, proceso in PROCESO_SEGUN_AREA.items():
        conexion.execute(
            sa.text(
                "UPDATE omp_oportunidades o SET proceso_id = c.id "
                "FROM omp_catalogos c "
                "WHERE c.tenant_id = o.tenant_id AND c.tipo = 'proceso' "
                "AND c.nombre = :proceso AND o.area = :area AND o.proceso_id IS NULL"
            ),
            {"proceso": proceso, "area": area},
        )

    for origen, fuente in FUENTE_SEGUN_ORIGEN.items():
        conexion.execute(
            sa.text(
                "UPDATE omp_oportunidades o SET fuente_id = c.id "
                "FROM omp_catalogos c "
                "WHERE c.tenant_id = o.tenant_id AND c.tipo = 'fuente' "
                "AND c.nombre = :fuente AND o.origen = :origen AND o.fuente_id IS NULL"
            ),
            {"fuente": fuente, "origen": origen},
        )

    # Todo lo que ya existía se abrió como oportunidad de mejora: el módulo
    # no conocía otro tratamiento. Dejarlo en blanco obligaría a Calidad a
    # clasificar a mano un histórico cuyo tratamiento ya se sabe.
    op.execute(
        "UPDATE omp_oportunidades o SET tratamiento_id = c.id "
        "FROM omp_catalogos c "
        "WHERE c.tenant_id = o.tenant_id AND c.tipo = 'tratamiento' "
        "AND c.codigo = 'OMP' AND o.tratamiento_id IS NULL"
    )

    # El consecutivo por proceso, en el orden en que se abrieron. Las que
    # quedaron sin proceso comparten su propia numeración hasta que alguien
    # se lo asigne.
    op.execute(
        "UPDATE omp_oportunidades o SET consecutivo = n.fila FROM ("
        "  SELECT id, ROW_NUMBER() OVER ("
        "    PARTITION BY tenant_id, proceso_id ORDER BY creado_en, id"
        "  ) AS fila FROM omp_oportunidades"
        ") n WHERE o.id = n.id"
    )


def downgrade() -> None:
    op.add_column("omp_acciones", sa.Column(
        "completada", sa.Boolean(), nullable=False, server_default="false",
    ))
    op.execute("UPDATE omp_acciones SET completada = true WHERE estado = 'cumplida'")
    op.drop_column("omp_acciones", "estado")
    op.drop_column("omp_acciones", "orden")

    op.add_column("omp_oportunidades", sa.Column("responsable_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_omp_responsable", "omp_oportunidades", "users", ["responsable_id"], ["id"],
    )
    # Se recupera el primero de resolución: es lo único que cabía antes.
    op.execute(
        "UPDATE omp_oportunidades o SET responsable_id = r.usuario_id FROM ("
        "  SELECT DISTINCT ON (omp_id) omp_id, usuario_id FROM omp_responsables"
        "  WHERE tipo = 'resolucion' ORDER BY omp_id, id"
        ") r WHERE o.id = r.omp_id"
    )

    op.drop_table("omp_historial")
    op.drop_table("omp_relaciones")
    op.drop_table("omp_seguimientos")
    op.drop_table("omp_responsables")

    op.drop_constraint("fk_omp_validado_sgc", "omp_oportunidades", type_="foreignkey")
    op.drop_constraint("fk_omp_tratamiento", "omp_oportunidades", type_="foreignkey")
    op.drop_constraint("fk_omp_fuente", "omp_oportunidades", type_="foreignkey")
    op.drop_constraint("fk_omp_proceso", "omp_oportunidades", type_="foreignkey")
    op.drop_index("ix_omp_oportunidades_proceso_id", table_name="omp_oportunidades")

    for columna in (
        "requiere_revision", "reportado_por_texto", "nota_sgc", "validado_sgc_en",
        "validado_sgc_por", "nota_cierre", "verificacion_planeada", "beneficio_mejora",
        "correccion", "causa_medio_ambiente", "causa_medidas", "causa_material",
        "causa_maquinaria", "causa_mano_obra", "causa_metodo", "causa_efecto",
        "hallazgos_similares", "clasificacion", "tratamiento_id", "fuente_id",
        "proceso_id", "fecha_registro", "consecutivo",
    ):
        op.drop_column("omp_oportunidades", columna)

    op.drop_table("omp_catalogos")
