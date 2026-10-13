"""add configuration indexes and default scenes

Revision ID: 20260804_0002
Revises: 20260803_0001
Create Date: 2026-08-04
"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "20260804_0002"
down_revision: str | None = "20260803_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


DEFAULT_RULES = [
    ("R001", "合同主体与签约权限审查", "合规校验", "high", "检查合同主体名称、资质、授权及签约权限是否完整有效。"),
    ("R002", "服务范围与交付成果审查", "条款完整性", "medium", "检查服务范围、交付成果、里程碑、交付期限和验收标准是否清晰。"),
    ("R003", "付款条件与结算节点审查", "金额与支付", "high", "检查付款比例、付款期限、前置条件、发票要求和结算安排是否完整。"),
    ("R004", "知识产权与成果归属审查", "AI语义审查", "high", "检查既有成果、定制成果和第三方组件的权属及使用范围。"),
    ("R005", "保密责任与数据安全审查", "合规校验", "medium", "检查保密范围、期限、数据处理、安全义务和泄露责任约定。"),
    ("R006", "违约责任与赔偿边界审查", "AI语义审查", "medium", "检查违约责任是否明确、对等，并识别赔偿范围及责任上限风险。"),
    ("R007", "合同解除与终止条件审查", "条款完整性", "low", "检查解除、终止、交接、存续义务及费用结算机制。"),
    ("R008", "争议解决条款审查", "合规校验", "low", "检查适用法律、管辖法院或仲裁机构是否明确有效。"),
]

DEFAULT_SCENES = [
    (
        "技术服务合同审查",
        "适用于技术开发、咨询与服务类合同",
        "你是严谨的技术服务合同审查专家。仅依据合同材料与关联规则，从用户选择的合同立场识别风险，重点关注服务范围、交付验收、付款、知识产权、数据安全与责任边界。不得虚构原文或法律结论。",
        1,
        ["R001", "R002", "R003", "R004", "R005", "R006"],
    ),
    (
        "采购合同审查",
        "适用于货物采购及配套服务合同",
        "你是严谨的采购合同审查专家。仅依据合同材料与关联规则，从用户选择的合同立场识别风险，重点关注标的规格、交付、验收、付款、质保、解除和违约责任。不得虚构原文或法律结论。",
        2,
        ["R001", "R002", "R003", "R006", "R007"],
    ),
    (
        "通用合同审查",
        "适用于暂无专用场景的常见合同",
        "你是严谨的商事合同审查专家。仅依据合同材料与关联规则，从用户选择的合同立场识别履约与合规风险。证据不足时应提示人工核验，不得虚构原文或确定性结论。",
        3,
        ["R001", "R003", "R006", "R007", "R008"],
    ),
]


def upgrade() -> None:
    op.create_index("ix_review_rule_status", "review_rule", ["status"])
    op.create_index(
        "ix_review_scene_available", "review_scene", ["status", "display_order"]
    )
    op.create_index(
        "ix_scene_rule_relation_rule_id", "scene_rule_relation", ["rule_id"]
    )

    now = datetime.now(UTC)
    rule_table = sa.table(
        "review_rule",
        sa.column("rule_id", sa.String),
        sa.column("rule_name", sa.String),
        sa.column("business_type", sa.String),
        sa.column("rule_type", sa.String),
        sa.column("risk_level", sa.String),
        sa.column("description", sa.Text),
        sa.column("review_requirement", sa.Text),
        sa.column("status", sa.Boolean),
        sa.column("update_time", sa.DateTime),
    )
    op.bulk_insert(
        rule_table,
        [
            {
                "rule_id": rule_id,
                "rule_name": name,
                "business_type": "合同审查",
                "rule_type": rule_type,
                "risk_level": risk_level,
                "description": requirement,
                "review_requirement": requirement,
                "status": True,
                "update_time": now,
            }
            for rule_id, name, rule_type, risk_level, requirement in DEFAULT_RULES
        ],
    )

    scene_table = sa.table(
        "review_scene",
        sa.column("scene_name", sa.String),
        sa.column("business_type", sa.String),
        sa.column("description", sa.String),
        sa.column("system_prompt", sa.Text),
        sa.column("status", sa.Boolean),
        sa.column("display_order", sa.Integer),
        sa.column("update_time", sa.DateTime),
    )
    op.bulk_insert(
        scene_table,
        [
            {
                "scene_name": name,
                "business_type": "合同审查",
                "description": description,
                "system_prompt": prompt,
                "status": True,
                "display_order": display_order,
                "update_time": now,
            }
            for name, description, prompt, display_order, _ in DEFAULT_SCENES
        ],
    )

    connection = op.get_bind()
    rule_ids = dict(
        connection.execute(sa.text("SELECT rule_id, id FROM review_rule")).all()
    )
    scene_ids = dict(
        connection.execute(sa.text("SELECT scene_name, id FROM review_scene")).all()
    )
    relation_table = sa.table(
        "scene_rule_relation",
        sa.column("scene_id", sa.Integer),
        sa.column("rule_id", sa.Integer),
    )
    op.bulk_insert(
        relation_table,
        [
            {"scene_id": scene_ids[scene_name], "rule_id": rule_ids[rule_id]}
            for scene_name, _, _, _, related_rule_ids in DEFAULT_SCENES
            for rule_id in related_rule_ids
        ],
    )


def downgrade() -> None:
    connection = op.get_bind()
    scene_names = [scene[0] for scene in DEFAULT_SCENES]
    rule_codes = [rule[0] for rule in DEFAULT_RULES]
    scene_table = sa.table(
        "review_scene", sa.column("id", sa.Integer), sa.column("scene_name", sa.String)
    )
    rule_table = sa.table(
        "review_rule", sa.column("id", sa.Integer), sa.column("rule_id", sa.String)
    )
    relation_table = sa.table(
        "scene_rule_relation",
        sa.column("scene_id", sa.Integer),
        sa.column("rule_id", sa.Integer),
    )
    seeded_scene_ids = sa.select(scene_table.c.id).where(
        scene_table.c.scene_name.in_(scene_names)
    )
    connection.execute(
        sa.delete(relation_table).where(relation_table.c.scene_id.in_(seeded_scene_ids))
    )
    connection.execute(sa.delete(scene_table).where(scene_table.c.scene_name.in_(scene_names)))
    connection.execute(sa.delete(rule_table).where(rule_table.c.rule_id.in_(rule_codes)))
    op.drop_index("ix_scene_rule_relation_rule_id", table_name="scene_rule_relation")
    op.drop_index("ix_review_scene_available", table_name="review_scene")
    op.drop_index("ix_review_rule_status", table_name="review_rule")
