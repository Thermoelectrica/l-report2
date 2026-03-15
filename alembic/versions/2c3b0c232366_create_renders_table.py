"""Create renders table

Revision ID: 2c3b0c232366
Revises: 
Create Date: 2026-03-15 21:03:20.127184

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2c3b0c232366'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create renders table
    op.create_table(
        'renders',
        sa.Column('parameter_hash', sa.String(length=64), nullable=False, comment='SHA256 hash of report_id + parameters'),
        sa.Column('report_id', sa.String(length=255), nullable=False, comment='Report identifier'),
        sa.Column('parameters_json', sa.Text(), nullable=False, comment='JSON-encoded parameters'),
        sa.Column('status', sa.String(length=50), nullable=False, comment='PENDING, RUNNING, COMPLETED, FAILED'),
        sa.Column('pdf_path', sa.String(length=512), nullable=True, comment='Storage path to PDF file'),
        sa.Column('file_size_bytes', sa.Integer(), nullable=True, comment='PDF file size in bytes'),
        sa.Column('error_message', sa.Text(), nullable=True, comment='Error details if status is FAILED'),
        sa.Column('created_at', sa.DateTime(), nullable=False, comment='When render was requested'),
        sa.Column('started_at', sa.DateTime(), nullable=True, comment='When rendering started'),
        sa.Column('completed_at', sa.DateTime(), nullable=True, comment='When rendering finished'),
        sa.PrimaryKeyConstraint('parameter_hash')
    )
    
    # Create indexes
    op.create_index('ix_renders_report_id', 'renders', ['report_id'], unique=False)
    op.create_index('ix_renders_status', 'renders', ['status'], unique=False)
    op.create_index('ix_renders_completed_at', 'renders', ['completed_at'], unique=False)
    op.create_index('ix_renders_report_status', 'renders', ['report_id', 'status'], unique=False)
    op.create_index('ix_renders_completed_at_status', 'renders', ['completed_at', 'status'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    # Drop indexes
    op.drop_index('ix_renders_completed_at_status', table_name='renders')
    op.drop_index('ix_renders_report_status', table_name='renders')
    op.drop_index('ix_renders_completed_at', table_name='renders')
    op.drop_index('ix_renders_status', table_name='renders')
    op.drop_index('ix_renders_report_id', table_name='renders')
    
    # Drop table
    op.drop_table('renders')
