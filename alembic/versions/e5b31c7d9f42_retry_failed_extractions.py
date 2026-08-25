"""Preserve failed extraction attempts while permitting retry.

Revision ID: e5b31c7d9f42
Revises: d4a2f19c8e01
"""

from alembic import op

revision = "e5b31c7d9f42"
down_revision = "d4a2f19c8e01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("uq_extraction_event_models", "extraction_run", type_="unique")
    op.create_index("ix_extraction_event_models", "extraction_run", ["organization_id", "event_id", "extractor_model", "embedding_model"])


def downgrade() -> None:
    raise RuntimeError("Downgrading would make preserved extraction retries incompatible; restore from a backup instead")
