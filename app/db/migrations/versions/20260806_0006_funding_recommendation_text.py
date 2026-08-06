"""allow long funding recommendations

Revision ID: 20260806_0006
Revises: 20260806_0005
Create Date: 2026-08-06
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260806_0006"
down_revision: str | None = "20260806_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "funding_guide",
        "funding_stage_recommendation",
        existing_type=sa.String(length=100),
        type_=sa.Text(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "funding_guide",
        "funding_stage_recommendation",
        existing_type=sa.Text(),
        type_=sa.String(length=100),
        existing_nullable=True,
    )
