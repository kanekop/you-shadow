
"""create materials table

Revision ID: create_materials_table
Revises: 
Create Date: 2025-05-03 12:50:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'create_materials_table'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('materials',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('material_name', sa.String(), nullable=False),
        sa.Column('storage_key', sa.String(), nullable=False),
        sa.Column('transcript', sa.Text(), nullable=True),
        sa.Column('upload_timestamp', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

def downgrade():
    op.drop_table('materials')
