"""0002_add_github_imports

Revision ID: 0002_add_github_imports
Revises: 0001_initial_schema
Create Date: 2026-10-10 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0002_add_github_imports'
down_revision = '0001_initial_schema'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'github_imports',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('repo_url', sa.String(length=500), nullable=False),
        sa.Column('owner', sa.String(length=255), nullable=False),
        sa.Column('repo_name', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=511), nullable=False),
        sa.Column('default_branch', sa.String(length=255), nullable=True),
        sa.Column('commit_sha', sa.String(length=40), nullable=True),
        sa.Column('import_status', sa.String(length=50), nullable=False, server_default='pending'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('error_code', sa.String(length=50), nullable=True),
        sa.Column('extracted_files', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('indexed_chunks', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('html_url', sa.String(length=500), nullable=True),
        sa.Column('stars', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_private', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.Column('language', sa.String(length=100), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id', name='uq_github_imports_project_id')
    )
    op.create_index(op.f('ix_github_imports_project_id'), 'github_imports', ['project_id'], unique=True)
    op.create_index(op.f('ix_github_imports_import_status'), 'github_imports', ['import_status'], unique=False)


def downgrade():
    op.drop_table('github_imports')
