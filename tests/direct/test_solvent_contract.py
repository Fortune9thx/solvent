"""
gltest direct-mode tests for SOLVENT.

These deploy the real bundle (contracts/build/Solvent.bundled.py) into a
real GenVM sandbox and drive the actual pool -> enroll -> file -> adjudicate
-> claim flow, plus the stale-cancel and pool-floor escape hatches. The
pure-logic rules are covered separately in tests/test_*.py.

The runner is pinned to the same SDK generation as the bundle's Depends
hash. `direct_vm.warp` moves the clock the contract reads via
datetime.now(timezone.utc), which is what makes the 72h stale window
testable without waiting.
"""

import json
import re
import subprocess
import sys
from datetime import datetime, timezone

import pytest

CONTRACT_PATH = "contracts/build/Solvent.bundled.py"
SDK_VERSION = "v0.6.0-rc6"

GEN = 10 ** 18
UNIT_FACE = 100 * GEN
MAX_UNITS = 3
CLAIM_BOND = 5 * GEN
FEE_BPS = 500  # 5%

POLICY = (
    "Coverage is owed when the beneficiary proves, from independently "
    "fetched HTTPS evidence, that the named service breached its published "
    "availability target. Force majeure and scheduled maintenance are "
    "excluded."
)

BASE_TIME = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)


def _hex(addr) -> str:
    s = str(addr)
    if s.startswith("0x") and len(s) == 42:
        return s.lower()
    return ("0x" + bytes(addr).hex()).lower()


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _verdict(decision, **overrides) -> str:
    payload = {
        "decision": decision,
        "clause_ids": ["SLA-1"],
        "exclusion_ids": [],
        "evidence_usable": [0],
        "code": "PROVEN",
    }
    payload.update(overrides)
    return json.dumps(payload)


PAGE_BODY = (
    "<html><head><title>Status</title></head><body>"
    "<p>The API was unavailable for 9 hours on 2026-05-30.</p>"
    "</body></html>"
)


@pytest.fixture
def contract(direct_deploy, direct_owner, direct_vm):
    # gltest clears its own artifacts/ dir at session start; rebuild so a
    # stale bundle can never be what is tested.
    subprocess.run(
        [sys.executable, "contracts/build_bundle.py"], check=True, capture_output=True
    )
    direct_vm.warp(_iso(BASE_TIME))
    return direct_deploy(
        CONTRACT_PATH,
        _hex(direct_owner),
        POLICY,
        str(UNIT_FACE),
        str(MAX_UNITS),
        str(CLAIM_BOND),
        str(FEE_BPS),
        sdk_version=SDK_VERSION,
    )


@pytest.fixture
def funded(contract, direct_vm):
    direct_vm.value = 3 * UNIT_FACE
    contract.top_up_pool()
    return contract


def _enroll(contract, direct_vm, who):
    with direct_vm.prank(who):
        return contract.enroll_unit()


def _file(contract, direct_vm, who, unit_id, urls=None):
    with direct_vm.prank(who):
        direct_vm.value = CLAIM_BOND
        return contract.file_claim(
            unit_id=unit_id,
            narrative="The service was down for most of the day.",
            urls=urls or ["https://status.example.com/incidents/2026-05-30"],
        )


def _adjudicate(contract, direct_vm, claim_id, decision, **overrides):
    direct_vm.mock_web(r".*", {"method": "GET", "status": 200, "body": PAGE_BODY})
    direct_vm.mock_llm(r".*", _verdict(decision, **overrides))
    return contract.adjudicate(claim_id=claim_id)


def _claimable(contract, addr) -> int:
    return int(contract.get_claimable(address=_hex(addr)))


# ---------------------------------------------------------------------------


class TestConfig:
    def test_deploy_and_config(self, contract):
        cfg = json.loads(contract.get_config())
        assert cfg["unit_face"] == str(UNIT_FACE)
        assert cfg["max_units"] == str(MAX_UNITS)
        assert cfg["claim_bond"] == str(CLAIM_BOND)
        assert cfg["fee_bps"] == FEE_BPS
        assert set(cfg["decisions"]) == {"FULL", "HALF", "NONE", "INCONCLUSIVE"}

    def test_policy_hash_is_stable(self, contract):
        p = json.loads(contract.get_policy())
        assert len(p["policy_hash"]) == 64
        assert "availability" in p["policy_text"]

    def test_initial_solvency_empty(self, contract):
        s = json.loads(contract.get_solvency())
        assert s["pool_balance"] == "0"
        assert s["live_units"] == "0"
        assert s["is_solvent"] is True

    def test_bad_fee_bps_rejected(self, direct_deploy, direct_owner, direct_vm):
        with pytest.raises(Exception):
            direct_deploy(
                CONTRACT_PATH,
                _hex(direct_owner),
                POLICY,
                str(UNIT_FACE),
                str(MAX_UNITS),
                str(CLAIM_BOND),
                "10001",
                sdk_version=SDK_VERSION,
            )


