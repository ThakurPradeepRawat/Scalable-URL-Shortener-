"""initial schema: urls + id_counter

Revision ID: 0001
Revises:
Create Date: 2026-09-27

"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "urls",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=False),
        sa.Column("short_code", sa.String(length=16), nullable=False, unique=True),
        sa.Column("long_url", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("click_count", sa.BigInteger(), server_default="0", nullable=False),
    )
    op.create_index("idx_short_code", "urls", ["short_code"], unique=True)
    op.create_index(
        "idx_expires_at",
        "urls",
        ["expires_at"],
        postgresql_where=sa.text("expires_at IS NOT NULL"),
    )

    op.create_table(
        "id_counter",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("current_value", sa.BigInteger(), nullable=False, server_default="0"),
    )
    # Seed the single counter row the block allocator UPDATEs against.
    op.execute("INSERT INTO id_counter (id, current_value) VALUES (1, 0)")


def downgrade() -> None:
    op.drop_table("id_counter")
    op.drop_index("idx_expires_at", table_name="urls")
    op.drop_index("idx_short_code", table_name="urls")
    op.drop_table("urls")
