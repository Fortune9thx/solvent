# SOLVENT

A single-issuer coverage bond on [GenLayer](https://genlayer.com). One issuer
capitalises a pool; beneficiaries enroll **discrete coverage units** against a
policy frozen at deployment. When a unit holder files a bonded claim, the
coverage question — *did this incident breach the frozen policy, under evidence
each validator fetches for itself over HTTPS?* — is settled by GenLayer
consensus, never by the issuer and never by the claimant.

- **Network:** GenLayer Studio Next / Studio Dev, chain **61997**
- **Live contract:** `0xE2FA3894A64c8D5D354BFC48588ab7A5c7f4D45D`
- **App:** https://solvent-fortune9thxs-projects.vercel.app
- **Explorer:** https://explorer-studio-dev.genlayer.com

Studio Next is a development network its operators can reset. If the contract
vanishes, `deploy/deployments.json` is stale and the app fails closed — it says
the contract is unreachable rather than showing invented data.

## The product law

Outcomes are **discrete only**: `FULL`, `HALF`, `NONE`, `INCONCLUSIVE`. There is
no `awarded_pct`, no claimant-proposed percentage, and nothing for a validator to
rubber-stamp. The payout schedule is a pure function of the decision:

| Decision | Beneficiary | Treasury | Unit |
|---|---|---|---|
| `FULL` | `face − fee + bond` | `fee` | closed (`CLAIMED_FULL`) |
| `HALF` | `face/2 − fee + bond` | `fee` | closed (`CLAIMED_HALF`) |
| `NONE` | `0` | `bond` (forfeited) | reopened |
| `INCONCLUSIVE` | `bond` (refunded) | `0` | reopened |

`fee = payout_gross * fee_bps / 10000`, strict integer division.

## The money invariant

```
pool_balance >= live_units * unit_face
```

Asserted after **every** mutation. Solvency is checked **before** a unit is
enrolled (never after exposure exists). Issuer withdrawals are floored at live
exposure. `claim()` is the one and only method that moves GEN out of the
contract, and it writes the ledger effect **before** the outbound transfer.

## How a claim resolves

1. **Enroll** — the issuer funds the pool; a unit is enrolled only if the pool
   already backs the new exposure.
2. **File** — a beneficiary files a bonded claim (narrative + HTTPS evidence
   URLs). Only the unit's holder may file; only one claim may be open per unit.
3. **Adjudicate** — anyone may push a claim forward; nobody can steer it. The
   single non-deterministic step. Every validator re-fetches the evidence,
   re-runs the prompt, canonicalizes its own verdict through the same pure code,
   and compares only `(decision, clause_ids, exclusion_ids, evidence_usable,
   code)`. Accounting runs only on the agreed envelope, re-parsed in
   deterministic code.
4. **Claim** — payout + bond are credited to the ledger; `claim()` moves them.

A claim that can never settle has two escape hatches: attempts are capped at 3,
and after 72h anyone may `cancel_stale_claim` to return the bond and free the
unit.

## Repository layout

```
contracts/Solvent.py                  the contract (source of truth)
contracts/solventlib/                 pure logic, zero genlayer imports
contracts/build_bundle.py             inlines solventlib -> the deployable file
contracts/build/Solvent.bundled.py    GENERATED — deployed; never hand-edited
tests/                                pure-logic tests
tests/direct/                         real GenVM direct-mode tests
deploy/                               probe · deploy · verify · deployments.json
frontend/                             Vite + React + TypeScript
docs/                                 STATUS · STEWARD · SECURITY · audit
```

## Commands

```bash
python contracts/build_bundle.py                 # regenerate the deployable bundle
python -m pytest tests -q -p no:gltest --ignore=tests/direct   # pure tests
python -m pytest tests/direct -q                 # real GenVM direct tests
genvm-lint lint contracts/build/Solvent.bundled.py
node deploy/probe_schema.mjs contracts/build/Solvent.bundled.py   # free pre-deploy check
node deploy/deploy.mjs                            # real deploy (funds-moving)
node deploy/verify.mjs                            # post-deploy verification (free)
npm --prefix frontend ci && npm --prefix frontend run build
```

## Status

`docs/STATUS.md` records exactly what was verified and when, including what was
**not** exercised. The honest summary: the contract is deployed, schema-verified,
and its full write/read surface passes 59 tests (30 pure + 29 real GenVM
direct-mode). The on-chain happy path (top-up → enroll → file → adjudicate →
claim) has **not** yet been driven on the live chain; that is stated as a
limitation, not implied to have passed.

## License

MIT.
