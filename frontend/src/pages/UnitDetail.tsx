import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { fmtGen, fmtTime, shortAddr, submitWrite, type ClaimRecord } from "../lib/chain";
import { useProtocolData } from "../lib/hooks";
import {
  ClaimStatusPill,
  DecisionPill,
  Empty,
  ErrorNote,
  Loading,
  useApp,
} from "../components/Common";

function Comparable({ c }: { c: ClaimRecord["comparable"] }) {
  if (!c || !c.decision) return null;
  return (
    <div className="card tight" style={{ marginTop: 12 }}>
      <span className="k" style={{ fontSize: 12, color: "var(--faint)" }}>
        COMPARABLE (consensus envelope)
      </span>
      <div className="kv" style={{ marginTop: 8 }}>
        <dt>decision</dt>
        <dd>{c.decision}</dd>
        <dt>clause_ids</dt>
        <dd>{(c.clause_ids ?? []).join(", ") || "—"}</dd>
        <dt>exclusion_ids</dt>
        <dd>{(c.exclusion_ids ?? []).join(", ") || "—"}</dd>
        <dt>evidence_usable</dt>
        <dd>{(c.evidence_usable ?? []).join(", ") || "—"}</dd>
        <dt>code</dt>
        <dd>{c.code || "—"}</dd>
      </div>
    </div>
  );
}

export default function UnitDetail() {
  const { unitId = "" } = useParams();
  const { account, refreshWallet } = useApp();
  const { board, config, loading, error, reload } = useProtocolData();
  const [busy, setBusy] = useState("");
  const [msg, setMsg] = useState("");
  const [fail, setFail] = useState("");

  const unit = board?.units.find((u) => u.unit_id === unitId) ?? null;
  const claims = (board?.claims ?? []).filter((c) => c.unit_id === unitId);

  const run = async (label: string, fn: () => Promise<void>) => {
    setBusy(label);
    setMsg("");
    setFail("");
    try {
      await fn();
      setMsg(label);
      reload();
      refreshWallet();
    } catch (err) {
      setFail(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy("");
    }
  };

  const act = (method: string, args: unknown[], ok: string) => () =>
    run(ok, async () => {
      if (!account) throw new Error("Connect a wallet first.");
      const out = await submitWrite({ method, args, account });
      if (!out.ok) throw new Error(out.reason);
    });

  if (loading && !board) return <Loading />;
  if (error) return <ErrorNote error={error} />;
  if (!unit) {
    return (
      <section className="section">
        <Empty>
          No unit <span className="mono">{unitId}</span> in the recent board.
        </Empty>
        <div className="actions" style={{ marginTop: 16 }}>
          <Link to="/app">
            <button>Back to board</button>
          </Link>
        </div>
      </section>
    );
  }

  const isBeneficiary = !!account && account.toLowerCase() === unit.beneficiary.toLowerCase();
  const canFile = unit.status === "ACTIVE" && !unit.open_claim_id && isBeneficiary;
  const canExpire = unit.status === "ACTIVE" && !unit.open_claim_id;

  return (
    <section className="section" style={{ marginTop: 8 }}>
      <div className="section-head">
        <h2 className="mono">{unit.unit_id}</h2>
        <span className="count">unit</span>
      </div>

      <div className="card">
        <div className="kv">
          <dt>Beneficiary</dt>
          <dd>{unit.beneficiary}</dd>
          <dt>Status</dt>
          <dd>
            {unit.status}
            {isBeneficiary ? " · you" : ""}
          </dd>
          <dt>Enrolled</dt>
          <dd>{fmtTime(unit.enrolled_at)}</dd>
          <dt>Policy hash</dt>
          <dd>{unit.policy_hash}</dd>
          <dt>Open claim</dt>
          <dd>{unit.open_claim_id || "—"}</dd>
        </div>

        <div className="actions" style={{ marginTop: 16 }}>
          {canFile && (
            <Link to={`/app/u/${unit.unit_id}/file`}>
              <button className="primary">File a claim</button>
            </Link>
          )}
          {canExpire && (
            <button disabled={!!busy} onClick={act("expire_unit", [unit.unit_id], "Unit expired.")}>
              Expire unit
            </button>
          )}
          {!account && <span className="note">Connect a wallet to act.</span>}
        </div>

        {(msg || fail) && (
          <p className={`note ${fail ? "bad" : "good"}`} style={{ marginTop: 12 }}>
            {fail || msg}
          </p>
        )}
      </div>

      <div className="section-head" style={{ marginTop: 30 }}>
        <h3>Claims on this unit</h3>
        <span className="count">{unit.claims_count} filed</span>
      </div>

      {claims.length === 0 && <Empty>No claims filed on this unit.</Empty>}

      {claims
        .slice()
        .reverse()
        .map((c) => (
          <div className="card" key={c.claim_id} style={{ marginBottom: 14 }}>
            <div className="actions" style={{ justifyContent: "space-between" }}>
              <span className="id mono">{c.claim_id}</span>
              <span className="actions">
                <ClaimStatusPill status={c.status} />
                <DecisionPill decision={c.decision} />
              </span>
            </div>
            <p className="note" style={{ marginTop: 10 }}>
              {c.narrative}
            </p>
            <div className="kv" style={{ marginTop: 10 }}>
              <dt>Bond</dt>
              <dd>{fmtGen(c.bond)} GEN</dd>
              <dt>Filed</dt>
              <dd>{fmtTime(c.filed_at)}</dd>
              <dt>Attempts</dt>
              <dd>
                {c.judge_attempts}
                {config ? ` / ${config.max_judge_attempts}` : ""}
              </dd>
              {c.urls?.length ? (
                <>
                  <dt>Evidence</dt>
                  <dd>
                    {c.urls.map((u) => (
                      <div key={u}>
                        <a href={u} target="_blank" rel="noreferrer">
                          {u}
                        </a>
                      </div>
                    ))}
                  </dd>
                </>
              ) : null}
            </div>

            <Comparable c={c.comparable} />

            <div className="actions" style={{ marginTop: 14 }}>
              {c.status === "OPEN" && (
                <button
                  className="primary"
                  disabled={!!busy}
                  onClick={act("adjudicate", [c.claim_id], "Claim adjudicated.")}
                >
                  {busy === "Claim adjudicated." ? "Adjudicating…" : "Adjudicate"}
                </button>
              )}
              {c.status === "OPEN" && (
                <button
                  disabled={!!busy}
                  title="Returns the bond and frees the unit once the claim is stale"
                  onClick={act("cancel_stale_claim", [c.claim_id], "Stale claim cancelled.")}
                >
                  Cancel if stale
                </button>
              )}
              {c.status === "APPROVED" && (
                <button
                  disabled={!!busy}
                  onClick={act("abandon_approved", [c.claim_id], "Claim abandoned.")}
                >
                  Abandon
                </button>
              )}
            </div>
          </div>
        ))}

      <div className="actions" style={{ marginTop: 20 }}>
        <Link to="/app">
          <button>Back to board</button>
        </Link>
        <span className="note">
          Beneficiary <span className="mono">{shortAddr(unit.beneficiary)}</span>
        </span>
      </div>
    </section>
  );
}
