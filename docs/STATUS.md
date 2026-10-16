# STATUS

What was actually verified, and when. If something was not run, it says so here
rather than implying coverage. Keep it honest.

_Last updated: 2026-10-16._

## Live

- **Contract:** `0xff361d7458553fD82434B170c2A0E074aB9e4C7c` on GenLayer Studio
  Next (chain 61997).
- **Deploy tx:** `0x7d97a278e9710ab70fa25d778df695f8c4f06202b5e54206c3a2c9456581de6d`
  (consensus `ACCEPTED`, `FINISHED_WITH_RETURN`).
- **Bundle:** `contracts/build/Solvent.bundled.py`, 26 296 bytes,
  sha256 `82a4d16889261f96c3875939cd75248c0b1d8317a88b34061001fb23b43e0e5a`.
- **App:** https://solvent-fortune9thxs-projects.vercel.app (public;
  Deployment Protection SSO disabled). The deployed JS bundle was confirmed to
  contain the address above, so `VITE_CONTRACT_ADDRESS` was inlined at build.

## Verified

| Check | Result |
|---|---|
| `genvm-lint lint contracts/build/Solvent.bundled.py` | PASS (3 checks) |
| `genvm-lint check` on the bundle | PASS — Contract `Solvent`, 16 methods (7 view, 9 write) |
| `node deploy/probe_schema.mjs` (free) | PASS — schema + runner/Depends resolve on 61997 |
| `node deploy/verify.mjs` (free) | PASS — 16 methods; all frozen constants match; policy text intact |
| `node deploy/smoke.mjs` (live write, bounded) | PASS — see below |
| `python -m pytest tests` (pure) | 26 passed |
| `python -m pytest tests/direct` (real GenVM) | 23 passed |
| `npm --prefix frontend run build` | PASS (tsc + vite) |

### What the direct tests actually exercise

The 23 direct-mode tests deploy the **real bundle** into a GenVM sandbox and
drive: deploy + config + policy hash; solvency at enrollment; `MAX_UNITS`;
bond floor; beneficiary-only filing; one-open-claim; URL/SSRF and narrative
validation; `FULL`/`HALF`/`NONE`/`INCONCLUSIVE` accounting and pool conservation;
force-consistency (empty evidence ⇒ `INCONCLUSIVE`; exclusion ⇒ `NONE`);
`claim()` single-draw then `NOTHING_TO_CLAIM`; the 72h stale-cancel path via
`direct_vm.warp`; the withdraw floor; and `expire_unit`.

They run **where the pinned GenVM runner is cached**. On this machine the runner
resolved, so all 23 executed and passed. From a cold machine the direct suite may
be unable to fetch the runner asset; that is upstream, not a defect here. Do not
downgrade the claim to "only the pure tests ran" in an environment where the
direct suite was not attempted — run it and report what happened.

## NOT verified — state this plainly

- **No live on-chain happy path.** The full sequence top-up → enroll → file →
  adjudicate → claim has **not** been driven against the deployed address. It is
  covered by direct-mode tests, not by a live transaction. No units or claims
  exist on the live contract (`get_board` is empty; `pool_balance` is 0).

### What WAS driven live (bounded)

The `genlayer` CLI's `write` has no option to attach a payable `value`, and the
deploy signer is a keystore (no raw key in this environment), so the payable
steps (`top_up_pool`, `file_claim`) could not be sent from this tooling. A
non-payable write whose guard must fire *was* driven:

- `enroll_unit` on the empty pool (tx
  `0xfa767cfc199d2109dec4efe5a6aa913bfb73d88050b6c9bcd3c679640aa8d72c`,
  earlier `0x6e367d02c1904f1def254e85e78ddde9f2c06fa8b76d26a86eefa6c811afbf61`)
  was **decided `ACCEPTED` with leader execution `FINISHED_WITH_ERROR`** — the
  deployed bytecode executes writes, and its solvency precondition refused to
  create exposure the pool does not back. This is the only live write performed.

Note: `genlayer trace` is unavailable on this RPC (`gen_dbg_traceTransaction`
is not exposed), so the exact error string was not read back from a trace; the
refusal is evidenced by the `FINISHED_WITH_ERROR` write result.

- **Not exercised live anywhere:** `top_up_pool`, `file_claim`, `adjudicate`
  (the nondet path), `cancel_stale_claim`, `abandon_approved`, `expire_unit`,
  `withdraw_pool`, and `claim`'s outbound transfer.
- **The EOA transfer primitive** (`_Recipient(...).emit_transfer`) is proven by
  direct-mode `claim()` tests and by the same pattern in sibling live projects,
  but no live payout has been performed from this address.
- **Frontend** was built and deployed, and the address was confirmed inlined;
  it has not been exercised end-to-end against the live contract in a wallet
  session.

## A real defect found and fixed during this build

The first deployment (`0xB7fc34F974a64DD216b010212c7Dc970814aA148`) succeeded and
passed schema checks, but its **frozen policy text was corrupted**: the
`sanitize_text` prompt-injection filter replaced the literal word `END`
case-insensitively, turning `independently` into `indep ently` — which also
changed `policy_hash`. The filter was narrowed to strip only
delimiter-impersonation tokens (bracket/fence sequences), a regression test was
added (`test_sanitize_text_preserves_ordinary_words`), and the contract was
redeployed to the current address. The superseded address and reason are recorded
in `deploy/deployments.json`.

## Toolchain

- Python 3.12.10, pytest 9.1.1, genvm-linter 0.11.1rc2
- gltest / genlayer-test 0.30.0rc2, genlayer-py 0.19.0rc2
- genlayer-js 2.0.0-rc.1, Node v22.16.0
- Deploy signer: unlocked `bradbury-deploy` keystore (never printed).
