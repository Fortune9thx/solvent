"""Judgment parsing, equivalence normalization, and prompt generation for SOLVENT.
Pure Python, zero external dependencies.
"""
import json
import re

from .accounting import (
    DECISION_FULL,
    DECISION_HALF,
    DECISION_INCONCLUSIVE,
    DECISION_NONE,
    VALID_DECISIONS,
)


def force_consistency(
    raw_decision: str,
    clause_ids: list[str],
    exclusion_ids: list[str],
    evidence_usable: list[int],
    code: str,
) -> dict:
    """
    Normalizes and forces consistency on adjudication fields.
    Rules:
      1. Decision must be in VALID_DECISIONS. Default to INCONCLUSIVE if unknown.
      2. If evidence_usable is empty -> decision MUST be INCONCLUSIVE (code: NO_USABLE_EVIDENCE).
      3. If decision is FULL or HALF, but exclusions are present and triggered ->
         force decision to NONE (code: VOIDED_BY_EXCLUSIONS) or INCONCLUSIVE.
      4. If decision is FULL or HALF, but no clauses were breached ->
         force decision to NONE (code: NO_CLAUSE_BREACHED).
      5. Clause IDs and Exclusion IDs must be sorted and deduplicated.
      6. evidence_usable must be sorted deduplicated integers.
    """
    decision = str(raw_decision).strip().upper()
    if decision not in VALID_DECISIONS:
        decision = DECISION_INCONCLUSIVE

    # Clean and sort clause_ids
    clean_clauses = sorted(list({str(c).strip() for c in clause_ids if str(c).strip()}))
    clean_exclusions = sorted(list({str(e).strip() for e in exclusion_ids if str(e).strip()}))

    # Clean and sort evidence_usable
    clean_usable = []
    for u in evidence_usable:
        try:
            val = int(u)
            if val >= 0 and val not in clean_usable:
                clean_usable.append(val)
        except (ValueError, TypeError):
            continue
    clean_usable.sort()

    clean_code = str(code).strip() if code else "OK"

    # Rule 2: No usable evidence -> INCONCLUSIVE
    if not clean_usable:
        decision = DECISION_INCONCLUSIVE
        clean_code = "NO_USABLE_EVIDENCE"

    # Rule 3: Exclusions void claim
    if decision in (DECISION_FULL, DECISION_HALF) and clean_exclusions:
        decision = DECISION_NONE
        clean_code = "VOIDED_BY_EXCLUSIONS"

    # Rule 4: Claim approved without clauses breached
    if decision in (DECISION_FULL, DECISION_HALF) and not clean_clauses:
        decision = DECISION_NONE
        clean_code = "NO_CLAUSE_BREACHED"

    return {
        "clause_ids": clean_clauses,
        "code": clean_code,
        "decision": decision,
        "evidence_usable": clean_usable,
        "exclusion_ids": clean_exclusions,
    }


def parse_llm_judgment_response(raw_response: str) -> dict:
    """
    Extracts JSON object from LLM response and applies force_consistency.
    """
    if not raw_response or not isinstance(raw_response, str):
        return force_consistency(DECISION_INCONCLUSIVE, [], [], [], "EMPTY_RESPONSE")

    # Search for JSON block or curly braces
    json_match = re.search(r"\{[\s\S]*\}", raw_response)
    if not json_match:
        return force_consistency(DECISION_INCONCLUSIVE, [], [], [], "NO_JSON_FOUND")

    try:
        data = json.loads(json_match.group(0))
    except Exception:
        return force_consistency(DECISION_INCONCLUSIVE, [], [], [], "JSON_PARSE_ERROR")

    raw_decision = data.get("decision", DECISION_INCONCLUSIVE)
    clause_ids = data.get("clause_ids", [])
    if not isinstance(clause_ids, list):
        clause_ids = []
    exclusion_ids = data.get("exclusion_ids", [])
    if not isinstance(exclusion_ids, list):
        exclusion_ids = []
    evidence_usable = data.get("evidence_usable", [])
    if not isinstance(evidence_usable, list):
        evidence_usable = []
    code = data.get("code", "OK")

    return force_consistency(raw_decision, clause_ids, exclusion_ids, evidence_usable, code)


def canonicalize_for_comparison(judgment_dict: dict) -> str:
    """
    Returns deterministic JSON string containing ONLY the 5 comparable fields in sorted order.
    """
    comparable = {
        "clause_ids": sorted(list(judgment_dict.get("clause_ids", []))),
        "code": str(judgment_dict.get("code", "")),
        "decision": str(judgment_dict.get("decision", DECISION_INCONCLUSIVE)),
        "evidence_usable": sorted(list(judgment_dict.get("evidence_usable", []))),
        "exclusion_ids": sorted(list(judgment_dict.get("exclusion_ids", []))),
    }
    return json.dumps(comparable, sort_keys=True, separators=(",", ":"))


def build_adjudication_prompt(
    policy_text: str,
    narrative: str,
    evidence_items: list[dict],
) -> str:
    """
    Builds the safe evaluation prompt for the LLM judge.
    evidence_items is a list of {'index': int, 'url': str, 'content': str}
    """
    lines = [
        "You are an impartial coverage bond arbitrator evaluating an incident claim under a strict policy.",
        "Your task is to review the policy, the incident narrative, and the independently retrieved HTTPS evidence.",
        "",
        "AVAILABLE DECISION OUTCOMES (choose EXACTLY one):",
        "- FULL: The evidence conclusively proves a total outage/breach under the policy terms.",
        "- HALF: The evidence conclusively proves a partial outage/breach under the policy terms.",
        "- NONE: The incident did not breach policy terms, or an explicit exclusion applies.",
        "- INCONCLUSIVE: The evidence is insufficient, contradictory, unreachable, or unverified.",
        "",
        "FROZEN POLICY TERMS:",
        f"[[POLICY_START]]\n{policy_text}\n[[POLICY_END]]",
        "",
        "CLAIMANT NARRATIVE:",
        f"[[NARRATIVE_START]]\n{narrative}\n[[NARRATIVE_END]]",
        "",
        "EVIDENCE RETRIEVED FROM HTTPS URLS:",
    ]

    for item in evidence_items:
        idx = item.get("index", 0)
        url = item.get("url", "")
        content = item.get("content", "")
        lines.append(f"Evidence #{idx} from {url}:")
        lines.append(f"[[EVIDENCE_{idx}_START]]\n{content}\n[[EVIDENCE_{idx}_END]]")

    lines.extend([
        "",
        "OUTPUT REQUIREMENT:",
        "Return ONLY a valid JSON object with EXACTLY this structure:",
        "{",
        '  "decision": "FULL" | "HALF" | "NONE" | "INCONCLUSIVE",',
        '  "clause_ids": ["CLAUSE-1", ...],',
        '  "exclusion_ids": ["EXCLUSION-1", ...],',
        '  "evidence_usable": [0, 1, ...],',
        '  "code": "REASON_CODE_IN_CAPS"',
        "}",
        "Do not include any conversational preamble or markdown backticks.",
    ])

    return "\n".join(lines)
