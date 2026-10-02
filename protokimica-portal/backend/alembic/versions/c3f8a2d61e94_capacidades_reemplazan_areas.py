"""Cerrar PQRS, validar el SGC, aprobar y pagar pasan a ser capacidades

Revision ID: c3f8a2d61e94
Revises: a6c2e9f41d07
Create Date: 2026-10-01

Hasta hoy, quién cierra una PQRS, quién da el visto bueno del SGC y quién
aprueba y paga un presupuesto lo decidían cuatro constantes con nombres de
área de Protokimica (`AREA_SERVICIO_CLIENTE`, `AREA_SGC`,
`AREA_APRUEBA_PAGOS`, `AREA_REGISTRA_PAGOS`). Ahora lo decide la tabla de
capacidades, que se administra desde el portal.

**Esta migración es la que evita que, al desplegar, nadie pueda cerrar una
PQRS.** Las cuatro capacidades se sembraban solo al abrir Administración ›
Capacidades: en una empresa donde nadie la abrió, la tabla estaría vacía y
el código nuevo diría que no a todos. Aquí se siembran con las mismas áreas
que tenían las constantes, así que nadie gana ni pierde un permiso.

Si ya hay una fila para esa capacidad y esa área —vigente o REVOCADA— no se
toca: una revocada es una decisión de un administrador, no un hueco.
"""
from alembic import op
import sqlalchemy as sa

revision = "c3f8a2d61e94"
down_revision = "a6c2e9f41d07"
branch_labels = None
depends_on = None

# Escritas aquí y no importadas de `SEMILLA_INICIAL`: una migración describe
# el estado de un momento.
CAPACIDADES = (
    ("pqrs.cerrar", "Servicio al Cliente"),
    ("mejora.validar_sgc", "Calidad"),
    ("presupuesto.aprobar", "Administración"),
    ("presupuesto.pagar", "Tesorería"),
)


def upgrade() -> None:
    conexion = op.get_bind()
    tenants = conexion.execute(sa.text("SELECT id FROM tenants")).fetchall()
    for (tenant_id,) in tenants:
        # Un otorgamiento necesita quién lo otorgó: el admin más antiguo, que
        # es quien habría entrado a darlo a mano.
        admin = conexion.execute(sa.text(
            "SELECT id FROM users WHERE tenant_id = :t AND rol = 'admin' ORDER BY id LIMIT 1"
        ), {"t": tenant_id}).fetchone()
        if not admin:
            continue
        for capacidad, area in CAPACIDADES:
            ya = conexion.execute(sa.text(
                "SELECT 1 FROM capacidades_otorgadas "
                "WHERE tenant_id = :t AND capacidad = :c AND area = :a"
            ), {"t": tenant_id, "c": capacidad, "a": area}).fetchone()
            if ya:
                continue
            conexion.execute(sa.text(
                "INSERT INTO capacidades_otorgadas (tenant_id, capacidad, area, otorgada_por) "
                "VALUES (:t, :c, :a, :por)"
            ), {"t": tenant_id, "c": capacidad, "a": area, "por": admin[0]})


def downgrade() -> None:
    # No se borra nada: no hay forma de distinguir las filas que puso esta
    # migración de las que un administrador ya había otorgado antes, y borrar
    # las segundas le quitaría el permiso a quien lo tenía.
    pass
