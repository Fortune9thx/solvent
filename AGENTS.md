# Working notes

Single-issuer coverage bond on GenLayer. Read this before changing anything.

## Commit rules — not negotiable

- Author is **`Fortunex9 <fortuneemx@gmail.com>`**, sole-authored.
- **No co-author trailer, no AI attribution, no session links** — not in commit
  messages, not in PR bodies, not in docs, not in code comments.

## Source of truth

- `contracts/Solvent.py` + `contracts/solventlib/*` are the sources.
- `contracts/build/Solvent.bundled.py` is **generated** — never hand-edit it.
  Regenerate with `python contracts/build_bundle.py`.
- `deploy/deployments.json` is the **only** place the live address lives.

## Verify before believing anything

```bash
python contracts/build_bundle.py
genvm-lint lint contracts/build/Solvent.bundled.py
python -m pytest tests -q -p no:gltest --ignore=tests/direct
python -m pytest tests/direct -q
node deploy/probe_schema.mjs contracts/build/Solvent.bundled.py
node deploy/verify.mjs
npm --prefix frontend run build
```

## Traps that have already cost real time

1. **Never use `eth_getCode` as a liveness probe.** A healthy GenLayer IC returns
   `0x`. Use `gen_getContractSchema` (schema when live, `-32001` when absent).
2. **The `genlayer` CLI has no 61997 preset** (its `studionet` is 61999). Always
   pass `--rpc https://studio-dev.genlayer.com/api`. `genlayer-js`'s
   `studioDevnet` *is* 61997.
3. **Fees:** a zero/partial distribution fails client-side with
   `FeeValueMustBeNonZero(1)` (reads like a revert). `deploy/deploy.mjs` passes a
   complete distribution; keep it.
4. **Constructor args:** numeric args are decimal strings; the policy is
   multi-word. Drive the CLI's JS entry with an argv array (no shell) — see
   `deploy/deploy.mjs`.
5. **Unit tests need `-p no:gltest`** when `genlayer-test` is installed, or its
   pytest plugin blocks collection validating `gltest.config.yaml`.
6. **`tests/direct` needs the pinned GenVM runner cached.** It runs where the
   runner is present; from a cold checkout the runner asset may not download.
   CI marks that job `continue-on-error`.
7. **`VITE_*` is inlined at build time.** Changing `VITE_CONTRACT_ADDRESS` on
   Vercel does nothing until a redeploy. Confirm the address is in the deployed
   JS bundle before believing the app.
8. **Sanitizers must attack delimiters, not words.** An over-broad filter turned
   `independently` into `indep ently` on a live deploy (see `docs/audit.md` F1).
