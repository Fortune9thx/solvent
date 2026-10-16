"""Strict accounting and solvency invariant calculations for SOLVENT.
Pure Python, zero external dependencies.
All values are integer wei (u256). No floats.
"""

# Discrete decision outcomes
DECISION_FULL = "FULL"
DECISION_HALF = "HALF"
DECISION_NONE = "NONE"
DECISION_INCONCLUSIVE = "INCONCLUSIVE"

VALID_DECISIONS = {DECISION_FULL, DECISION_HALF, DECISION_NONE, DECISION_INCONCLUSIVE}

# Unit lifecycle states
UNIT_ACTIVE = "ACTIVE"
UNIT_EXPIRED = "EXPIRED"
UNIT_CLAIMED_FULL = "CLAIMED_FULL"
UNIT_CLAIMED_HALF = "CLAIMED_HALF"

# Claim lifecycle states
CLAIM_OPEN = "OPEN"
CLAIM_APPROVED = "APPROVED"       # Decision FULL or HALF; pending claim()
CLAIM_DENIED = "DENIED"           # Decision NONE
CLAIM_INCONCLUSIVE = "INCONCLUSIVE"  # Decision INCONCLUSIVE
CLAIM_SETTLED = "SETTLED"         # Funds withdrawn via claim()
CLAIM_CANCELLED = "CANCELLED"     # Stale cancellation
CLAIM_ABANDONED = "ABANDONED"     # Abandon approved claim


def calculate_payout(unit_face: int, fee_bps: int, decision: str) -> tuple[int, int]:
    """
    Calculates beneficiary payout and treasury fee for a decision.
    payout_beneficiary, fee_amount
    All math is strict integer division.
    """
    if not (0 <= fee_bps <= 10000):
        raise ValueError("fee_bps must be between 0 and 10000")
    if unit_face < 0:
        raise ValueError("unit_face must be non-negative")

    if decision == DECISION_FULL:
        fee_amount = (unit_face * fee_bps) // 10000
        payout = unit_face - fee_amount
        return payout, fee_amount
    elif decision == DECISION_HALF:
        gross_half = unit_face // 2
        fee_amount = (gross_half * fee_bps) // 10000
        payout = gross_half - fee_amount
        return payout, fee_amount
    elif decision in (DECISION_NONE, DECISION_INCONCLUSIVE):
        return 0, 0
    else:
        raise ValueError(f"Unknown decision: {decision}")


def verify_solvency_invariant(pool_balance: int, live_units: int, unit_face: int) -> bool:
    """
    Asserts pool_balance >= live_units * unit_face
    """
    if pool_balance < 0 or live_units < 0 or unit_face < 0:
        return False
    return pool_balance >= (live_units * unit_face)


def max_withdrawable(pool_balance: int, live_units: int, unit_face: int) -> int:
    """
    Calculates maximum amount the issuer can withdraw while maintaining solvency.
    Exposure floor = live_units * unit_face.
    """
    exposure = live_units * unit_face
    if pool_balance < exposure:
        return 0
    return pool_balance - exposure
