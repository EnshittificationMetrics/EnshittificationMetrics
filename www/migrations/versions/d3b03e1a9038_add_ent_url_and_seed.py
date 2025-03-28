"""add ent url and seed

Revision ID: d3b03e1a9038
Revises: f47f398aface
Create Date: 2025-01-28 16:16:13.255948

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd3b03e1a9038'
down_revision = 'f47f398aface'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('entity', schema=None) as batch_op:
        batch_op.add_column(sa.Column('ent_url', sa.String(length=70), nullable=True))
        batch_op.add_column(sa.Column('seed', sa.Text(), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('entity', schema=None) as batch_op:
        batch_op.drop_column('seed')
        batch_op.drop_column('ent_url')

    # ### end Alembic commands ###
