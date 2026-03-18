"""add_output_format_fields

Revision ID: 929351a9dd65
Revises: 2c3b0c232366
Create Date: 2026-03-18 18:33:14.030654

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '929351a9dd65'
down_revision: Union[str, Sequence[str], None] = '2c3b0c232366'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add new columns
    op.add_column('renders',
        sa.Column('output_format', sa.String(50), nullable=True,
                  comment='Output format (weasyprint, docx, etc.)'))
    op.add_column('renders',
        sa.Column('file_extension', sa.String(10), nullable=True,
                  comment='File extension (pdf, docx, etc.)'))
    
    # Set default values for existing records
    op.execute("UPDATE renders SET output_format = 'weasyprint', file_extension = 'pdf'")
    
    # Make columns non-nullable after setting defaults
    op.alter_column('renders', 'output_format', nullable=False)
    op.alter_column('renders', 'file_extension', nullable=False)
    
    # Rename pdf_path to output_path for clarity
    op.alter_column('renders', 'pdf_path', new_column_name='output_path')


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column('renders', 'output_path', new_column_name='pdf_path')
    op.drop_column('renders', 'file_extension')
    op.drop_column('renders', 'output_format')
