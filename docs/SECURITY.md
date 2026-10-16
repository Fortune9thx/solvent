# SECURITY

SOLVENT's security rests on four properties, each enforced in code and covered
by tests. This file states them, the trust assumptions, and what is explicitly
**not** defended.

## 1. The solvency invariant

```
pool_balance >= live_units * unit_face
```

`verify_solvency_invariant` is pure integer math (no floats). `_assert_solvent()`
runs after every mutation. Enrollment checks solvency **before** creating the new
exposure, so an insolvent unit can never exist even transiently. Issuer
withdrawal is capped at `max_withdrawable = pool_balance − live_units * unit_face`.

## 2. One outbound path

`claim()` is the only method that transfers value out. It:

1. reads the caller's credited balance,
2. **writes the ledger to zero first**, then
3. emits the transfer.

Order matters: a re-entrant or failed transfer cannot observe a non-zero balance
twice. The transfer uses an empty `@gl.evm.contract_interface` shim
(`_Recipient(addr).emit_transfer(value=...)`) — the documented primitive for a
plain native value transfer to an EOA. (`gl.get_contract_at(addr).emit_transfer`
is for cross-contract *method calls*, not plain value transfers.)

## 3. SSRF hardening on evidence

Filing is where an attacker controls input that the adjudicator will fetch.
`validate_url` enforces, before any fetch:

- **scheme** must be `https`, port must be `443` (or absent);
- **no credentials** in the URL;
- **length** ≤ 512, and no whitespace/control characters;
- **host** must be a valid DNS name with an alphabetic TLD, *or* a canonical
  4-part decimal IPv4;
- **blocked hosts/suffixes**: `localhost`, `.local`, `.internal`, `.arpa`,
  `.lan`, `.test`, `.example`, `.invalid`, `metadata.google.internal`,
  `instance-data`;
- **blocked IP ranges**: loopback, private, link-local, multicast, reserved,
  unspecified, CGNAT (`100.64.0.0/10`), and `0.0.0.0/8`;
- **IPv6 literals are rejected outright**, as are non-canonical/octal IPv4 forms.

URLs are canonicalized (`https://host/path?query`) and de-duplicated. At most 5
URLs, and fetch content is truncated to 4000 chars. URLs are validated **twice**:
once at filing (rejecting bad input) and again inside the non-deterministic
leader before each fetch (so a saved record can never be fetched unchecked).

## 4. Deterministic re-derivation across validators

`adjudicate` contains the one non-deterministic step. The leader fetches each
URL and runs the LLM prompt; then `canonicalize_for_comparison` reduces the
result to exactly five fields:

```
decision, clause_ids, exclusion_ids, evidence_usable, code
```

The validator independently re-fetches, re-runs the prompt, and re-derives its
own canonical envelope — then compares the two. `force_consistency` normalizes
before comparison and enforces the product law:

- no usable evidence ⇒ `INCONCLUSIVE`;
- `FULL`/`HALF` with any triggered exclusion ⇒ `NONE`;
- `FULL`/`HALF` with no breached clause ⇒ `INCONCLUSIVE` (a malformed approval
  fails safe and refunds the bond; it never slashes the claimant on an
  unsubstantiated model output).

Accounting is applied **only** to the agreed envelope, re-parsed in deterministic
code — a non-deterministic value is never trusted to move money directly.

## Prompt-injection posture

Untrusted text (policy, narrative, fetched evidence) is wrapped between fixed
markers (`[[POLICY_START]] … [[POLICY_END]]`, `[[EVIDENCE_n_START]] …`) and the
sanitizer strips only **delimiter-impersonation tokens** — backtick fences and
`[[`/`]]`/`<<<`/`>>>` sequences — so content cannot fabricate a wrapper marker.

An earlier version additionally stripped the literal words `BEGIN`/`END` and any
`---`, which corrupted legitimate prose (`independently` → `indep ently`) and
silently changed the policy hash. That was a real defect, fixed and regression
tested. The lesson recorded here: sanitizers must attack the *delimiters*, not
ordinary words.

## Trust assumptions and limits

- **Timestamps.** `_now_ts()` uses `datetime.now(timezone.utc)` inside a
  transaction. On this `Depends` pin that is deterministic and accepted by the
  linter; the stale-claim window relies on it. If a future pin makes wall-clock
  reads non-deterministic, the 72h escape hatch must be reworked.
- **LLM output is non-deterministic.** The design tolerates this by comparing
  only the canonical envelope and by forcing consistency; it does not promise a
  specific verdict from specific text.
- **Validator honesty.** The model assumes validators fetch independently as
  specified. The comparison only constrains the five canonical fields; it cannot
  prove an honest fetch. This is the standard GenLayer trust model.
- **No access control on `adjudicate`/`cancel_stale_claim`** — by design. They
  are permissionless; neither can change who is owed or how much.
- **`abandon_approved`** is a bookkeeping hatch; it does not revoke the ledger
  credits already granted, which remain claimable via `claim()`.
- **Studio Next may be reset.** The contract can vanish; the app fails closed.
