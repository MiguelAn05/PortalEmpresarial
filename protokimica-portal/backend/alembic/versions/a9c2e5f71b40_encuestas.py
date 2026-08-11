"""modulo de encuestas: plantillas, preguntas y respuestas

Las preguntas se guardan como datos para que crear una encuesta nueva no
necesite ni migración ni despliegue.

No toca `pqrs_encuestas`: esa sigue igual, y el módulo la lee con un
adaptador. Migrarla sería reescribir algo que funciona en producción.

Revision ID: a9c2e5f71b40
Revises: d4f81c60a7e3
Create Date: 2026-08-10 15:40:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a9c2e5f71b40'
down_revision = 'd4f81c60a7e3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'enc_plantillas',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('nombre', sa.String(length=200), nullable=False),
        sa.Column('descripcion', sa.Text(), nullable=True),
        sa.Column('slug', sa.String(length=60), nullable=False),
        sa.Column('sujeto_tipo', sa.String(length=40), nullable=True),
        sa.Column('mensaje_final', sa.Text(), nullable=True),
        sa.Column('activa', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('creado_en', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'slug', name='uq_plantilla_slug'),
    )
    op.create_index('ix_enc_plantillas_tenant_id', 'enc_plantillas', ['tenant_id'])
    op.create_index('ix_enc_plantillas_slug', 'enc_plantillas', ['slug'])

    op.create_table(
        'enc_preguntas',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('plantilla_id', sa.Integer(), nullable=False),
        sa.Column('texto', sa.Text(), nullable=False),
        sa.Column('ayuda', sa.Text(), nullable=True),
        sa.Column('tipo', sa.String(length=20), nullable=False, server_default='escala'),
        sa.Column('opciones', sa.Text(), nullable=True),
        sa.Column('clave', sa.String(length=60), nullable=True),
        sa.Column('obligatoria', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('orden', sa.Integer(), nullable=False, server_default='0'),
        # Cascada: borrar la plantilla se lleva sus preguntas. Sin esto el
        # borrado falla contra la llave foránea.
        sa.ForeignKeyConstraint(['plantilla_id'], ['enc_plantillas.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_enc_preguntas_plantilla_id', 'enc_preguntas', ['plantilla_id'])

    op.create_table(
        'enc_respuestas',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('plantilla_id', sa.Integer(), nullable=False),
        sa.Column('sujeto_ref', sa.String(length=60), nullable=True),
        sa.Column('sujeto_nombre', sa.String(length=200), nullable=True),
        sa.Column('respondida_en', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['plantilla_id'], ['enc_plantillas.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_enc_respuestas_tenant_id', 'enc_respuestas', ['tenant_id'])
    op.create_index('ix_enc_respuestas_plantilla_id', 'enc_respuestas', ['plantilla_id'])
    op.create_index('ix_enc_respuestas_sujeto_ref', 'enc_respuestas', ['sujeto_ref'])
    op.create_index('ix_enc_respuestas_respondida_en', 'enc_respuestas', ['respondida_en'])

    op.create_table(
        'enc_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('respuesta_id', sa.Integer(), nullable=False),
        sa.Column('pregunta_id', sa.Integer(), nullable=False),
        sa.Column('valor_numero', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('valor_texto', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['respuesta_id'], ['enc_respuestas.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['pregunta_id'], ['enc_preguntas.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_enc_items_respuesta_id', 'enc_items', ['respuesta_id'])
    op.create_index('ix_enc_items_pregunta_id', 'enc_items', ['pregunta_id'])


def downgrade() -> None:
    op.drop_table('enc_items')
    op.drop_table('enc_respuestas')
    op.drop_table('enc_preguntas')
    op.drop_table('enc_plantillas')
