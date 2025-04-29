"""Add phone verification fields

Revision ID: 5f276b20b829
Revises: 60a87dae919f
Create Date: 2025-04-28 15:18:13.199355

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5f276b20b829'
down_revision: Union[str, None] = '60a87dae919f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # For SQLite compatibility, use batch mode for ALTER TABLE operations
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('phone_number', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('is_phone_verified', sa.Boolean(), nullable=True, server_default='0'))
        batch_op.add_column(sa.Column('phone_verification_code', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('phone_verification_expiry', sa.DateTime(), nullable=True))

    # Update the subscription type enum values if needed
    # This might not be needed depending on your database setup
    # op.execute("ALTER TYPE subscriptiontype RENAME VALUE 'premium' TO 'creator'")
    # op.execute("ALTER TYPE subscriptiontype RENAME VALUE 'professional' TO 'pro_lab'")


def downgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('phone_verification_expiry')
        batch_op.drop_column('phone_verification_code')
        batch_op.drop_column('is_phone_verified')
        batch_op.drop_column('phone_number')