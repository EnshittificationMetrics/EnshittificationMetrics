"""remove MutableList

Revision ID: b9e3ebf83d5d
Revises: 1f15b75ca569
Create Date: 2024-07-03 13:51:30.530223

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b9e3ebf83d5d'
down_revision = '1f15b75ca569'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('art', schema=None) as batch_op:
        batch_op.drop_column('ent_names')

    with op.batch_alter_table('entity', schema=None) as batch_op:
        batch_op.drop_column('stage_history')

    with op.batch_alter_table('news', schema=None) as batch_op:
        batch_op.drop_column('ent_names')

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('news', schema=None) as batch_op:
        batch_op.add_column(sa.Column('ent_names', sa.BLOB(), nullable=True))

    with op.batch_alter_table('entity', schema=None) as batch_op:
        batch_op.add_column(sa.Column('stage_history', sa.BLOB(), nullable=True))

    with op.batch_alter_table('art', schema=None) as batch_op:
        batch_op.add_column(sa.Column('ent_names', sa.BLOB(), nullable=True))

    # ### end Alembic commands ###