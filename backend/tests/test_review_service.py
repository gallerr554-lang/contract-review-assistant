import json

import pytest

from app.models.review import ReviewTask
from app.schemas.review import ModelReviewOutput
from app.service.review_service import ReviewService


def test_parse_model_json_code_fence() -> None:
    payload = {
        "summary": "付款条件存在风险。",
        "risks": [
            {
                "name": "付款条件不明确",
                "level": "medium",
                "rule_id": "R003",
                "rule_name": "付款条件与结算节点审查",
                "original_text": "付款节点另行协商",
                "source": "合同.txt",
                "description": "付款义务触发条件不清晰。",
                "suggestion": "补充验收及发票作为付款前提。",
            }
        ],
    }

    output = ReviewService.parse_model_output(f"```json\n{json.dumps(payload)}\n```")

    assert output.summary == "付款条件存在风险。"
    assert output.risks[0].rule_id == "R003"


def test_reject_invalid_model_output() -> None:
    with pytest.raises(ValueError, match="JSON"):
        ReviewService.parse_model_output("无法完成审查")


def test_normalize_marks_unmatched_quote_for_manual_review(tmp_path) -> None:
    service = ReviewService(file_service=None)
    task = ReviewTask(
        task_no="CR001",
        upload_id="upload",
        contract_name="合同.txt",
        contract_text="付款应在验收后十日内完成。",
        attachment_names=[],
        attachment_texts=[],
        scene_name="通用合同审查",
        scene_snapshot={
            "rules": [
                {
                    "rule_id": "R003",
                    "rule_name": "付款条件与结算节点审查",
                    "risk_level": "medium",
                    "review_requirement": "检查付款条件。",
                }
            ]
        },
        scale="标准",
        position="甲方",
        status="PROCESSING",
        progress=0,
        current_step=0,
        current_message="测试",
    )
    output = ModelReviewOutput.model_validate(
        {
            "summary": "存在付款风险。",
            "risks": [
                {
                    "name": "付款条件不明确",
                    "level": "medium",
                    "rule_id": "R003",
                    "rule_name": "付款条件与结算节点审查",
                    "original_text": "付款节点另行协商",
                    "source": "合同.txt",
                    "description": "说明",
                    "suggestion": "建议",
                }
            ],
        }
    )

    risks = service._normalize_risks(task, output)

    assert risks[0]["locatable"] is False
    assert risks[0]["source"] == "合同.txt"
