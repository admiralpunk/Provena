"""Add trusted credentials and append-only conflict review.

Revision ID: 9a7bce89dc4c
Revises: ccc08f8f4372
"""
from alembic import op
import sqlalchemy as sa

revision = "9a7bce89dc4c"
down_revision = "ccc08f8f4372"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "credential",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("key_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["organization_id"], ["organization.id"]),
        sa.UniqueConstraint("organization_id", "id"),
        sa.CheckConstraint("role IN ('agent','human','tool')", name="credential_role"),
    )
    op.execute("""
      INSERT INTO credential (id, organization_id, key_hash, role, label)
      SELECT gen_random_uuid(), id, api_key_hash, 'agent', 'migrated tenant key'
      FROM organization
    """)
    op.add_column("event", sa.Column("credential_id", sa.UUID()))
    op.create_foreign_key("fk_event_credential_tenant", "event", "credential", ["organization_id", "credential_id"], ["organization_id", "id"])
    op.add_column("memory_action", sa.Column("credential_id", sa.UUID()))
    op.create_foreign_key("fk_action_credential_tenant", "memory_action", "credential", ["organization_id", "credential_id"], ["organization_id", "id"])
    op.create_unique_constraint("uq_relationship_org_id", "claim_relationship", ["organization_id", "id"])
    op.create_table(
        "conflict_review",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("case_relationship_id", sa.UUID(), nullable=False),
        sa.Column("reviewer_credential_id", sa.UUID(), nullable=False),
        sa.Column("decision", sa.String(32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id", "case_relationship_id"], ["claim_relationship.organization_id", "claim_relationship.id"]),
        sa.ForeignKeyConstraint(["organization_id", "reviewer_credential_id"], ["credential.organization_id", "credential.id"]),
        sa.UniqueConstraint("organization_id", "case_relationship_id"),
        sa.CheckConstraint("decision IN ('contradiction','temporal_change','dismissed')", name="conflict_decision"),
    )
    op.drop_constraint("event_source_kind", "event", type_="check")
    op.drop_constraint("event_authority_policy", "event", type_="check")
    op.create_check_constraint("event_source_kind", "event", "source_kind IN ('user_statement','user_correction','tool_observation','test_output','assistant_inference','hypothesis')")
    op.create_check_constraint("event_authority_value", "event", "authority IN ('high','medium','low','ephemeral')")
    op.drop_constraint("organization_api_key_hash_key", "organization", type_="unique")
    op.drop_column("organization", "api_key_hash")
    op.execute("""
      CREATE FUNCTION provena_credential_guard() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN
        IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'credential history cannot be deleted'; END IF;
        IF ROW(NEW.organization_id, NEW.key_hash, NEW.role, NEW.label, NEW.created_at)
           IS DISTINCT FROM ROW(OLD.organization_id, OLD.key_hash, OLD.role, OLD.label, OLD.created_at)
           OR OLD.revoked_at IS NOT NULL OR NEW.revoked_at IS NULL
        THEN RAISE EXCEPTION 'credential may only be revoked once'; END IF;
        RETURN NEW;
      END $$;
      CREATE TRIGGER credential_guard BEFORE UPDATE OR DELETE ON credential
        FOR EACH ROW EXECUTE FUNCTION provena_credential_guard();
    """)
    op.execute("""
      CREATE FUNCTION provena_event_authority() RETURNS trigger LANGUAGE plpgsql AS $$
      DECLARE credential_role text; credential_revoked timestamptz;
      BEGIN
        IF NEW.credential_id IS NULL THEN RAISE EXCEPTION 'new events require a credential'; END IF;
        SELECT role, revoked_at INTO credential_role, credential_revoked FROM credential
          WHERE organization_id=NEW.organization_id AND id=NEW.credential_id;
        IF credential_role IS NULL OR credential_revoked IS NOT NULL THEN
          RAISE EXCEPTION 'credential missing or revoked'; END IF;
        IF NOT (
          (credential_role='agent' AND ((NEW.source_kind IN ('user_statement','assistant_inference') AND NEW.authority='low') OR (NEW.source_kind='hypothesis' AND NEW.authority='ephemeral')))
          OR (credential_role='human' AND ((NEW.source_kind='user_statement' AND NEW.authority='medium') OR (NEW.source_kind='user_correction' AND NEW.authority='high')))
          OR (credential_role='tool' AND NEW.source_kind IN ('tool_observation','test_output') AND NEW.authority='high')
        ) THEN RAISE EXCEPTION 'source authority is not allowed for credential role'; END IF;
        RETURN NEW;
      END $$;
      CREATE TRIGGER event_authority BEFORE INSERT ON event FOR EACH ROW
        EXECUTE FUNCTION provena_event_authority();
    """)
    op.execute("CREATE TRIGGER conflict_review_append_only BEFORE UPDATE OR DELETE ON conflict_review FOR EACH ROW EXECUTE FUNCTION provena_append_only()")
    op.execute("""
      CREATE FUNCTION provena_conflict_review_guard() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN
        IF (SELECT role FROM credential WHERE organization_id=NEW.organization_id AND id=NEW.reviewer_credential_id) IS DISTINCT FROM 'human'
           OR (SELECT revoked_at FROM credential WHERE organization_id=NEW.organization_id AND id=NEW.reviewer_credential_id) IS NOT NULL
        THEN RAISE EXCEPTION 'conflict review requires an active human credential'; END IF;
        IF (SELECT kind FROM claim_relationship WHERE organization_id=NEW.organization_id AND id=NEW.case_relationship_id) IS DISTINCT FROM 'related_to'
        THEN RAISE EXCEPTION 'conflict review requires a possible-conflict relationship'; END IF;
        RETURN NEW;
      END $$;
      CREATE TRIGGER conflict_review_guard BEFORE INSERT ON conflict_review FOR EACH ROW
        EXECUTE FUNCTION provena_conflict_review_guard();
    """)


def downgrade() -> None:
    raise RuntimeError("Downgrading would discard credential and review provenance; restore from a backup instead")
