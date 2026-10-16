import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { fmtGen, submitWrite, toWei } from "../lib/chain";
import { useProtocolData } from "../lib/hooks";
import { ErrorNote, Loading, useApp } from "../components/Common";

export default function FileClaim() {
  const { unitId = "" } = useParams();
  const { account, refreshWallet } = useApp();
  const { config, board, loading, error, reload } = useProtocolData();
  const [narrative, setNarrative] = useState("");
  const [urlsText, setUrlsText] = useState("https://");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [fail, setFail] = useState("");
  const navigate = useNavigate();

  const unit = board?.units.find((u) => u.unit_id === unitId) ?? null;

  const parseUrls = () =>
    urlsText
      .split(/[\n,]/)
      .map((s) => s.trim())
      .filter(Boolean);

  const onSubmit = async () => {
    if (!account) {
      setFail("Connect a wallet first.");
      return;
    }
    const urls = parseUrls();
    if (!urls.length) {
      setFail("Provide at least one HTTPS evidence URL.");
      return;
    }
    setBusy(true);
    setMsg("");
    setFail("");
    try {
      const out = await submitWrite({
        method: "file_claim",
        args: [unitId, narrative, urls],
        value: toWei(fmtGen(config?.claim_bond ?? "0", 18)),
        account,
      });
      if (!out.ok) throw new Error(out.reason);
      setMsg("Claim filed.");
      reload();
      refreshWallet();
      setTimeout(() => navigate(`/app/u/${unitId}`), 900);
    } catch (err) {
      setFail(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  if (loading && !config) return <Loading />;
  if (error) return <ErrorNote error={error} />;
  if (!unit) {
    return (
      <section className="section">
        <ErrorNote error={`No unit ${unitId} in the recent board.`} />
        <Link to="/app">
          <button style={{ marginTop: 16 }}>Back to board</button>
        </Link>
      </section>
    );
  }

  return (
    <section className="section" style={{ marginTop: 8, maxWidth: 720 }}>
      <div className="section-head">
        <h2>File a claim</h2>
        <span className="count mono">{unit.unit_id}</span>
      </div>

      <div className="card">
        <div className="field">
          <label>Narrative</label>
          <textarea
            value={narrative}
            onChange={(e) => setNarrative(e.target.value)}
            placeholder="What happened, when, and how it breaches the policy."
          />
          <div className="hint">
            Plain text. This is fed to the adjudication prompt alongside the
            frozen policy.
          </div>
        </div>

        <div className="field">
          <label>Evidence URLs</label>
          <textarea
            value={urlsText}
            onChange={(e) => setUrlsText(e.target.value)}
            placeholder="https://status.example.com/incidents/2026-05-30"
          />
          <div className="hint">
            One HTTPS URL per line. Private, loopback and link-local addresses
            are refused before anything is fetched.
          </div>
        </div>

        <div className="kv">
          <dt>Bond (attached)</dt>
          <dd>{config ? `${fmtGen(config.claim_bond)} GEN` : "—"}</dd>
          <dt>Beneficiary</dt>
          <dd>{unit.beneficiary}</dd>
        </div>

        <div className="actions" style={{ marginTop: 18 }}>
          <button className="primary" disabled={busy} onClick={onSubmit}>
            {busy ? "Filing…" : "File claim"}
          </button>
          <Link to={`/app/u/${unitId}`}>
            <button>Cancel</button>
          </Link>
        </div>

        {(msg || fail) && (
          <p className={`note ${fail ? "bad" : "good"}`} style={{ marginTop: 14 }}>
            {fail || msg}
          </p>
        )}

        {account && account.toLowerCase() !== unit.beneficiary.toLowerCase() && (
          <p className="note bad" style={{ marginTop: 14 }}>
            Only the unit's beneficiary may file. The connected account does not
            match.
          </p>
        )}
      </div>
    </section>
  );
}
