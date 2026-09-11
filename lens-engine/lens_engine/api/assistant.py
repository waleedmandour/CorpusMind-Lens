"""Assistant routes (§9.20/§10) — grounded Q&A + tool surface + audit."""
from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..ai.audit import audit_event, read_audit
from ..ai.providers import Message, get_provider
from ..ai.tools import run_tool, tool_manifest
from ..config import get_settings
from ..logging import get_logger
from ..vision.annotations import DIMENSION_IDS

log = get_logger(__name__)
router = APIRouter(tags=["assistant"])

_SYSTEM = """You are the CorpusMind Lens Assistant, a grounded research assistant for
multimodal corpus analysis.
Rules:
1. Grounded tool-calling ONLY. Every factual/numeric claim in your answer must be tied to a
   tool result provided in this conversation (evidence ids will be shown to the user).
2. If you cannot ground a statement, prefix it with "[ungrounded]" — never present it as fact.
3. Interpretive claims must be phrased as framework-lensed hypotheses ("under a [Framework]
   reading, X may indicate Y"), never as settled facts about real people/institutions.
4. Use the user's vocabulary: image sets, images, annotations, measures."""


class AskBody(BaseModel):
    question: str
    set_id: str | None = None
    image_id: str | None = None
    provider_id: str = "ollama"
    model: str = ""


@router.get("/assistant/tools")
async def tools() -> list[dict]:
    return tool_manifest()


@router.get("/assistant/audit")
async def audit(limit: int = 100) -> list[dict]:
    return read_audit(limit)


@router.post("/assistant/ask")
async def ask(body: AskBody) -> dict:
    """Two-phase grounded ask: the model selects tools; each executed tool's
    result is fed back; the final answer must cite tool evidence. Any claim
    without a tool basis is required (by system prompt) to carry an
    '[ungrounded]' prefix, which the UI flags visibly (§4 Principle 2)."""
    settings = get_settings()
    provider = get_provider(body.provider_id)

    context_hint = {
        "set_id": body.set_id,
        "image_id": body.image_id,
        "available_tools": [t["name"] for t in tool_manifest()],
        "schema_dims": list(DIMENSION_IDS),
    }
    try:
        plan = await provider.chat(
            [Message(role="system", content=_SYSTEM),
             Message(role="user", content=(
                 f"Context: {json.dumps(context_hint)}\n\nQuestion: {body.question}\n\n"
                 f"Which tools (with arguments) should run to answer this grounded? "
                 f"Reply ONLY with JSON: [{{\"tool\": name, \"args\": {{...}}}}]. "
                 f"If none are needed, reply []."))],
            model=body.model or "llama3.1",
        )
    except Exception as e:
        raise HTTPException(502, f"Assistant planner unreachable ({body.provider_id}): {e}")

    tool_calls = []
    try:
        m = json.loads(plan.content[plan.content.find("["): plan.content.rfind("]") + 1])
        tool_calls = m if isinstance(m, list) else []
    except Exception:
        tool_calls = []

    results = []
    for call in tool_calls[:6]:
        name = str(call.get("tool", ""))
        args = call.get("args") or {}
        if body.set_id and "set_id" in args and not args.get("set_id"):
            args["set_id"] = body.set_id
        if body.image_id and "image_id" in args and not args.get("image_id"):
            args["image_id"] = body.image_id
        results.append({"tool": name, "result": run_tool(name, args)})

    evidence_block = json.dumps(
        [{"tool": r["tool"], "summary": r["result"].get("summary") or r["result"].get("error", ""),
          "grounded": r["result"].get("grounded", False),
          "data": r["result"].get("data")} for r in results],
        ensure_ascii=False, default=str)[:12000]

    try:
        answer = await provider.chat(
            [Message(role="system", content=_SYSTEM),
             Message(role="user", content=(
                 f"Question: {body.question}\n\nTool evidence (grounded):\n{evidence_block}\n\n"
                 f"Answer now. Cite the tool names that ground each claim. Prefix any "
                 f"ungrounded statement with [ungrounded]."))],
            model=body.model or "llama3.1",
        )
    except Exception as e:
        raise HTTPException(502, f"Assistant writer unreachable: {e}")

    audit_event("assistant_ask", question=body.question[:300],
                tools=[r["tool"] for r in results],
                provider=answer.provider, model=answer.model)
    return {
        "answer": answer.content,
        "provider": answer.provider,
        "model": answer.model,
        "tool_calls": [{"tool": r["tool"], "grounded": r["result"].get("grounded", False),
                        "summary": r["result"].get("summary") or r["result"].get("error")}
                       for r in results],
        "grounding_note": "Every claim resolves to a tool call above or is prefixed "
                          "[ungrounded] and flagged in the UI (§4 Principle 2).",
    }
