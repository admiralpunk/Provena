"""Give external agent sessions an idempotent identity.

Revision ID: a7d53e9f1b84
Revises: f6c42d8e0a73
"""

from alembic import op

revision = "a7d53e9f1b84"
down_revision = "f6c42d8e0a73"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint("uq_session_external_ref", "session", ["organization_id", "scope_id", "external_ref"])


def downgrade() -> None:
    op.drop_constraint("uq_session_external_ref", "session", type_="unique")
