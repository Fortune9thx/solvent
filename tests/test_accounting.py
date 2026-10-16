"""Tests for accounting and solvency invariant in solventlib.
"""
import pytest
from contracts.solventlib.accounting import (
    DECISION_FULL,
    DECISION_HALF,
    DECISION_INCONCLUSIVE,
    DECISION_NONE,
    calculate_payout,
    max_withdrawable,
    verify_solvency_invariant,
)


def test_calculate_payout_full():
    unit_face = 1000 * 10**18  # 1000 GEN
    fee_bps = 500              # 5% fee to treasury

    payout, fee = calculate_payout(unit_face, fee_bps, DECISION_FULL)
    # 5% of 1000 = 50 GEN
    assert fee == 50 * 10**18
    assert payout == 950 * 10**18
    assert payout + fee == unit_face


def test_calculate_payout_half():
    unit_face = 1000 * 10**18
    fee_bps = 500

    payout, fee = calculate_payout(unit_face, fee_bps, DECISION_HALF)
    # Gross half = 500 GEN; 5% fee = 25 GEN; Net payout = 475 GEN
    assert fee == 25 * 10**18
    assert payout == 475 * 10**18
    assert payout + fee == 500 * 10**18


def test_calculate_payout_none_and_inconclusive():
    unit_face = 1000 * 10**18
    fee_bps = 500

    p_none, f_none = calculate_payout(unit_face, fee_bps, DECISION_NONE)
    assert p_none == 0
    assert f_none == 0

    p_inc, f_inc = calculate_payout(unit_face, fee_bps, DECISION_INCONCLUSIVE)
    assert p_inc == 0
    assert f_inc == 0


def test_solvency_invariant_conservation():
    unit_face = 100 * 10**18
    live_units = 5
    # Required exposure = 500 GEN

    # Exact solvent
    assert verify_solvency_invariant(500 * 10**18, live_units, unit_face) is True
    # Over-collateralized
    assert verify_solvency_invariant(600 * 10**18, live_units, unit_face) is True
    # Under-collateralized (violation)
    assert verify_solvency_invariant(499 * 10**18, live_units, unit_face) is False


def test_max_withdrawable_respects_floor():
    unit_face = 100 * 10**18
    live_units = 5
    pool = 750 * 10**18

    withdrawable = max_withdrawable(pool, live_units, unit_face)
    assert withdrawable == 250 * 10**18

    # After withdrawing max_withdrawable, pool remains exactly solvent
    remaining = pool - withdrawable
    assert verify_solvency_invariant(remaining, live_units, unit_face) is True
    assert max_withdrawable(remaining, live_units, unit_face) == 0


def test_zero_withdrawable_when_under_floor():
    unit_face = 100 * 10**18
    live_units = 5
    pool = 400 * 10**18
    assert max_withdrawable(pool, live_units, unit_face) == 0
