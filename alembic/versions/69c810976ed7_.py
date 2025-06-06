"""empty message

Revision ID: 69c810976ed7
Revises: 823ec237c897
Create Date: 2025-05-07 21:47:50.873597

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '69c810976ed7'
down_revision: Union[str, None] = '823ec237c897'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('notion_integrations',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('access_token', sa.String(), nullable=False),
    sa.Column('workspace_id', sa.String(), nullable=True),
    sa.Column('formulas_db_id', sa.String(), nullable=True),
    sa.Column('docs_db_id', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id')
    )
    op.create_index(op.f('ix_notion_integrations_id'), 'notion_integrations', ['id'], unique=False)
    op.create_table('notion_syncs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('formula_id', sa.Integer(), nullable=False),
    sa.Column('notion_page_id', sa.String(), nullable=False),
    sa.Column('last_synced', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['formula_id'], ['formulas.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_notion_syncs_id'), 'notion_syncs', ['id'], unique=False)
    op.add_column('formulas', sa.Column('msds', sa.Text(), nullable=True))
    op.add_column('formulas', sa.Column('sop', sa.Text(), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('formulas', 'sop')
    op.drop_column('formulas', 'msds')
    op.drop_index(op.f('ix_notion_syncs_id'), table_name='notion_syncs')
    op.drop_table('notion_syncs')
    op.drop_index(op.f('ix_notion_integrations_id'), table_name='notion_integrations')
    op.drop_table('notion_integrations')
    # ### end Alembic commands ###
