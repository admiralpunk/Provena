"""Add audited extraction runs and pgvector claim embeddings.

Revision ID: d4a2f19c8e01
Revises: c8f51e2a6d40
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

revision = "d4a2f19c8e01"
down_revision = "c8f51e2a6d40"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.add_column("retrieval_event", sa.Column("query_text", sa.Text()))
    op.add_column("retrieval_event", sa.Column("method", sa.String(32), nullable=False, server_default="exact"))
    op.create_check_constraint("retrieval_method", "retrieval_event", "method IN ('exact','semantic')")
    op.create_table(
        "claim_embedding",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("claim_id", sa.UUID(), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "id"),
        sa.UniqueConstraint("organization_id", "claim_id", "model"),
        sa.ForeignKeyConstraint(["organization_id", "claim_id"], ["claim.organization_id", "claim.id"]),
    )
    op.execute("CREATE INDEX ix_claim_embedding_hnsw ON claim_embedding USING hnsw (embedding vector_cosine_ops)")
    op.execute("CREATE TRIGGER claim_embedding_append_only BEFORE UPDATE OR DELETE ON claim_embedding FOR EACH ROW EXECUTE FUNCTION provena_append_only()")
    op.create_table(
        "extraction_run",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("event_id", sa.UUID(), nullable=False),
        sa.Column("extractor_model", sa.String(100), nullable=False),
        sa.Column("embedding_model", sa.String(100), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("facts", postgresql.JSONB(), nullable=False),
        sa.Column("error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "id"),
        sa.UniqueConstraint("organization_id", "event_id", "extractor_model", "embedding_model", name="uq_extraction_event_models"),
        sa.ForeignKeyConstraint(["organization_id", "event_id"], ["event.organization_id", "event.id"]),
        sa.CheckConstraint("status IN ('completed','failed')", name="extraction_status"),
    )
    op.execute("CREATE TRIGGER extraction_run_append_only BEFORE UPDATE OR DELETE ON extraction_run FOR EACH ROW EXECUTE FUNCTION provena_append_only()")


def downgrade() -> None:
    raise RuntimeError("Downgrading would discard extraction provenance and semantic indexes; restore from a backup instead")