class TestPoolAndEnroll:
    def test_enroll_requires_backing(self, contract, direct_vm, direct_alice):
        # Empty pool -> cannot back a unit.
        with pytest.raises(Exception):
            _enroll(contract, direct_vm, direct_alice)

    def test_top_up_then_enroll(self, funded, direct_vm, direct_alice):
        uid = _enroll(funded, direct_vm, direct_alice)
        s = json.loads(funded.get_solvency())
        assert s["live_units"] == "1"
        assert s["is_solvent"] is True
        u = json.loads(funded.get_unit(unit_id=uid))
        assert u["status"] == "ACTIVE"
        assert u["beneficiary"] == _hex(direct_alice)

    def test_max_units_capped(self, funded, direct_vm, direct_alice, direct_bob):
        _enroll(funded, direct_vm, direct_alice)
        _enroll(funded, direct_vm, direct_bob)
        _enroll(funded, direct_vm, direct_bob)
        with pytest.raises(Exception, match=re.escape("MAX_UNITS")):
            _enroll(funded, direct_vm, direct_alice)

    def test_enroll_insolvent_after_withdraw(self, funded, direct_vm, direct_owner):
        # Withdraw down to exactly the floor, then a new unit must be refused.
        face = UNIT_FACE
        withdrawable = 3 * face - 0  # no live units yet -> whole pool
        direct_vm.value = 0
        funded.withdraw_pool(amount=str(withdrawable))
        with pytest.raises(Exception):
            _enroll(funded, direct_vm, direct_owner)


class TestFileClaim:
    def test_file_and_read_back(self, funded, direct_vm, direct_alice):
        uid = _enroll(funded, direct_vm, direct_alice)
        cid = _file(funded, direct_vm, direct_alice, uid)
        c = json.loads(funded.get_claim(claim_id=cid))
        assert c["status"] == "OPEN"
        assert c["bond"] == CLAIM_BOND
        assert c["urls"] == ["https://status.example.com/incidents/2026-05-30"]

    def test_bond_below_minimum_rejected(self, funded, direct_vm, direct_alice):
        uid = _enroll(funded, direct_vm, direct_alice)
        with direct_vm.prank(direct_alice):
            direct_vm.value = CLAIM_BOND - 1
            with pytest.raises(Exception, match=re.escape("BOND_TOO_SMALL")):
                funded.file_claim(
                    unit_id=uid, narrative="x", urls=["https://status.example.com"]
                )

    def test_only_beneficiary_can_file(self, funded, direct_vm, direct_alice, direct_bob):
        uid = _enroll(funded, direct_vm, direct_alice)
        with direct_vm.prank(direct_bob):
            direct_vm.value = CLAIM_BOND
            with pytest.raises(Exception, match=re.escape("NOT_BENEFICIARY")):
                funded.file_claim(
                    unit_id=uid, narrative="x", urls=["https://status.example.com"]
                )

    def test_second_open_claim_refused(self, funded, direct_vm, direct_alice):
        uid = _enroll(funded, direct_vm, direct_alice)
        _file(funded, direct_vm, direct_alice, uid)
        with pytest.raises(Exception, match=re.escape("UNIT_HAS_OPEN_CLAIM")):
            _file(funded, direct_vm, direct_alice, uid)

    def test_bad_and_private_urls_refused(self, funded, direct_vm, direct_alice):
        uid = _enroll(funded, direct_vm, direct_alice)
        for bad in ("http://status.example.com", "https://169.254.169.254/x"):
            with pytest.raises(Exception, match=re.escape("BAD_EVIDENCE_URLS")):
                _file(funded, direct_vm, direct_alice, uid, urls=[bad])

    def test_empty_narrative_refused(self, funded, direct_vm, direct_alice):
        uid = _enroll(funded, direct_vm, direct_alice)
        with direct_vm.prank(direct_alice):
            direct_vm.value = CLAIM_BOND
            with pytest.raises(Exception, match=re.escape("NARRATIVE_EMPTY")):
                funded.file_claim(
                    unit_id=uid, narrative="   ", urls=["https://status.example.com"]
                )


