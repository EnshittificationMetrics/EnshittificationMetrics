"""entity history

Revision ID: 1f15b75ca569
Revises: 73185df7db2c
Create Date: 2024-06-26 11:56:44.936847

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1f15b75ca569'
down_revision = '73185df7db2c'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('entity', schema=None) as batch_op:
        batch_op.add_column(sa.Column('stage_history', sa.PickleType(), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('entity', schema=None) as batch_op:
        batch_op.drop_column('stage_history')

    # ### end Alembic commands ###
