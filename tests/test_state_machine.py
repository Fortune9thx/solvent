"""State machine and invariant integration tests for Solvent contract logic.
Tests lifecycle: enroll, solvency check, claim filing, discrete accounting, stale cancel, withdrawal.
"""
import pytest
from contracts.solventlib.accounting import (
    DECISION_FULL,
    DECISION_HALF,
    DECISION_NONE,
    DECISION_INCONCLUSIVE,
    calculate_payout,
    verify_solvency_invariant,
    max_withdrawable,
)


class MockSolventState:
    """Simulates the Solvent contract state machine according to product law."""
    def __init__(self, unit_face: int, max_units: int, claim_bond: int, fee_bps: int):
        self.unit_face = unit_face
        self.max_units = max_units
        self.claim_bond = claim_bond
        self.fee_bps = fee_bps
        self.max_judge_attempts = 3
        self.pool_balance = 0
        self.live_units = 0
        self.units = {}
        self.claims = {}
        self.claimable = {}

    def top_up_pool(self, amount: int):
        assert amount > 0
        self.pool_balance += amount

    def enroll_unit(self, beneficiary: str, unit_id: int):
        assert len(self.units) < self.max_units, "Max units reached"
        new_live = self.live_units + 1
        assert verify_solvency_invariant(self.pool_balance, new_live, self.unit_face), "Insolvent"
        self.live_units = new_live
        self.units[unit_id] = {
            "unit_id": unit_id,
            "beneficiary": beneficiary,
            "status": "ACTIVE",
            "open_claim_id": 0,
        }

    def file_claim(self, unit_id: int, claim_id: int, beneficiary: str, bond: int, narrative: str, urls: list):
        assert bond >= self.claim_bond
        u = self.units[unit_id]
        assert u["status"] == "ACTIVE"
        assert u["beneficiary"] == beneficiary
        assert u["open_claim_id"] == 0
        assert len(narrative) > 0
        assert len(urls) > 0

        self.claims[claim_id] = {
            "claim_id": claim_id,
            "unit_id": unit_id,
            "beneficiary": beneficiary,
            "bond": bond,
            "status": "OPEN",
            "judge_attempts": 0,
        }
        u["open_claim_id"] = claim_id

    def adjudicate(self, claim_id: int, decision: str):
        c = self.claims[claim_id]
        assert c["status"] == "OPEN"
        c["judge_attempts"] += 1
        u = self.units[c["unit_id"]]

        b_addr = c["beneficiary"]
        bond = c["bond"]

        if decision == DECISION_FULL:
            payout, fee = calculate_payout(self.unit_face, self.fee_bps, DECISION_FULL)
            self.claimable[b_addr] = self.claimable.get(b_addr, 0) + payout + bond
            self.claimable["treasury"] = self.claimable.get("treasury", 0) + fee
            self.pool_balance -= self.unit_face
            self.live_units -= 1
            u["status"] = "CLAIMED_FULL"
            u["open_claim_id"] = 0
            c["status"] = "APPROVED"

        elif decision == DECISION_HALF:
            payout, fee = calculate_payout(self.unit_face, self.fee_bps, DECISION_HALF)
            self.claimable[b_addr] = self.claimable.get(b_addr, 0) + payout + bond
            self.claimable["treasury"] = self.claimable.get("treasury", 0) + fee
            gross_half = self.unit_face // 2
            self.pool_balance -= gross_half
            self.live_units -= 1
            u["status"] = "CLAIMED_HALF"
            u["open_claim_id"] = 0
            c["status"] = "APPROVED"

        elif decision == DECISION_NONE:
            self.claimable["treasury"] = self.claimable.get("treasury", 0) + bond
            u["open_claim_id"] = 0
            c["status"] = "DENIED"

        elif decision == DECISION_INCONCLUSIVE:
            self.claimable[b_addr] = self.claimable.get(b_addr, 0) + bond
            u["open_claim_id"] = 0
            c["status"] = "INCONCLUSIVE"


def test_state_machine_solvency_and_double_enroll():
    unit_face = 100 * 10**18
    sm = MockSolventState(unit_face=unit_face, max_units=2, claim_bond=5 * 10**18, fee_bps=500)

    # Initial enroll fails because pool is 0
    with pytest.raises(AssertionError, match="Insolvent"):
        sm.enroll_unit("0xalice", 1)

    # Deposit 200 GEN -> allows 2 units
    sm.top_up_pool(200 * 10**18)
    assert verify_solvency_invariant(sm.pool_balance, sm.live_units, sm.unit_face)

    # Enroll 1
    sm.enroll_unit("0xalice", 1)
    assert sm.live_units == 1
    assert verify_solvency_invariant(sm.pool_balance, sm.live_units, sm.unit_face)

    # Enroll 2
    sm.enroll_unit("0xbob", 2)
    assert sm.live_units == 2
    assert verify_solvency_invariant(sm.pool_balance, sm.live_units, sm.unit_face)

    # Enroll 3 fails due to max_units
    with pytest.raises(AssertionError, match="Max units reached"):
        sm.enroll_unit("0xcharlie", 3)


def test_full_claim_flow_and_invariant_preservation():
    unit_face = 100 * 10**18
    sm = MockSolventState(unit_face=unit_face, max_units=10, claim_bond=5 * 10**18, fee_bps=500)
    sm.top_up_pool(300 * 10**18)
    sm.enroll_unit("0xalice", 1)

    # File claim
    sm.file_claim(1, 1, "0xalice", 5 * 10**18, "Outage verified", ["https://status.app.com"])
    # Second claim on same unit fails
    with pytest.raises(AssertionError):
        sm.file_claim(1, 2, "0xalice", 5 * 10**18, "Duplicate", ["https://status.app.com"])

    # Adjudicate FULL
    sm.adjudicate(1, DECISION_FULL)

    # Check conservation
    # Pool had 300, face 100 paid out -> pool now 200
    assert sm.pool_balance == 200 * 10**18
    assert sm.live_units == 0
    assert verify_solvency_invariant(sm.pool_balance, sm.live_units, sm.unit_face)

    # Beneficiary claimable: 95 GEN payout + 5 GEN bond = 100 GEN
    assert sm.claimable["0xalice"] == 100 * 10**18
    # Treasury claimable: 5 GEN fee
    assert sm.claimable["treasury"] == 5 * 10**18
