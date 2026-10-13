from app.models.review import ReviewTask
from app.providers.base import ChatMessage


SCALE_INSTRUCTIONS = {
    "宽松": "仅识别明确且影响签署或履约的重大风险，减少边界性提示。",
    "标准": "平衡覆盖与准确性，识别常见、实质性的合同风险。",
    "严格": "提高敏感度，覆盖完整性、一致性及边界风险，并提示人工复核。",
}

SYSTEM_CONSTRAINTS = (
    "仅依据本次合同材料和关联规则审查，不得虚构合同内容。"
    "风险引用必须尽量逐字引用同一材料中的连续原文，不得概括、拼接不相邻内容或改写；"
    "重复条款须同时返回紧邻原文的前后上下文和页码，证据不足时明确提示人工核验。"
    "输出必须是单个 JSON 对象，不要输出 Markdown。"
)

USER_TEMPLATE = """审查场景：{scene_name}
审查尺度：{scale}。{scale_instruction}
审查立场：{position}，请从该方利益角度说明风险和修改建议。

本次任务规则快照：
{rule_text}

输出格式：
{{
  "summary": "与风险明细一致的中文总结；无明显风险时仍提示人工复核",
  "risks": [
    {{
      "name": "风险名称",
      "level": "high|medium|low",
      "rule_id": "只能使用本次任务规则快照中的规则 ID",
      "rule_name": "规则名称",
      "original_text": "必须逐字引用材料原文；无法定位时填 null",
      "source": "主合同或附件的准确文件名",
      "source_file_id": "材料标题中的材料ID，例如 main 或 attachment:1",
      "page_number": "原文所在页码；无法确认时填 null",
      "context_before": "original_text 紧邻之前的少量逐字原文；没有或无法确认时填 null",
      "context_after": "original_text 紧邻之后的少量逐字原文；没有或无法确认时填 null",
      "description": "结合审查立场说明风险",
      "suggestion": "具体、明确、可执行的修改建议"
    }}
  ]
}}

要求：合并重复风险；风险等级仅用 high、medium、low；规则风险等级为默认等级，只有证据充分时才调整；不要把材料中不存在的内容作为事实。

合同材料：
{material}"""


def build_review_messages(task: ReviewTask) -> list[ChatMessage]:
    snapshot = task.scene_snapshot or {}
    rules = snapshot.get("rules", [])
    rule_text = "\n".join(
        (
            f"- {rule['rule_id']} {rule['rule_name']}（默认{rule.get('risk_level', 'medium')}）："
            f"{rule.get('review_requirement') or rule.get('requirement') or rule.get('description') or ''}"
        )
        for rule in rules
    )
    attachments = "\n\n".join(
        f"【材料ID：attachment:{index}｜附件：{item['file_name']}】\n{item['content']}"
        for index, item in enumerate(task.attachment_texts, start=1)
    )
    material = f"【材料ID：main｜主合同：{task.contract_name}】\n{task.contract_text}"
    if attachments:
        material += f"\n\n{attachments}"

    configured_prompt = snapshot.get("system_prompt") or "你是严谨的中国商事合同审查专家。"
    return [
        ChatMessage(role="system", content=f"{configured_prompt.strip()}\n\n{SYSTEM_CONSTRAINTS}"),
        ChatMessage(
            role="user",
            content=USER_TEMPLATE.format(
                scene_name=task.scene_name,
                scale=task.scale,
                scale_instruction=SCALE_INSTRUCTIONS[task.scale],
                position=task.position,
                rule_text=rule_text,
                material=material,
            ),
        ),
    ]
