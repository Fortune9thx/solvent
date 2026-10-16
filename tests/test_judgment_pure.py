"""Tests for pure judgment parsing, equivalence canonicalization, and force-consistency.
"""
from contracts.solventlib.judgment import (
    canonicalize_for_comparison,
    force_consistency,
    parse_llm_judgment_response,
)


def test_force_consistency_no_usable_evidence():
    # If LLM says FULL but evidence_usable is empty -> force INCONCLUSIVE
    res = force_consistency(
        raw_decision="FULL",
        clause_ids=["SLA-1"],
        exclusion_ids=[],
        evidence_usable=[],
        code="ALL_GOOD",
    )
    assert res["decision"] == "INCONCLUSIVE"
    assert res["code"] == "NO_USABLE_EVIDENCE"


def test_force_consistency_voided_by_exclusions():
    # If LLM says FULL or HALF but an exclusion is triggered -> force NONE
    res = force_consistency(
        raw_decision="FULL",
        clause_ids=["SLA-1"],
        exclusion_ids=["EXC-FORCE-MAJEURE"],
        evidence_usable=[0],
        code="MET",
    )
    assert res["decision"] == "NONE"
    assert res["code"] == "VOIDED_BY_EXCLUSIONS"


def test_force_consistency_no_clause_breached_fails_safe_to_inconclusive():
    # If LLM says HALF but cites no clause, the approval is malformed and
    # cannot be trusted: fail toward INCONCLUSIVE (bond refunded), never a
    # punitive NONE that would slash the claimant on an unsubstantiated output.
    res = force_consistency(
        raw_decision="HALF",
        clause_ids=[],
        exclusion_ids=[],
        evidence_usable=[0],
        code="OUTAGE_ALLEGED",
    )
    assert res["decision"] == "INCONCLUSIVE"
    assert res["code"] == "INCOMPLETE_VERDICT"


def test_force_consistency_exclusion_still_denies_even_without_clauses():
    # A triggered exclusion is a real denial: NONE wins over the rule-4
    # fail-safe, so an exclusion is never laundered into a refund.
    res = force_consistency(
        raw_decision="FULL",
        clause_ids=[],
        exclusion_ids=["EXC-FORCE-MAJEURE"],
        evidence_usable=[0],
        code="MET",
    )
    assert res["decision"] == "NONE"
    assert res["code"] == "VOIDED_BY_EXCLUSIONS"


def test_parse_llm_judgment_response():
    sample_json = """
    ```json
    {
        "decision": "HALF",
        "clause_ids": ["SLA-2"],
        "exclusion_ids": [],
        "evidence_usable": [1, 0],
        "code": "PARTIAL_OUTAGE_PROVEN"
    }
    ```
    """
    res = parse_llm_judgment_response(sample_json)
    assert res["decision"] == "HALF"
    assert res["clause_ids"] == ["SLA-2"]
    assert res["evidence_usable"] == [0, 1]  # sorted
    assert res["code"] == "PARTIAL_OUTAGE_PROVEN"


def test_canonicalize_for_comparison_reproducible():
    obj1 = {
        "decision": "HALF",
        "exclusion_ids": [],
        "clause_ids": ["B", "A"],
        "code": "OK",
        "evidence_usable": [2, 0],
        "extra_field": "ignored",
    }
    obj2 = {
        "clause_ids": ["A", "B"],
        "code": "OK",
        "decision": "HALF",
        "evidence_usable": [0, 2],
        "exclusion_ids": [],
    }
    str1 = canonicalize_for_comparison(obj1)
    str2 = canonicalize_for_comparison(obj2)
    assert str1 == str2
    assert "extra_field" not in str1
