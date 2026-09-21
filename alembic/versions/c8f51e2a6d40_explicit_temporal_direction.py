"""Require explicit direction for new temporal-change reviews.

Revision ID: c8f51e2a6d40
Revises: b7e34c1f6a20
"""
from alembic import op
import sqlalchemy as sa

revision = "c8f51e2a6d40"
down_revision = "b7e34c1f6a20"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("conflict_review", sa.Column("superseding_claim_id", sa.UUID()))
    op.create_foreign_key("fk_review_superseding_claim_tenant", "conflict_review", "claim", ["organization_id", "superseding_claim_id"], ["organization_id", "id"])
    op.execute("""
      CREATE OR REPLACE FUNCTION provena_conflict_review_guard() RETURNS trigger LANGUAGE plpgsql AS $$
      DECLARE case_from uuid; case_to uuid; case_kind text;
      BEGIN
        IF (SELECT role FROM credential WHERE organization_id=NEW.organization_id AND id=NEW.reviewer_credential_id) IS DISTINCT FROM 'human'
           OR (SELECT revoked_at FROM credential WHERE organization_id=NEW.organization_id AND id=NEW.reviewer_credential_id) IS NOT NULL
        THEN RAISE EXCEPTION 'conflict review requires an active human credential'; END IF;
        SELECT kind, from_claim_id, to_claim_id INTO case_kind, case_from, case_to
          FROM claim_relationship WHERE organization_id=NEW.organization_id AND id=NEW.case_relationship_id;
        IF case_kind IS DISTINCT FROM 'related_to'
        THEN RAISE EXCEPTION 'conflict review requires a possible-conflict relationship'; END IF;
        IF NEW.decision='temporal_change' AND
           (NEW.superseding_claim_id IS NULL OR NEW.superseding_claim_id NOT IN (case_from, case_to))
        THEN RAISE EXCEPTION 'temporal change requires an explicit case-claim direction'; END IF;
        IF NEW.decision<>'temporal_change' AND NEW.superseding_claim_id IS NOT NULL
        THEN RAISE EXCEPTION 'only temporal change may choose a superseding claim'; END IF;
        RETURN NEW;
      END $$;
    """)


def downgrade() -> None:
    raise RuntimeError("Downgrading would discard reviewed temporal direction; restore from a backup instead")
