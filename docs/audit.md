# Audit — self-review

Scope: `contracts/Solvent.py` + `contracts/solventlib/*` (the bundled deployable
file), the deploy tooling, and the frontend's read/write path. Method: source
review against the product law, the invariant, and the nondet boundary; the 59
tests; `genvm-lint`; a live schema/constant verification; and manual tracing of
every value-moving path. This is a self-audit, not an independent third party.
A later pass specifically cross-checked this build against the bug histories of
four sibling GenLayer builds (`non`, `datum`, `primacy`, `sentinel`) — that pass
is what surfaced F4.

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
`leader_fn` and compares strings. `gl.vm.run_nondet` hands the *validator* a
wrapper (`.calldata`), not the leader's raw value — the callback reads `.calldata`
and compares to its own re-derived string; the *call site* receives the bare value
and `json.loads`-es it. The agreed envelope is coerced to a dict, and the decision
is validated against `VALID_DECISIONS` (defaulting to `INCONCLUSIVE`). Storage is
re-loaded after the nondet call rather than trusting captured objects. Addresses
are normalized to lowercase hex at every write and lookup — including `claim()`,
where a case-mismatch bug (found by direct test `test_claim_pulls_once_then_nothing`)
had zeroed the ledger at a non-normalized key while crediting a lowercased one.
Fetched bodies pass through `normalize_fetch_content`, which decodes the SDK's
`bytes` body to text and marks non-200 responses, so the judge is only ever shown
sanitized page text or an explicit non-evidence marker.

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

### F4 — every on-chain fetch collapsed to empty (fixed; found by cross-checking siblings)

**Severity:** critical correctness — the product was non-functional on chain.
`gl.nondet.web.Response.body` is `bytes`, never `str` (documented in `non`'s
normalizer, same SDK generation). The leader passed `body` directly to
`sanitize_text()`, which returns `""` for any non-str, so every fetched page became
`[EMPTY_RESPONSE]` and the judge — seeing no evidence — would resolve every claim
`INCONCLUSIVE`. The suite did not catch it: `mock_llm` answers independently of
the prompt, and gltest's web mock even encodes a `str` body to `bytes` first, so
the mocked "happy path" passed on empty evidence. **Fix:** `normalize_fetch_content`
decodes bytes and marks non-200 responses; the leader uses it. Regression:
`test_web_text_flows_into_prompt` (mock LLM fires only if the page text is in the
prompt) plus pure tests over bytes/None/non-200. **Redeployed.**

### F5 — malformed approval slashed the claimant (fixed)

**Severity:** correctness / fairness. A `FULL`/`HALF` with no `clause_ids` was
forced to `NONE`, slashing the bond on what is an unsubstantiated model output.
Failing safe means failing toward `INCONCLUSIVE` (bond refunded). Now forces
`INCONCLUSIVE`/`INCOMPLETE_VERDICT`; a genuinely triggered exclusion still yields
`NONE`. Tests: `test_force_consistency_no_clause_breached_fails_safe_to_inconclusive`,
`test_force_consistency_exclusion_still_denies_even_without_clauses`.

### F6 — `validator_fn` was never executed (closed)

gltest's direct mode invokes only the leader during the normal call, so the
validator closure had no test: a validator that returned `False` for every honest
leader would have passed the whole suite while breaking consensus. Added
`TestValidatorIndependence`, which drives the real captured closure via
`direct_vm.run_validator()` and asserts it accepts an honest leader and rejects one
it cannot reproduce. This is the same gap that bit `non`.

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
