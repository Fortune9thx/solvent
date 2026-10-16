# Audit — self-review

Scope: `contracts/Solvent.py` + `contracts/solventlib/*` (the bundled deployable
file), the deploy tooling, and the frontend's read/write path. Method: source
review against the product law, the invariant, and the nondet boundary; the 49
tests; `genvm-lint`; a live schema/constant verification; and manual tracing of
every value-moving path. This is a self-audit, not an independent third party.

## Value-moving paths — traced

Every exit of GEN from the contract:

1. `claim()` → zeroes the ledger, then `emit_transfer`. **The only outbound path.**
2. `withdraw_pool(amount)` → `pool_balance -= amount`, credit issuer. Funds stay
   in-contract until `claim()`.
3. `adjudicate` credits (FULL/HALF payout+bond; NONE bond→treasury; INCONCLUSIVE
   bond→beneficiary). Credits only; no transfer.
4. `cancel_stale_claim` / `expire_unit` credit or release exposure; no transfer.

Checked: credits never exceed `pool_balance` for the payout path, because the
payout is derived from `unit_face` which the pool was required to back at
enrollment; `_assert_solvent()` runs after each. The fee credit is intra-contract
(issuer treasury), so it does not break the pool invariant.

## Invariant and accounting — checked

- `calculate_payout` is strict integer division; `FULL` = face − fee, `HALF` =
  face/2 − fee, `NONE`/`INCONCLUSIVE` = 0.
- Enrollment solvency-checked before exposure; withdrawal floored at live
  exposure; both covered by direct tests (`test_enroll_requires_backing`,
  `test_withdraw_below_floor_rejected`, `test_enroll_insolvent_after_withdraw`).
- Double-claim and double-open-claim paths return `NOTHING_TO_CLAIM` /
  `UNIT_HAS_OPEN_CLAIM` (direct tests).

## Nondet boundary — checked

Leader returns the canonical envelope as a string; validator calls the identical
`leader_fn` and compares strings. The agreed envelope is `json.loads`-ed inside
deterministic code, coerced to a dict, and the decision is validated against
`VALID_DECISIONS` (defaulting to `INCONCLUSIVE`). Storage is re-loaded after the
nondet call rather than trusting captured objects. Addresses are normalized to
lowercase hex at every write and lookup — including `claim()`, where a
case-mismatch bug (found by direct test `test_claim_pulls_once_then_nothing`)
had zeroed the ledger at a non-normalized key while crediting a lowercased one.

## Findings

### F1 — `sanitize_text` corrupted ordinary words (fixed)

**Severity:** correctness / low security. The forbidden-pattern list removed the
literal word `END` case-insensitively (and `BEGIN`, and any `---`). On the first
live deploy this silently turned `independently` into `indep ently` in the frozen
policy and changed `policy_hash`. **Fix:** strip only delimiter-impersonation
tokens (`[[`/`]]`/`<<<`/`>>>`/fences). Regression: 
`test_sanitize_text_preserves_ordinary_words`. **Redeployed.**

### F2 — `get_board` omitted claims (fixed during build)

The initial view returned a bare unit array. Extended to `{units, claims,
unit_count, claim_count}` so the Activity view can show claims without an
unbounded index. No security impact.

### F3 — empty contract-interface transfer primitive (verified, not a bug)

Confirmed via a sibling live project and `helix/contracts/host_vault.py` that the
plain EOA value transfer uses the `_Recipient` shim, and that
`gl.get_contract_at(...).emit_transfer` is for cross-contract calls. Using the
wrong form for an EOA payout would have been a silent no-op. Covered by the
direct `claim()` test.

## Residual risks — accepted, documented

- **Live happy path not exercised on-chain.** See `STATUS.md`. No live tx has
  moved money; verification is schema+constants+direct tests.
- **Timestamps.** Reliance on `datetime.now` for the 72h window is pinned to this
  `Depends` hash; see `SECURITY.md`.
- **`claim()` does not mark the claim `SETTLED`.** The claim record keeps its
  `APPROVED` status after payout (the ledger is what zeroes). Cosmetic only —
  `claim()` is idempotent via the ledger — but noted for honesty.
- **Validator-fetch honesty** is assumed, as in the standard GenLayer model.
- **`CLAIM_SETTLED` is defined but unused**; harmless dead constant.

## What is deliberately simple

No upgradeability, no admin key over the policy, no percentage awards, no
caller-proposed payout. The contract is small on purpose: fewer paths, each
tested.
