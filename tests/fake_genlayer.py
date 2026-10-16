"""Minimal fake_genlayer test harness:
Simulates strict_eq verification and validator disagreement.
"""
import pytest
from contracts.solventlib.judgment import canonicalize_for_comparison


class FakeValidatorCluster:
    def __init__(self):
        self.validators = []

    def register_validator(self, fn):
        self.validators.append(fn)

    def execute_nondet(self, leader_fn, eq_principle="strict_eq"):
        leader_output = leader_fn()
        for v in self.validators:
            v_output = v()
            if eq_principle == "strict_eq":
                if v_output != leader_output:
                    raise RuntimeError(f"Consensus failed: validator output '{v_output}' != leader '{leader_output}'")
        return leader_output


def test_validator_agreement_succeeds():
    cluster = FakeValidatorCluster()

    def leader():
        return canonicalize_for_comparison({
            "decision": "FULL",
            "clause_ids": ["SLA-1"],
            "exclusion_ids": [],
            "evidence_usable": [0],
            "code": "PROVEN",
        })

    def validator1():
        return canonicalize_for_comparison({
            "decision": "FULL",
            "clause_ids": ["SLA-1"],
            "exclusion_ids": [],
            "evidence_usable": [0],
            "code": "PROVEN",
        })

    cluster.register_validator(validator1)
    res = cluster.execute_nondet(leader)
    assert "FULL" in res


def test_validator_disagreement_aborts_without_state_change():
    cluster = FakeValidatorCluster()

    def leader():
        return canonicalize_for_comparison({
            "decision": "FULL",
            "clause_ids": ["SLA-1"],
            "exclusion_ids": [],
            "evidence_usable": [0],
            "code": "PROVEN",
        })

    def dissenting_validator():
        return canonicalize_for_comparison({
            "decision": "NONE",
            "clause_ids": [],
            "exclusion_ids": [],
            "evidence_usable": [0],
            "code": "UNPROVEN",
        })

    cluster.register_validator(dissenting_validator)
    with pytest.raises(RuntimeError, match="Consensus failed"):
        cluster.execute_nondet(leader)
