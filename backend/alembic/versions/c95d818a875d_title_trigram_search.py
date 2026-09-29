"""title trigram search

Revision ID: c95d818a875d
Revises: cdc8eb2da53d
Create Date: 2026-09-28 23:03:01.319766

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import pgvector.sqlalchemy


# revision identifiers, used by Alembic.
revision: str = 'c95d818a875d'
down_revision: Union[str, Sequence[str], None] = 'cdc8eb2da53d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE INDEX ix_movies_title_trgm ON movies USING gin (title gin_trgm_ops)")
    op.execute(
        "CREATE INDEX ix_movies_original_title_trgm ON movies USING gin (original_title gin_trgm_ops)"
    )
    op.create_index("ix_movies_original_language", "movies", ["original_language"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_movies_original_language", table_name="movies")
    op.execute("DROP INDEX ix_movies_original_title_trgm")
    op.execute("DROP INDEX ix_movies_title_trgm")
