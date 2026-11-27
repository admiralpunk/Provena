"""Record full-text retrieval as its own audited method.

Revision ID: b8c2e4f61a35
Revises: a7d53e9f1b84
"""

from alembic import op

revision = "b8c2e4f61a35"
down_revision = "a7d53e9f1b84"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("retrieval_method", "retrieval_event", type_="check")
    op.create_check_constraint("retrieval_method", "retrieval_event", "method IN ('exact','semantic','fulltext')")


def downgrade() -> None:
    # Fails while full-text retrievals exist, so their audit records are never rewritten.
    op.drop_constraint("retrieval_method", "retrieval_event", type_="check")
    op.create_check_constraint("retrieval_method", "retrieval_event", "method IN ('exact','semantic')")
