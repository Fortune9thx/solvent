# STEWARD

How to operate SOLVENT without corrupting it or losing funds.

## Ground rules

- `contracts/build/Solvent.bundled.py` is **generated**. Never hand-edit it. Edit
  `contracts/Solvent.py` or `contracts/solventlib/*.py`, then run
  `python contracts/build_bundle.py`.
- `deploy/deployments.json` is the **single source of truth** for the live
  address. Never hardcode an address elsewhere.
- The constructor's `unit_face`, `max_units`, `claim_bond`, `fee_bps` and the
  `policy_text` are **frozen at deployment**. Changing the policy means a new
  deployment and a new `policy_hash`; existing units are bound to the old hash.

## Redeploy after a source change

```bash
python contracts/build_bundle.py
genvm-lint lint contracts/build/Solvent.bundled.py
python -m pytest tests -q -p no:gltest --ignore=tests/direct
python -m pytest tests/direct -q
node deploy/probe_schema.mjs contracts/build/Solvent.bundled.py   # free, no gas
node deploy/deploy.mjs                                            # real, funds-moving
node deploy/verify.mjs                                            # free
```

`deploy.mjs` drives the `genlayer` CLI's own JS entry with an argv array (no
shell), because the policy is a multi-word string and the numeric args must
arrive as strings. It supplies a **complete, non-zero fee distribution** —
consensus v0.6 rejects a zero/missing distribution with
`FeeValueMustBeNonZero(1)` **client-side**, before broadcast, though the message
reads like an on-chain revert. The distribution in the script is the proven one;
do not replace it with a bare `estimateTransactionFees()` call without
re-verifying against a real successful deploy.

Note: the `genlayer` CLI has **no 61997 preset** (its `studionet` is 61999, one
digit away). Always pass `--rpc https://studio-dev.genlayer.com/api` explicitly.
The 61997 preset lives in `genlayer-js`'s `studioDevnet`, which the deploy/verify
scripts use.

## Operating the pool

1. **Fund** — `top_up_pool` is payable; the attached value is added to the pool.
   The caller need not be the issuer; the issuer is whoever deployed.
2. **Enroll** — call `enroll_unit`. It reverts if the pool does not already back
   the new exposure, or if `max_units` is reached. Adds `unit_face` of exposure.
3. **Withdraw** — `withdraw_pool(amount)` is issuer-only and floored at
   `live_units * unit_face`. It credits the issuer's ledger balance; the GEN
   leaves the contract only via `claim()`.
4. **Claim** — `claim()` pays the caller their whole credited balance and zeroes
   the ledger **before** the outbound transfer.

## Handling claims

- Only the unit's beneficiary may `file_claim`, only while the unit is `ACTIVE`
  and has no open claim. The attached value becomes the bond.
- `adjudicate(claim_id)` is **permissionless** — anyone may pay the gas to move a
  claim forward; nobody can influence the result.
- If a claim cannot converge, `cancel_stale_claim` returns the bond and frees the
  unit once attempts are exhausted (3) or 72h have elapsed since filing.

## If the network is reset

Studio Next can be reset by its operators. If `gen_getContractSchema` returns
`-32001` ("not found") for the address, the contract is gone. Redeploy, then
update `deploy/deployments.json` and the app's `VITE_CONTRACT_ADDRESS`, and
**redeploy the frontend with the build cache disabled** — `VITE_*` values are
inlined at build time.

## Commit rules

- Author is **`Fortunex9 <fortuneemx@gmail.com>`**, sole-authored.
- No co-author trailer, no AI attribution, no session links — not in commits, not
  in docs, not in code comments.
