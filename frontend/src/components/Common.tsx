import { useEffect, useState, type ReactNode } from "react";
import { useOutletContext } from "react-router-dom";
import {
  CHAIN_ID,
  CONTRACT_ADDRESS,
  EXPLORER,
  NETWORK_LABEL,
  explorerAddress,
  shortAddr,
  type Decision,
  type Liveness,
} from "../lib/chain";
import type { AppContext } from "./AppShell";

export function useApp(): AppContext {
  return useOutletContext<AppContext>();
}

/* -------------------------------------------------------------------------
   Decision + status pills
   ------------------------------------------------------------------------- */

const DECISION_CLASS: Record<string, string> = {
  FULL: "full",
  HALF: "half",
  NONE: "none",
  INCONCLUSIVE: "inconclusive",
};

export function DecisionPill({ decision }: { decision: Decision | string }) {
  if (!decision) return <span className="pill inconclusive">undecided</span>;
  return <span className={`pill ${DECISION_CLASS[decision] ?? "inconclusive"}`}>{decision}</span>;
}

const UNIT_CLASS: Record<string, string> = {
  ACTIVE: "active",
  CLAIMED_FULL: "full",
  CLAIMED_HALF: "half",
  EXPIRED: "inconclusive",
};

export function UnitStatusPill({ status }: { status: string }) {
  return (
    <span className={`pill ${UNIT_CLASS[status] ?? "inconclusive"}`}>
      {(status || "—").replace(/_/g, " ").toLowerCase()}
    </span>
  );
}

const CLAIM_CLASS: Record<string, string> = {
  OPEN: "active",
  APPROVED: "full",
  DENIED: "none",
  INCONCLUSIVE: "inconclusive",
  SETTLED: "full",
  CANCELLED: "inconclusive",
  ABANDONED: "half",
};

export function ClaimStatusPill({ status }: { status: string }) {
  return (
    <span className={`pill ${CLAIM_CLASS[status] ?? "inconclusive"}`}>
      {(status || "—").replace(/_/g, " ").toLowerCase()}
    </span>
  );
}

/* -------------------------------------------------------------------------
   Network chip
   ------------------------------------------------------------------------- */

export function NetworkChip({ liveness }: { liveness: Liveness }) {
  const cls =
    liveness.kind === "live"
      ? "pill active"
      : liveness.kind === "rpc-down"
      ? "pill none"
      : "pill half";
  return (
    <span className={cls} style={{ marginRight: 12 }}>
      {NETWORK_LABEL} · {CHAIN_ID}
    </span>
  );
}

/* -------------------------------------------------------------------------
   Liveness banner.

   These states are the ONLY thing standing between a visitor and a
   confident-looking screen full of nothing. Each one says plainly which is
   true and what it means. A live contract renders nothing here.
   ------------------------------------------------------------------------- */

export function LivenessBanner({ liveness }: { liveness: Liveness }) {
  if (liveness.kind === "live" || liveness.kind === "checking") return null;

  if (liveness.kind === "undeployed") {
    return (
      <div className="banner warn">
        <span className="dot" />
        <div>
          <strong>Not deployed.</strong> No contract address is configured, so
          there is nothing to read. Every panel below is empty because the
          protocol has no state yet — not because the state is zero.
        </div>
      </div>
    );
  }

  if (liveness.kind === "no-code") {
    return (
      <div className="banner warn">
        <span className="dot" />
        <div>
          <strong>Nothing deployed at this address.</strong>{" "}
          <span className="mono">{shortAddr(liveness.address)}</span> returns no
          contract schema. {NETWORK_LABEL} state can be reset by the operators;
          when that happens the protocol must be redeployed and this address
          updated.
        </div>
      </div>
    );
  }

  return (
    <div className="banner bad">
      <span className="dot" />
      <div>
        <strong>Cannot reach the network.</strong> The {NETWORK_LABEL} RPC did
        not answer ({liveness.detail}). Nothing is shown rather than something
        stale.
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------
   Empty / loading / error states
   ------------------------------------------------------------------------- */

export function Empty({ children }: { children: ReactNode }) {
  return <div className="empty">{children}</div>;
}

export function Loading({ label = "Reading chain" }: { label?: string }) {
  return (
    <div className="empty">
      <span className="spinner" /> {label}…
    </div>
  );
}

export function ErrorNote({ error }: { error: string }) {
  return (
    <div className="banner bad">
      <span className="dot" />
      <div>
        <strong>Read failed.</strong> {error}
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------
   Footer
   ------------------------------------------------------------------------- */

export function Footer() {
  return (
    <footer className="shell">
      <div className="divider" />
      <div className="foot">
        <span>
          SOLVENT settles one question: does an incident breach the frozen
          policy, on evidence each validator fetches for itself?
        </span>
        <span className="spacer" />
        {CONTRACT_ADDRESS ? (
          <a className="mono" href={explorerAddress(CONTRACT_ADDRESS)} target="_blank" rel="noreferrer">
            {shortAddr(CONTRACT_ADDRESS)}
          </a>
        ) : (
          <span>not deployed</span>
        )}
        <a href={EXPLORER} target="_blank" rel="noreferrer">
          Explorer
        </a>
        <span>MIT</span>
      </div>
    </footer>
  );
}

/* -------------------------------------------------------------------------
   Copy-to-clipboard mono value
   ------------------------------------------------------------------------- */

export function Copyable({ value, short }: { value: string; short?: boolean }) {
  const [done, setDone] = useState(false);
  useEffect(() => {
    if (!done) return;
    const t = setTimeout(() => setDone(false), 1200);
    return () => clearTimeout(t);
  }, [done]);
  if (!value) return <span className="note">—</span>;
  return (
    <button
      className="mono"
      title={value}
      onClick={() => {
        navigator.clipboard?.writeText(value).then(
          () => setDone(true),
          () => undefined
        );
      }}
      style={{ background: "none", border: 0, padding: 0, font: "inherit", color: "inherit" }}
    >
      {done ? "copied" : short ? shortAddr(value) : value}
    </button>
  );
}
