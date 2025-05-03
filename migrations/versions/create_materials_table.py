
"""create core tables

Revision ID: create_core_tables
Revises: 
Create Date: 2025-05-03 12:50:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'create_core_tables'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Create audio_recordings table
    op.create_table('audio_recordings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('filename', sa.String(), nullable=False),
        sa.Column('transcript', sa.Text(), nullable=False),
        sa.Column('file_hash', sa.String(), nullable=False, unique=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Create materials table
    op.create_table('materials',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('material_name', sa.String(), nullable=False),
        sa.Column('storage_key', sa.String(), nullable=False),
        sa.Column('transcript', sa.Text(), nullable=True),
        sa.Column('upload_timestamp', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Create practice_logs table
    op.create_table('practice_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('practice_type', sa.String(), nullable=False),
        sa.Column('recording_id', sa.Integer(), nullable=True),
        sa.Column('material_id', sa.Integer(), nullable=True),
        sa.Column('wer', sa.Float(), nullable=False),
        sa.Column('practiced_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('original_text', sa.Text(), nullable=True),
        sa.Column('user_text', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['material_id'], ['materials.id']),
        sa.ForeignKeyConstraint(['recording_id'], ['audio_recordings.id']),
        sa.PrimaryKeyConstraint('id')
    )

def downgrade():
    op.drop_table('practice_logs')
    op.drop_table('materials')
    op.drop_table('audio_recordings')
