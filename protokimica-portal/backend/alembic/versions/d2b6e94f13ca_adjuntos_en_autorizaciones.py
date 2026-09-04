"""Autorizaciones: adjunto en la solicitud y en la respuesta

Revision ID: d2b6e94f13ca
Revises: c1d05b83e7f2
Create Date: 2026-09-04

Una autorización se pedía y se firmaba con puro texto. El soporte —la
factura, la foto del producto, el concepto de la analista— viajaba por correo
aparte, así que quien tiene que decidir buscaba en dos sitios, y la
autorización quedaba aprobada sin nada que la sustentara para cuando alguien
la audite.

Ahora el archivo va con la pregunta y con la respuesta. Son rutas, igual que
el resto de adjuntos del portal (`pqrs_seguimientos.adjunto_evidencia`), y
comparten su límite: `/uploads` todavía no tiene control de acceso real, así
que aquí no se sube nada que no pueda quedar en una URL adivinable.

Las autorizaciones que ya existen quedan en NULL, que es lo correcto: se
pidieron sin adjunto y así fue.
"""
from alembic import op
import sqlalchemy as sa

revision = "d2b6e94f13ca"
down_revision = "c1d05b83e7f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "autorizaciones_pqrs",
        sa.Column("adjunto_solicitud", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "autorizaciones_pqrs",
        sa.Column("adjunto_respuesta", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("autorizaciones_pqrs", "adjunto_respuesta")
    op.drop_column("autorizaciones_pqrs", "adjunto_solicitud")
