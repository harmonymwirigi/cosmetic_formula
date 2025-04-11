"""add_user_profile_fields

Revision ID: 7edf8b7c6af3
Revises: 78c43957d4fb
Create Date: 2025-04-10 23:52:18.516322

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7edf8b7c6af3'
down_revision: Union[str, None] = '78c43957d4fb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.add_column('user_profiles', sa.Column('age', sa.Integer(), nullable=True))
    op.add_column('user_profiles', sa.Column('gender', sa.String(), nullable=True))
    # Add all other columns from the models.py file
    
def downgrade():
    op.drop_column('user_profiles', 'age')
    op.drop_column('user_profiles', 'gender')
    # Drop all other columns you added