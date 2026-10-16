import { useState } from "react";
import { Link } from "react-router-dom";
import { fmtGen, shortAddr, submitWrite, fmtTime, toWei } from "../lib/chain";
import { useClaimable, useProtocolData } from "../lib/hooks";
import {
  ClaimStatusPill,
  DecisionPill,
  Empty,
  ErrorNote,
  Loading,
  UnitStatusPill,
  useApp,
} from "../components/Common";

export default function Board() {
  const { isLive, account, refreshWallet } = useApp();
  const { config, solvency, board, loading, error, reload } = useProtocolData();
  const { owed, reload: reloadOwed } = useClaimable(account);
  const [topUp, setTopUp] = useState("10");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [fail, setFail] = useState("");

  const run = async (label: string, fn: () => Promise<void>) => {
    setBusy(true);
    setMsg("");
    setFail("");
    try {
      await fn();
      setMsg(label);
      reload();
      reloadOwed();
      refreshWallet();
    } catch (err) {
      setFail(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const onTopUp = () =>
    run("Pool topped up.", async () => {
      if (!account) throw new Error("Connect a wallet first.");
      const value = toWei(topUp);
      const out = await submitWrite({ method: "top_up_pool", args: [], value, account });
      if (!out.ok) throw new Error(out.reason);
    });

  const onClaim = () =>
    run("Payout claimed.", async () => {
      if (!account) throw new Error("Connect a wallet first.");
      const out = await submitWrite({ method: "claim", args: [], account });
      if (!out.ok) throw new Error(out.reason);
    });

  const units = board?.units ?? [];
  const claims = board?.claims ?? [];

  return (
    <>
      <section className="section" style={{ marginTop: 8 }}>
        <div className="section-head">
          <h2>Pool</h2>
          <span className="count">frozen policy · discrete outcomes only</span>
        </div>

        {error && <ErrorNote error={error} />}

        <div className="grid cols-4">
          <div className="card tight stat">
            <span className="k">Pool balance</span>
            <span className="v">{solvency ? `${fmtGen(solvency.pool_balance)} GEN` : "—"}</span>
          </div>
          <div className="card tight stat">
            <span className="k">Live exposure</span>
            <span className="v">{solvency ? `${fmtGen(solvency.exposure)} GEN` : "—"}</span>
          </div>
          <div className="card tight stat">
            <span className="k">Live units</span>
            <span className="v">{solvency ? solvency.live_units : "—"}</span>
          </div>
          <div className="card tight stat">
            <span className="k">Solvent</span>
            <span className="v small" style={{ color: solvency?.is_solvent ? "var(--full)" : "var(--none)" }}>
              {solvency ? (solvency.is_solvent ? "invariant holds" : "BROKEN") : "—"}
            </span>
          </div>
        </div>

        {config && (
          <div className="card" style={{ marginTop: 16 }}>
            <div className="kv">
              <dt>Unit face</dt>
              <dd>{fmtGen(config.unit_face)} GEN</dd>
              <dt>Claim bond</dt>
              <dd>{fmtGen(config.claim_bond)} GEN</dd>
              <dt>Max units</dt>
              <dd>{config.max_units}</dd>
              <dt>Protocol fee</dt>
              <dd>{(config.fee_bps / 100).toFixed(2)}%</dd>
              <dt>Policy hash</dt>
              <dd>{config.policy_hash}</dd>
            </div>
          </div>
        )}

        {account && (
          <div className="card" style={{ marginTop: 16 }}>
            <div className="actions">
              <div className="stat" style={{ flex: 1 }}>
                <span className="k">Your claimable</span>
                <span className="v">{owed === null ? "—" : `${fmtGen(owed)} GEN`}</span>
              </div>
              <button className="primary" disabled={busy || !owed || owed <= 0n} onClick={onClaim}>
                Claim
              </button>
              <input
                className="mono"
                style={{ maxWidth: 120 }}
                value={topUp}
                onChange={(e) => setTopUp(e.target.value)}
                aria-label="Top-up amount in GEN"
              />
              <button disabled={busy} onClick={onTopUp}>
                Top up pool
              </button>
            </div>
          </div>
        )}

        {(msg || fail) && (
          <p className={`note ${fail ? "bad" : "good"}`} style={{ marginTop: 12 }}>
            {fail || msg}
          </p>
        )}
      </section>

      <section className="section">
        <div className="section-head">
          <h2>Units</h2>
          <span className="count">{board ? `${board.unit_count} enrolled` : ""}</span>
          <div className="spacer" />
          {account && (
            <Link to="/app/enroll">
              <button>Enroll a unit</button>
            </Link>
          )}
        </div>

        {loading && !board && <Loading />}
        {!loading && isLive && units.length === 0 && !error && (
          <Empty>
            No units enrolled yet. The pool has no exposure.{" "}
            {account ? "Enroll the first unit." : "Connect a wallet to enroll."}
          </Empty>
        )}
        {!isLive && !loading && (
          <Empty>The protocol is not reachable, so the board is empty.</Empty>
        )}

        {units
          .slice()
          .reverse()
          .map((u) => (
            <Link key={u.unit_id} to={`/app/u/${u.unit_id}`}>
              <div className="row">
                <div>
                  <div className="id">{u.unit_id}</div>
                  <div className="sub mono">{shortAddr(u.beneficiary)}</div>
                </div>
                <UnitStatusPill status={u.status} />
                <div className="sub">{fmtTime(u.enrolled_at)}</div>
                <div className="sub">{u.open_claim_id ? "claim open" : "—"}</div>
              </div>
            </Link>
          ))}
      </section>

      <section className="section">
        <div className="section-head">
          <h2>Recent claims</h2>
          <span className="count">{board ? `${board.claim_count} filed` : ""}</span>
        </div>
        {!loading && claims.length === 0 && !error && (
          <Empty>No claims filed yet.</Empty>
        )}
        {claims
          .slice()
          .reverse()
          .map((c) => (
            <div className="row" key={c.claim_id}>
              <div>
                <div className="id">{c.claim_id}</div>
                <div className="sub mono">{c.unit_id}</div>
              </div>
              <ClaimStatusPill status={c.status} />
              <DecisionPill decision={c.decision} />
              <div className="sub">{fmtTime(c.filed_at)}</div>
            </div>
          ))}
      </section>
    </>
  );
}
