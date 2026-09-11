"""The 12 theoretical-framework discourse lenses (§9.13).

Framework templates are the ported, versioned YAML files in
``reference-data/frameworks/`` — loaded, never hard-coded. Each framework
runs in two modes:

* **heuristic** — deterministic: maps computed signals (colour notes,
  composition information value, detections, OCR text, annotation values)
  onto the framework's analytic categories, emitting claims with evidence
  ids and confidence. No model involvement; fully reproducible.
* **llm** — the framework YAML's guardrails become the system prompt; the
  model's output is parsed into the standard claim schema, passed through
  the consent gate, and any claim lacking an evidence id is flagged
  ``ungrounded`` (§4 Principle 2 — release-blocking ground truth).

Every claim is phrased as a framework-lensed hypothesis ("under a
[Framework] reading, X may indicate Y"), never as settled fact.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from ..logging import get_logger

log = get_logger(__name__)

FRAMEWORK_IDS = [
    "kress-van-leeuwen", "halliday-sfl", "fairclough-cda", "van-dijk-sca", "wodak-dha",
    "machin-mayr-mcda", "barthes-semiotics", "peirce-semiotics", "lakoff-johnson-cmt",
    "martin-white-appraisal", "toulmin-argumentation", "aristotle-rhetoric",
]


@dataclass(slots=True)
class FrameworkTemplate:
    id: str
    name: str
    full_name: str
    version: str
    framework_family: str
    categories: list[dict]
    guardrails: list[str]
    output_schema_hint: dict = field(default_factory=dict)
    raw: dict = field(default_factory=dict)


def load_frameworks(frameworks_dir: Path) -> dict[str, FrameworkTemplate]:
    out: dict[str, FrameworkTemplate] = {}
    for path in sorted(Path(frameworks_dir).glob("*.yaml")):
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception as e:
            log.warning("framework_yaml_unreadable", extra={"file": path.name, "error": str(e)})
            continue
        fid = raw.get("name") or path.stem
        out[fid] = FrameworkTemplate(
            id=fid,
            name=fid,
            full_name=raw.get("full_name", fid),
            version=str(raw.get("version", "0.0.0")),
            framework_family=raw.get("framework_family", "unknown"),
            categories=raw.get("categories", []) or [],
            guardrails=[str(g) for g in (raw.get("guardrails") or [])],
            output_schema_hint=raw.get("output_schema", {}) or {},
            raw=raw,
        )
    return out


# --------------------------------------------------------------------------- #
# Claim schema
# --------------------------------------------------------------------------- #


def claim(framework: str, category: str, text: str, evidence: list[str],
          confidence: float, *, mode: str = "heuristic", subcategory: str = "",
          ungrounded: bool = False) -> dict:
    """Standard claim dict — every downstream surface (API, UI, export,
    assistant) consumes this shape (§10: claim / evidence-ids / confidence /
    framework attribution)."""
    return {
        "framework": framework,
        "category": category,
        "subcategory": subcategory,
        "claim": text,
        "evidence": evidence,
        "confidence": round(confidence, 3),
        "mode": mode,
        "ungrounded": ungrounded,
    }


def hedge(framework_full_name: str, observation: str) -> str:
    """Wrap an observation in the framework-attributed hypothesis phrasing."""
    return f"Under a {framework_full_name} reading, {observation}"


# --------------------------------------------------------------------------- #
# Heuristic signal bundle
# --------------------------------------------------------------------------- #


@dataclass(slots=True)
class ImageSignals:
    """Everything the heuristic lenses reason over — all deterministic."""
    image_id: str
    colour: dict = field(default_factory=dict)
    composition: dict = field(default_factory=dict)
    ocr: dict = field(default_factory=dict)
    detections: list[dict] = field(default_factory=list)
    annotations: dict = field(default_factory=dict)
    caption: str = ""

    @property
    def info_value(self) -> dict:
        return (self.composition or {}).get("information_value", {})

    @property
    def ocr_text(self) -> str:
        return (self.ocr or {}).get("text", "") or self.caption

    def detection_labels(self, min_conf: float = 0.4) -> list[str]:
        return [d.get("label", "") for d in self.detections
                if float(d.get("confidence", 0)) >= min_conf and d.get("label")]


def signals_from_meta(image_id: str, meta: dict, caption: str = "") -> ImageSignals:
    return ImageSignals(
        image_id=image_id,
        colour=meta.get("colour") or {},
        composition=meta.get("composition") or {},
        ocr=meta.get("ocr") or {},
        detections=meta.get("detections") or [],
        annotations=meta.get("annotations") or {},
        caption=caption,
    )


# --------------------------------------------------------------------------- #
# Heuristic lens battery
# --------------------------------------------------------------------------- #

_SENTIMENT_POSITIVE = {"happy", "hope", "unity", "peace", "growth", "future", "together",
                       "success", "free", "family", "children", "progress"}
_SENTIMENT_NEGATIVE = {"fear", "threat", "crisis", "danger", "enemy", "war", "corrupt",
                       "decline", "chaos", "victim", "illegal", "invasion"}
_POWER_LEXICON = {"must", "will", "we demand", "stand with", "fight", "defend", "protect",
                  "strong", "strength", "power", "lead", "leader"}
_URGENCY = {"now", "today", "immediately", "urgent", "act", "join", "donate", "vote", "buy"}

_TECHNICAL_CDA = {"discourse", "strategy", "system", "reform", "policy", "economic",
                  "measures", "framework", "migration", "security"}


def _annotation_values(sig: ImageSignals, dim: str) -> list[str]:
    return list(((sig.annotations or {}).get(dim) or {}).get("values") or [])


def _kw(text: str, lexicon: set[str]) -> list[str]:
    t = f" {text.lower()} "
    return [w for w in lexicon if f" {w} " in t or f" {w}," in t or f" {w}." in t]


def _detect(sig: ImageSignals, labels: set[str]) -> list[str]:
    ll = sig.detection_labels()
    return [l for l in ll if any(k in l for k in labels)]


def heuristic_lens(fid: str, fw: FrameworkTemplate, sig: ImageSignals) -> list[dict]:
    """Deterministic claims per framework id. Each claim cites computed
    features (evidence ids) — nothing is generated from nothing."""
    F = fw.full_name
    claims: list[dict] = []
    iv = sig.info_value
    notes = (sig.colour or {}).get("colour_symbolism_notes") or []
    text = sig.ocr_text
    people = _detect(sig, {"person", "man", "woman", "child", "crowd", "face"})
    institutions = _detect(sig, {"flag", "logo", "symbol", "building", "mosque", "church"})

    # --- Visual Grammar family (Kress & van Leeuwen) ------------------------
    if fid == "kress-van-leeuwen":
        if iv.get("centre", 0) > 0.6:
            claims.append(claim(F, "compositional", hedge(
                F, "the centrality of the salient element may construct it as the "
                   "nucleus of the composition (centre–margin information value)."),
                ["composition.information_value.centre"],
                min(1.0, (iv["centre"] - 0.5) * 2), subcategory="centre_margin"))
        if iv.get("left", 0) > 0.6:
            claims.append(claim(F, "compositional", hedge(
                F, "salience concentrated on the left may present that zone as the "
                   "'Given' — what the viewer is treated as already knowing."),
                ["composition.information_value.left"], 0.55, subcategory="given_new"))
        if iv.get("top", 0) > 0.6:
            claims.append(claim(F, "compositional", hedge(
                F, "salience concentrated on the upper zone may present it as the "
                   "'Ideal' — the generalised or promised meaning."),
                ["composition.information_value.top"], 0.55, subcategory="ideal_real"))
        if people:
            shot = _annotation_values(sig, "shot_scale") or []
            sc = shot[0] if shot else ("close_up" if iv.get("centre", 0) > 0.55 else "long_shot")
            claims.append(claim(F, "interactive", hedge(
                F, f"the depiction of participants at '{sc}' may construct a particular "
                   f"social distance between viewer and represented participants."),
                ["detections.labels", "annotations.shot_scale"], 0.6,
                subcategory="social_distance"))
        for note in notes[:2]:
            claims.append(claim(F, "representational", hedge(
                F, f"the colour profile may function as a symbolic attribute: {note}"),
                ["colour.colour_symbolism_notes"], 0.5, subcategory="symbolic_attribute"))
        if not claims:
            claims.append(claim(F, "representational", hedge(
                F, "no strong compositional polarization was measured; the image may "
                   "rely on horizontal/vertical balance rather than centre-margin "
                   "hierarchy."), ["composition.information_value"], 0.3))

    # --- Halliday SFL --------------------------------------------------------
    elif fid == "halliday-sfl":
        if text:
            mood = "imperative" if _kw(text, _URGENCY) else "declarative"
            claims.append(claim(F, "interactive", hedge(
                F, f"the embedded text's dominant mood reads as {mood}, shaping the "
                   f"speech function the image offers its viewer (offer vs demand)."),
                ["ocr.text"], 0.55, subcategory="mood"))
        if iv.get("centre", 0) > 0.55:
            claims.append(claim(F, "representational", hedge(
                F, "central salience may realize a relational process — the image "
                   "ascribes an attribute to a central Carrier."),
                ["composition.information_value.centre"], 0.5))
        if _kw(text, _SENTIMENT_NEGATIVE):
            claims.append(claim(F, "representational", hedge(
                F, "negative-valenced lexis in the embedded text may realize material "
                   "or verbal processes of threat/loss in the ideational metafunction."),
                ["ocr.text"], 0.5))

    # --- CDA family ----------------------------------------------------------
    elif fid in ("fairclough-cda", "van-dijk-sca", "wodak-dha", "machin-mayr-mcda"):
        if text:
            power = _kw(text, _POWER_LEXICON)
            techn = _kw(text, _TECHNICAL_CDA)
            if power:
                claims.append(claim(F, "power_and_solidarity", hedge(
                    F, f"the modal/deontic lexis ({', '.join(power[:3])}) may enact "
                       f"authority and caller solidarity between text-producer and viewer."),
                    ["ocr.text"], 0.55, subcategory="modality"))
            if techn:
                claims.append(claim(F, "representation_of_social_actors", hedge(
                    F, f"nominalizations and technical lexis ({', '.join(techn[:3])}) may "
                       f"background agency — a classic re-wording strategy worth a closer "
                       f"passivity/transitivity pass."),
                    ["ocr.text"], 0.5, subcategory="nominalization"))
            pos, neg = _kw(text, _SENTIMENT_POSITIVE), _kw(text, _SENTIMENT_NEGATIVE)
            if pos and neg:
                claims.append(claim(F, "us_vs_them", hedge(
                    F, f"co-occurring positive self-referential lexis ({', '.join(pos[:2])}) "
                       f"and negative other-referential lexis ({', '.join(neg[:2])}) may "
                       f"construct in-group/out-group polarisation. This is a hypothesis "
                       f"about discursive strategy, not a settled fact about intent."),
                    ["ocr.text"], 0.5, subcategory="social_actors"))
        if institutions:
            claims.append(claim(F, "representation_of_social_actors", hedge(
                F, "detected institutional symbols/flags may anchor the depicted scene "
                   "to specific institutional or national identities."),
                ["detections.labels"], 0.45))
        if fid == "wodak-dha" and not claims:
            claims.append(claim(F, "discursive_strategies", hedge(
                F, "insufficient lexical signal was extracted for the discourse-"
                   "historical strategies pass; the image may need an OCR re-run or a "
                   "companion caption before the strategies can be assessed."),
                ["ocr.confidence"], 0.2))

    # --- Barthes semiotics ----------------------------------------------------
    elif fid == "barthes-semiotics":
        has_text = bool(text.strip())
        if has_text:
            claims.append(claim(F, "anchorage_relay", hedge(
                F, "the embedded text may function as ANCHORAGE — fixing the floating "
                   "chain of meanings the image projects. Relay (text advancing meaning "
                   "the image alone does not carry) cannot be ruled out from geometry "
                   "alone."), ["ocr.text", "annotations.multimodal_integration"], 0.5))
        if not has_text:
            claims.append(claim(F, "denotation", hedge(
                F, "with no embedded text, the image's connotative field may rest on its "
                   "denoted content alone (pure image message)."),
                ["ocr.word_count"], 0.35))
        for note in notes[:1]:
            claims.append(claim(F, "connotation", hedge(
                F, f"the colour profile may carry potential connotators: {note}"),
                ["colour.colour_symbolism_notes"], 0.45))

    # --- Peircean semiotics ----------------------------------------------------
    elif fid == "peirce-semiotics":
        if _detect(sig, {"logo", "emblem", "symbol", "flag"}):
            claims.append(claim(F, "symbol", hedge(
                F, "detected conventional marks may operate as SYMBOLS — signifying by "
                   "convention/habit rather than resemblance."),
                ["detections.labels"], 0.5))
        if people:
            claims.append(claim(F, "index", hedge(
                F, "depicted participants may function indexically — traces of the "
                   "events/persons they denote."),
                ["detections.labels"], 0.4))
        if not claims:
            claims.append(claim(F, "icon", hedge(
                F, "with no conventional marks detected, the image's signs may be "
                   "predominantly iconic (resemblance-driven)."),
                ["detections.labels"], 0.4))

    # --- Conceptual metaphor -----------------------------------------------------
    elif fid == "lakoff-johnson-cmt":
        met = []
        if _kw(text, {"journey", "path", "road", "step", "forward"}):
            met.append("LIFE/PROGRESS IS A JOURNEY")
        if _kw(text, {"build", "foundation", "strong", "framework", "construct"}):
            met.append("SOCIETY/ORGANISATION IS A BUILDING")
        if _kw(text, {"warm", "light", "dark", "cold"}):
            met.append("AFFECTION/VALUENCE IS TEMPERATURE")
        if _detect(sig, {"upward", "ladder", "mountain", "rising"}):
            met.append("MORE IS UP (importance/progress as verticality)")
        for m in met[:3]:
            claims.append(claim(F, "conceptual_metaphor", hedge(
                F, f"the visual/verbal evidence may instantiate the conceptual metaphor "
                   f"{m}. This is a candidate mapping for human verification "
                   f"(MIP/MIPVU-inspired gate), not a confirmed count."),
                ["ocr.text", "detections.labels"], 0.45))
        if not met:
            claims.append(claim(F, "conceptual_metaphor", hedge(
                F, "no strong metaphorical mappings surfaced from the extracted signals; "
                   "any mapping may remain implicit in the visual composition."),
                ["ocr.text"], 0.2))

    # --- Appraisal ----------------------------------------------------------------
    elif fid == "martin-white-appraisal":
        pos, neg = _kw(text, _SENTIMENT_POSITIVE), _kw(text, _SENTIMENT_NEGATIVE)
        if pos:
            claims.append(claim(F, "affect", hedge(
                F, f"positive affect lexis ({', '.join(pos[:3])}) may realize APPRECIATION/"
                   f"AFFECT of positive valence in the textual plane."),
                ["ocr.text"], 0.5))
        if neg:
            claims.append(claim(F, "affect", hedge(
                F, f"negative affect lexis ({', '.join(neg[:3])}) may realize negative "
                   f"AFFECT; check for amplified (graduated) forms nearby."),
                ["ocr.text"], 0.5))
        if _kw(text, {"clearly", "obviously", "undeniably", "certainly"}):
            claims.append(claim(F, "engagement", hedge(
                F, "high-certainty boosters may contract dialogic space — the text "
                   "positions its reading as the only reasonable one."),
                ["ocr.text"], 0.5))
        if not claims:
            claims.append(claim(F, "appraisal", hedge(
                F, "no strong appraisal signal in the extracted text; image-side "
                   "appraisal may remain available to the LLM/interpretive pass."),
                ["ocr.word_count"], 0.2))

    # --- Argumentation / persuasion ----------------------------------------------
    elif fid == "toulmin-argumentation":
        if text:
            claims.append(claim(F, "claim_warrant", hedge(
                F, "the embedded text may be treated as the ARGUMENT's claim; assess the "
                   "image as implicit warrant/backup linking the claim to its audience."),
                ["ocr.text"], 0.45))
        if _kw(text, _URGENCY):
            claims.append(claim(F, "motivation", hedge(
                F, "urgency markers may function as motivational appeals standing in "
                   "for explicit backing."),
                ["ocr.text"], 0.45))
        if not text:
            claims.append(claim(F, "claim_warrant", hedge(
                F, "with no embedded text, the image alone may carry the argumentative "
                   "burden; warrant reconstruction is fully inferential (low confidence)."),
                ["ocr.word_count"], 0.25))

    elif fid == "aristotle-rhetoric":
        if people and (sig.colour or {}).get("warm_cold_balance", 0) > 0.2:
            claims.append(claim(F, "pathos", hedge(
                F, "warm palette + human participants may constitute a pathos appeal "
                   "(affective identification)."),
                ["colour.warm_cold_balance", "detections.labels"], 0.5))
        if _kw(text, {"study", "research", "data", "expert", "according"}):
            claims.append(claim(F, "logos", hedge(
                F, "evidence-flavoured lexis may constitute a logos appeal; verify the "
                   "claims actually cited are present (do not count vibes as sources)."),
                ["ocr.text"], 0.5))
        if _detect(sig, {"logo", "building", "flag"}):
            claims.append(claim(F, "ethos", hedge(
                F, "institutional marks may ground an ethos appeal (authority by "
                   "association)."), ["detections.labels"], 0.45))
        if not claims:
            claims.append(claim(F, "rhetoric", hedge(
                F, "the rhetorical appeals profile is weak from deterministic signals "
                   "alone; run the LLM mode for an interpretive layer."),
                ["colour.dominant_colours"], 0.2))

    return claims


# --------------------------------------------------------------------------- #
# LLM mode
# --------------------------------------------------------------------------- #

_LLM_SYSTEM = """You are a discourse-analysis assistant applying the {full_name} framework.
Analytic categories: {categories}.
Output STRICT JSON: a list of claims, each {{"claim": str, "evidence_ids": [str],
"confidence": float, "category": str}}.
Guardrails you MUST obey:
{guardrails}
Evidence ids must reference concrete features the user provides (colour.*,
composition.*, ocr.*, detections.*, annotations.*). If you cannot cite evidence,
set "ungrounded": true on the claim. Never state ideology, bias, or power
relations as settled fact."""


async def llm_lens(fid: str, fw: FrameworkTemplate, sig: ImageSignals, provider, model: str) -> dict:
    """LLM mode for one framework lens. The model receives ONLY the
    deterministic evidence bundle and the YAML guardrails; its claims are
    parsed into the standard schema, flagged ungrounded when they cite no
    evidence, and passed through the consent gate."""
    import json as _json
    import re as _re

    from ..ai.providers import Message
    from ..vision.consent_gate import filter_discourse_claims

    system = _LLM_SYSTEM.format(
        full_name=fw.full_name,
        categories=", ".join(c.get("label", c.get("id", "?")) for c in fw.categories),
        guardrails="\n".join(f"- {g}" for g in fw.guardrails),
    )
    evidence_bundle = {
        "colour": sig.colour,
        "composition": sig.composition,
        "ocr": {"text": sig.ocr_text, "confidence": (sig.ocr or {}).get("confidence")},
        "detections": sig.detections,
        "annotations": sig.annotations,
    }
    user = (
        "Evidence bundle (deterministic computations — cite these as evidence_ids):\n"
        + _json.dumps(evidence_bundle, ensure_ascii=False, default=str)[:6000]
        + "\n\nApply the framework. Return ONLY the JSON claims list."
    )
    resp = await provider.chat(
        [Message(role="system", content=system), Message(role="user", content=user)],
        model=model,
    )

    raw = resp.content.strip()
    parsed: list = []
    claims_parsed, ungrounded_count = [], 0
    try:
        m = _re.search(r"\[.*\]", raw, _re.S)
        parsed = _json.loads(m.group(0)) if m else []
    except Exception:
        parsed = []
    for c in parsed if isinstance(parsed, list) else []:
        evidence = [str(e) for e in (c.get("evidence_ids") or c.get("evidence") or [])]
        ungrounded = bool(c.get("ungrounded")) or not evidence
        ungrounded_count += 1 if ungrounded else 0
        claims_parsed.append(claim(
            fw.full_name, str(c.get("category", "general")),
            str(c.get("claim", "")), evidence, float(c.get("confidence", 0.4)),
            mode="llm", ungrounded=ungrounded,
        ))
    gated = filter_discourse_claims(claims_parsed)
    return {
        "claims": gated["claims"],
        "person_descriptive_redacted": gated["person_descriptive_redacted"],
        "ungrounded_count": ungrounded_count,
        "model": resp.model,
        "provider": resp.provider,
        "parse_failed": parsed == [],
    }


FRAMEWORK_HINTS: dict[str, str] = {
    # heuristics keyed by template family when no specialised branch exists
}
