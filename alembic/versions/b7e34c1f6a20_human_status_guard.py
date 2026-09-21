"""Require active human credentials for new status actions.

Revision ID: b7e34c1f6a20
Revises: 9a7bce89dc4c
"""
from alembic import op

revision = "b7e34c1f6a20"
down_revision = "9a7bce89dc4c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
      CREATE FUNCTION provena_status_action_guard() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN
        IF NEW.action = 'status_changed' AND NOT EXISTS (
          SELECT 1 FROM credential c WHERE c.organization_id=NEW.organization_id
            AND c.id=NEW.credential_id AND c.role='human' AND c.revoked_at IS NULL
        ) THEN RAISE EXCEPTION 'status change requires an active human credential'; END IF;
        RETURN NEW;
      END $$;
      CREATE TRIGGER status_action_guard BEFORE INSERT ON memory_action FOR EACH ROW
        EXECUTE FUNCTION provena_status_action_guard();
    """)


def downgrade() -> None:
    op.execute("DROP FUNCTION provena_status_action_guard() CASCADE")
