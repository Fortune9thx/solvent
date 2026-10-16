import { Link } from "react-router-dom";
import { CHAIN_ID, CONTRACT_ADDRESS, EXPLORER, NETWORK_LABEL, shortAddr } from "../lib/chain";

const OUTCOMES = [
  {
    k: "FULL",
    cls: "full",
    d: "The incident breached the frozen policy on usable evidence. Face value is paid to the beneficiary, less the protocol fee.",
  },
  {
    k: "HALF",
    cls: "half",
    d: "The breach is partial or the evidence speaks to only part of the claim. Half face value is paid, less the protocol fee.",
  },
  {
    k: "NONE",
    cls: "none",
    d: "The claim does not hold, or a named exclusion applies. No payout; the claim bond is forfeited to the treasury.",
  },
  {
    k: "INCONCLUSIVE",
    cls: "inconclusive",
    d: "No usable evidence, or the clause and exclusion readings cannot be reconciled. No payout; the bond is returned exactly.",
  },
];

export default function Landing() {
  return (
    <>
      <header className="topbar">
        <div className="topbar-inner">
          <span className="brand">
            <span className="mark" />
            SOLVENT
          </span>
          <div className="spacer" />
          <Link to="/app" className="pill plain">
            Enter app →
          </Link>
        </div>
      </header>

      <main className="shell">
        <section className="hero">
          <h1>
            Coverage that <span className="accent">holds</span> when the terms
            are tested.
          </h1>
          <p className="lede">
            One issuer capitalises a pool. Beneficiaries enroll discrete
            coverage units against a policy frozen at deployment. When a claim
            is filed, GenLayer validators each fetch the evidence for
            themselves and settle the question — never the issuer, never the
            claimant.
          </p>
          <div className="actions" style={{ marginTop: 26 }}>
            <Link to="/app">
              <button className="primary">Open the board</button>
            </Link>
            <Link to="/app/enroll">
              <button>Enroll a unit</button>
            </Link>
          </div>
        </section>

        <section className="section">
          <h2>Four outcomes. No percentages.</h2>
          <p className="lede" style={{ marginTop: 4 }}>
            The payout is a pure function of the decision. There is no awarded
            share and no claimant-proposed figure for a validator to rubber
            stamp.
          </p>
          <div className="grid cols-2" style={{ marginTop: 18 }}>
            {OUTCOMES.map((o) => (
              <div className="card" key={o.k}>
                <span className={`pill ${o.cls}`}>{o.k}</span>
                <p>{o.d}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="section">
          <h2>How a claim resolves</h2>
          <div className="steps" style={{ marginTop: 16 }}>
            <div className="step">
              <div className="n">01 · ENROLL</div>
              <p className="note">
                The issuer funds the pool. The pool must already cover each new
                unit before it can be enrolled — the invariant is checked
                before exposure exists, not after.
              </p>
            </div>
            <div className="step">
              <div className="n">02 · FILE</div>
              <p className="note">
                A beneficiary files a bonded claim with a narrative and HTTPS
                evidence URLs. Only the unit's holder may file, and only one
                claim may be open on a unit at a time.
              </p>
            </div>
            <div className="step">
              <div className="n">03 · ADJUDICATE</div>
              <p className="note">
                Anyone may push the claim forward; nobody can steer it. Each
                validator re-fetches the same pages and re-derives its own
                verdict, then compares only a canonical envelope.
              </p>
            </div>
            <div className="step">
              <div className="n">04 · CLAIM</div>
              <p className="note">
                Payout plus bond are credited to the ledger. Withdrawal is the
                one and only outbound path, and it writes the effect before it
                moves value.
              </p>
            </div>
          </div>
        </section>

        <section className="section">
          <div className="card">
            <h2>The money invariant</h2>
            <p className="note" style={{ marginTop: 8, fontFamily: "var(--mono)" }}>
              pool_balance &ge; live_units &times; unit_face
            </p>
            <p className="note" style={{ marginTop: 10 }}>
              Asserted after every mutation. Solvency is checked before a unit
              is enrolled, issuer withdrawals are floored at live exposure, and
              a claim that can never settle releases its bond after 72h or once
              its attempts are exhausted.
            </p>
          </div>
        </section>

        <section className="section">
          <div className="facts">
            <div className="fact">
              <div className="v">{NETWORK_LABEL}</div>
              <div className="k">network · chain {CHAIN_ID}</div>
            </div>
            <div className="fact">
              <div className="v">{CONTRACT_ADDRESS ? shortAddr(CONTRACT_ADDRESS) : "—"}</div>
              <div className="k">contract</div>
            </div>
            <div className="fact">
              <div className="v">72h</div>
              <div className="k">stale-claim window</div>
            </div>
            <div className="fact">
              <div className="v">3</div>
              <div className="k">max adjudication attempts</div>
            </div>
          </div>
          <p className="note" style={{ marginTop: 18 }}>
            {NETWORK_LABEL} is a development network its operators can reset.
            If the contract vanishes, the app says so and shows nothing rather
            than something stale.
          </p>
        </section>

        <div className="divider" />
        <div className="foot">
          <span>Single-issuer coverage bond on GenLayer.</span>
          <span className="spacer" />
          <a href={EXPLORER} target="_blank" rel="noreferrer">
            Explorer
          </a>
          <span>MIT</span>
        </div>
      </main>
    </>
  );
}
