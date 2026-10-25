"""add_archived_at_to_candidate_profiles

Revision ID: 838873041248
Revises: 39d52ff65f22
Create Date: 2026-10-25 19:30:45.421673

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '838873041248'
down_revision: Union[str, None] = '39d52ff65f22'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('candidate_profiles', sa.Column('archived_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('candidate_profiles', 'archived_at')

