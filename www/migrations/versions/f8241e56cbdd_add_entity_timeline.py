"""add entity.timeline

Revision ID: f8241e56cbdd
Revises: 1fc7fcd5abc5
Create Date: 2024-12-10 23:59:09.218566

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f8241e56cbdd'
down_revision = '1fc7fcd5abc5'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('entity', schema=None) as batch_op:
        batch_op.add_column(sa.Column('timeline', sa.String(length=4096), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('entity', schema=None) as batch_op:
        batch_op.drop_column('timeline')

    # ### end Alembic commands ###