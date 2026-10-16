import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { fmtGen, submitWrite } from "../lib/chain";
import { useProtocolData } from "../lib/hooks";
import { ErrorNote, Loading, useApp } from "../components/Common";

export default function Enroll() {
  const { account, isLive, refreshWallet } = useApp();
  const { config, solvency, loading, error, reload } = useProtocolData();
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [fail, setFail] = useState("");
  const navigate = useNavigate();

  const canBack = solvency
    ? BigInt(solvency.withdrawable) >= 0n &&
      BigInt(solvency.pool_balance) >= BigInt(solvency.unit_face)
    : false;
  const atCap = config ? BigInt(config.unit_count) >= BigInt(config.max_units) : false;

  const onEnroll = async () => {
    if (!account) {
      setFail("Connect a wallet first.");
      return;
    }
    setBusy(true);
    setMsg("");
    setFail("");
    try {
      const out = await submitWrite({ method: "enroll_unit", args: [], account });
      if (!out.ok) throw new Error(out.reason);
      setMsg("Unit enrolled.");
      reload();
      refreshWallet();
      setTimeout(() => navigate("/app"), 900);
    } catch (err) {
      setFail(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="section" style={{ marginTop: 8, maxWidth: 720 }}>
      <div className="section-head">
        <h2>Enroll a coverage unit</h2>
      </div>

      {error && <ErrorNote error={error} />}
      {loading && !config && <Loading />}

      {config && solvency && (
        <>
          <div className="card">
            <div className="kv">
              <dt>You receive</dt>
              <dd>1 unit · {fmtGen(config.unit_face)} GEN face</dd>
              <dt>Your address</dt>
              <dd>{account ?? "not connected"}</dd>
              <dt>Unit cap</dt>
              <dd>
                {config.unit_count} / {config.max_units}
              </dd>
              <dt>Pool backing</dt>
              <dd>
                {fmtGen(solvency.pool_balance)} GEN against{" "}
                {fmtGen(solvency.exposure)} GEN exposure
              </dd>
            </div>
          </div>

          {atCap && <p className="note bad" style={{ marginTop: 14 }}>The unit cap is already reached.</p>}
          {!canBack && !atCap && (
            <p className="note bad" style={{ marginTop: 14 }}>
              The pool cannot back another unit right now. It needs more
              capital before the exposure can be created.
            </p>
          )}
          {canBack && !atCap && (
            <p className="note" style={{ marginTop: 14 }}>
              Enrolling adds {fmtGen(config.unit_face)} GEN of live exposure.
              The pool already covers it, so the solvency invariant holds before
              the unit exists.
            </p>
          )}

          <div className="actions" style={{ marginTop: 18 }}>
            <button
              className="primary"
              disabled={busy || !isLive || !account || atCap || !canBack}
              onClick={onEnroll}
            >
              {busy ? "Enrolling…" : "Enroll unit"}
            </button>
            <Link to="/app">
              <button>Cancel</button>
            </Link>
          </div>

          {(msg || fail) && (
            <p className={`note ${fail ? "bad" : "good"}`} style={{ marginTop: 14 }}>
              {fail || msg}
            </p>
          )}

          <div className="divider" />
          <p className="note">
            Coverage is against the policy frozen at deployment. Claims are
            filed with a bond and settled by validators, not the issuer.
          </p>
        </>
      )}
    </section>
  );
}
