"""Allow provider-specific embedding dimensions.

Revision ID: f6c42d8e0a73
Revises: e5b31c7d9f42
"""

from alembic import op
import sqlalchemy as sa

revision = "f6c42d8e0a73"
down_revision = "e5b31c7d9f42"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("ix_claim_embedding_hnsw", table_name="claim_embedding", postgresql_using="hnsw")
    op.execute("ALTER TABLE claim_embedding ALTER COLUMN embedding TYPE vector USING embedding::vector")
    op.add_column("claim_embedding", sa.Column("dimensions", sa.Integer(), sa.Computed("vector_dims(embedding)", persisted=True), nullable=False))
    op.create_check_constraint("embedding_dimensions", "claim_embedding", "dimensions > 0")


def downgrade() -> None:
    raise RuntimeError("Downgrading could discard embeddings with non-1536 dimensions; restore from a backup instead")
