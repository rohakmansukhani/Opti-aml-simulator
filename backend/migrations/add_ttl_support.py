"""
Database migration to add TTL support for data uploads.

Adds:
- data_uploads table for persistent metadata
- upload_id and expires_at columns to transactions and customers
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = 'add_ttl_support'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Create data_uploads table
    op.create_table(
        'data_uploads',
        sa.Column('upload_id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=True),
        sa.Column('upload_timestamp', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('filename', sa.String(), nullable=True),
        sa.Column('record_count_transactions', sa.Integer(), nullable=True),
        sa.Column('record_count_customers', sa.Integer(), nullable=True),
        sa.Column('schema_snapshot', sa.JSON(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(), server_default='active', nullable=True),
        sa.PrimaryKeyConstraint('upload_id')
    )
    
    # Add columns to transactions
    op.add_column('transactions', sa.Column('upload_id', sa.String(), nullable=True))
    op.add_column('transactions', sa.Column('expires_at', sa.DateTime(), nullable=True))
    op.create_foreign_key('fk_transactions_upload', 'transactions', 'data_uploads', ['upload_id'], ['upload_id'])
    
    # Add columns to customers
    op.add_column('customers', sa.Column('upload_id', sa.String(), nullable=True))
    op.add_column('customers', sa.Column('expires_at', sa.DateTime(), nullable=True))
    op.create_foreign_key('fk_customers_upload', 'customers', 'data_uploads', ['upload_id'], ['upload_id'])
    
    # Create index for efficient cleanup queries
    op.create_index('idx_transactions_expires_at', 'transactions', ['expires_at'])
    op.create_index('idx_customers_expires_at', 'customers', ['expires_at'])


def downgrade():
    # Drop indexes
    op.drop_index('idx_customers_expires_at', table_name='customers')
    op.drop_index('idx_transactions_expires_at', table_name='transactions')
    
    # Drop foreign keys
    op.drop_constraint('fk_customers_upload', 'customers', type_='foreignkey')
    op.drop_constraint('fk_transactions_upload', 'transactions', type_='foreignkey')
    
    # Drop columns
    op.drop_column('customers', 'expires_at')
    op.drop_column('customers', 'upload_id')
    op.drop_column('transactions', 'expires_at')
    op.drop_column('transactions', 'upload_id')
    
    # Drop table
    op.drop_table('data_uploads')
