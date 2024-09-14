"""added tables for news art and refs

Revision ID: 73185df7db2c
Revises: 3f295b307174
Create Date: 2024-06-18 12:29:21.547167

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '73185df7db2c'
down_revision = '3f295b307174'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('art',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('date_pub', sa.String(length=10), nullable=False),
    sa.Column('url', sa.String(length=64), nullable=True),
    sa.Column('text', sa.String(length=128), nullable=True),
    sa.Column('summary', sa.String(length=1024), nullable=True),
    sa.Column('ent_names', sa.PickleType(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('news',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('date_pub', sa.String(length=10), nullable=False),
    sa.Column('url', sa.String(length=64), nullable=True),
    sa.Column('text', sa.String(length=128), nullable=True),
    sa.Column('summary', sa.String(length=1024), nullable=True),
    sa.Column('ent_names', sa.PickleType(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('references',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('date_pub', sa.String(length=10), nullable=False),
    sa.Column('url', sa.String(length=64), nullable=True),
    sa.Column('text', sa.String(length=128), nullable=True),
    sa.Column('summary', sa.String(length=1024), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('references')
    op.drop_table('news')
    op.drop_table('art')
    # ### end Alembic commands ###