class TestAdjudicate:
    def test_full_pays_payout_plus_bond_and_conserves(self, funded, direct_vm, direct_alice):
        uid = _enroll(funded, direct_vm, direct_alice)
        cid = _file(funded, direct_vm, direct_alice, uid)
        decision = _adjudicate(funded, direct_vm, cid, "FULL")
        assert decision == "FULL"
        # payout = face - 5% fee; plus the bond refund.
        expected_bene = (UNIT_FACE - UNIT_FACE * FEE_BPS // 10000) + CLAIM_BOND
        assert _claimable(funded, direct_alice) == expected_bene
        s = json.loads(funded.get_solvency())
        assert s["live_units"] == "0"
        assert s["is_solvent"] is True
        assert int(s["pool_balance"]) == 3 * UNIT_FACE - UNIT_FACE

    def test_half_pays_half(self, funded, direct_vm, direct_alice):
        uid = _enroll(funded, direct_vm, direct_alice)
        cid = _file(funded, direct_vm, direct_alice, uid)
        assert _adjudicate(funded, direct_vm, cid, "HALF") == "HALF"
        gross_half = UNIT_FACE // 2
        expected = (gross_half - gross_half * FEE_BPS // 10000) + CLAIM_BOND
        assert _claimable(funded, direct_alice) == expected
        assert int(json.loads(funded.get_solvency())["pool_balance"]) == 3 * UNIT_FACE - gross_half

    def test_none_slashes_bond_to_treasury(self, funded, direct_vm, direct_alice, direct_owner):
        uid = _enroll(funded, direct_vm, direct_alice)
        cid = _file(funded, direct_vm, direct_alice, uid)
        assert _adjudicate(funded, direct_vm, cid, "NONE") == "NONE"
        assert _claimable(funded, direct_alice) == 0
        assert _claimable(funded, direct_owner) == CLAIM_BOND
        # Pool restored to the pre-claim balance; unit stays ACTIVE.
        assert int(json.loads(funded.get_solvency())["pool_balance"]) == 3 * UNIT_FACE

    def test_inconclusive_refunds_bond_no_payout(self, funded, direct_vm, direct_alice):
        uid = _enroll(funded, direct_vm, direct_alice)
        cid = _file(funded, direct_vm, direct_alice, uid)
        # No usable evidence forces INCONCLUSIVE via force-consistency.
        assert _adjudicate(
            funded, direct_vm, cid, "FULL", evidence_usable=[]
        ) == "INCONCLUSIVE"
        assert _claimable(funded, direct_alice) == CLAIM_BOND
        assert int(json.loads(funded.get_solvency())["pool_balance"]) == 3 * UNIT_FACE

    def test_force_consistency_voids_exclusion(self, funded, direct_vm, direct_alice):
        uid = _enroll(funded, direct_vm, direct_alice)
        cid = _file(funded, direct_vm, direct_alice, uid)
        # FULL but an exclusion is triggered -> NONE.
        assert _adjudicate(
            funded, direct_vm, cid, "FULL", exclusion_ids=["EXC-FORCE-MAJEURE"]
        ) == "NONE"


class TestClaimAndEscapes:
    def test_claim_pulls_once_then_nothing(self, funded, direct_vm, direct_alice):
        uid = _enroll(funded, direct_vm, direct_alice)
        cid = _file(funded, direct_vm, direct_alice, uid)
        _adjudicate(funded, direct_vm, cid, "FULL")
        with direct_vm.prank(direct_alice):
            direct_vm.value = 0
            paid = int(funded.claim())
            assert paid > 0
        assert _claimable(funded, direct_alice) == 0
        with direct_vm.prank(direct_alice):
            with pytest.raises(Exception, match=re.escape("NOTHING_TO_CLAIM")):
                funded.claim()

    def test_stale_cancel_after_window_refunds_bond(self, funded, direct_vm, direct_alice):
        uid = _enroll(funded, direct_vm, direct_alice)
        cid = _file(funded, direct_vm, direct_alice, uid)
        # Not yet cancellable under the window.
        with pytest.raises(Exception, match=re.escape("NOT_YET_CANCELLABLE")):
            funded.cancel_stale_claim(claim_id=cid)
        # Warp 73h and cancel permissionlessly.
        from datetime import timedelta

        direct_vm.warp(_iso(BASE_TIME + timedelta(hours=73)))
        assert funded.cancel_stale_claim(claim_id=cid) == "CANCELLED"
        assert _claimable(funded, direct_alice) == CLAIM_BOND
        assert json.loads(funded.get_claim(claim_id=cid))["status"] == "CANCELLED"
        assert json.loads(funded.get_unit(unit_id=uid))["open_claim_id"] == ""

    def test_withdraw_below_floor_rejected(self, funded, direct_vm, direct_owner, direct_alice):
        _enroll(funded, direct_vm, direct_alice)
        # Pool is 3*face; exposure is 1*face; withdrawable is 2*face.
        with pytest.raises(Exception, match=re.escape("EXCEEDS_POOL_FLOOR")):
            funded.withdraw_pool(amount=str(2 * UNIT_FACE + 1))
        assert funded.withdraw_pool(amount=str(2 * UNIT_FACE)) == str(2 * UNIT_FACE)

    def test_expire_unit_releases_exposure(self, funded, direct_vm, direct_alice):
        uid = _enroll(funded, direct_vm, direct_alice)
        assert funded.expire_unit(unit_id=uid) == "EXPIRED"
        assert json.loads(funded.get_solvency())["live_units"] == "0"
