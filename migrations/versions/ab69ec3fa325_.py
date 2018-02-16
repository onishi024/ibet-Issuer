"""empty message

Revision ID: ab69ec3fa325
Revises: 315113b9a387
Create Date: 2018-02-16 08:54:54.492296

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ab69ec3fa325'
down_revision = '315113b9a387'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('tokens', sa.Column('abi', sa.String(length=5024), nullable=True))
    op.add_column('tokens', sa.Column('bytecode', sa.String(length=5024), nullable=False))
    op.add_column('tokens', sa.Column('bytecode_runtime', sa.String(length=5024), nullable=False))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('tokens', 'bytecode_runtime')
    op.drop_column('tokens', 'bytecode')
    op.drop_column('tokens', 'abi')
    # ### end Alembic commands ###