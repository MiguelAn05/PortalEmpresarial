"""Sembrar capacidades de notas crédito para los tenants existentes

Revision ID: d81f6a4c92e3
Revises: c9e04a1b76d2
Create Date: 2026-09-06

`notas_credito/permisos.py` deja de comparar `usuario.area == "Contabilidad"`
y pasa a preguntar `tiene(db, usuario, "notas_credito.autorizar")` contra la
tabla `capacidades_otorgadas`. Esa tabla existe desde `b3d81e9f2c47`, pero
solo se llena cuando un admin abre Administración › Capacidades — y hasta que
eso pase, `tiene()` respondería que NADIE puede autorizar notas crédito,
Contabilidad incluida. Sería romper en producción el mismo permiso que esta
migración dice estar preservando.

Es el mismo caso que ya cubre el CLAUDE.md sobre migraciones de área: cuando
el cambio renombra o reubica un valor que ya rige, la migración tiene que
actualizar las filas, no solo el esquema.

Se otorgan las dos capacidades —autorizar y registrar— al área Contabilidad
para cada tenant que ya exista, usando como `otorgada_por` un administrador
de ese mismo tenant (si no hay ninguno, se salta: sin admin ese tenant no
tiene quien administre nada, y esto no es el problema que hay que resolver
primero). Es idempotente: si la fila ya existe —alguien abrió la pantalla
antes de correr esto—, no se duplica.
"""
from alembic import op
import sqlalchemy as sa

revision = "d81f6a4c92e3"
down_revision = "c9e04a1b76d2"
branch_labels = None
depends_on = None

AREA_CONTABILIDAD = "Contabilidad"
CAPACIDADES = ("notas_credito.autorizar", "notas_credito.registrar")


def upgrade() -> None:
    conn = op.get_bind()

    tenants = conn.execute(sa.text("SELECT id FROM tenants")).fetchall()
    for (tenant_id,) in tenants:
        admin = conn.execute(
            sa.text(
                "SELECT id FROM users WHERE tenant_id = :tid AND rol = 'admin' "
                "ORDER BY id LIMIT 1"
            ),
            {"tid": tenant_id},
        ).first()
        if not admin:
            continue
        admin_id = admin[0]

        for capacidad in CAPACIDADES:
            ya_existe = conn.execute(
                sa.text(
                    "SELECT 1 FROM capacidades_otorgadas "
                    "WHERE tenant_id = :tid AND capacidad = :cap AND area = :area"
                ),
                {"tid": tenant_id, "cap": capacidad, "area": AREA_CONTABILIDAD},
            ).first()
            if ya_existe:
                continue
            conn.execute(
                sa.text(
                    "INSERT INTO capacidades_otorgadas "
                    "(tenant_id, capacidad, area, otorgada_por, otorgada_en) "
                    "VALUES (:tid, :cap, :area, :por, now())"
                ),
                {"tid": tenant_id, "cap": capacidad, "area": AREA_CONTABILIDAD, "por": admin_id},
            )


def downgrade() -> None:
    conn = op.get_bind()
    for capacidad in CAPACIDADES:
        conn.execute(
            sa.text(
                "DELETE FROM capacidades_otorgadas "
                "WHERE capacidad = :cap AND area = :area"
            ),
            {"cap": capacidad, "area": AREA_CONTABILIDAD},
        )
