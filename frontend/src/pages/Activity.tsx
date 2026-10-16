import { Link } from "react-router-dom";
import { fmtGen, fmtTime, shortAddr } from "../lib/chain";
import { useProtocolData } from "../lib/hooks";
import {
  ClaimStatusPill,
  DecisionPill,
  Empty,
  ErrorNote,
  Loading,
  useApp,
} from "../components/Common";

export default function Activity() {
  const { isLive } = useApp();
  const { board, loading, error } = useProtocolData();
  const claims = (board?.claims ?? []).slice().reverse();

  return (
    <section className="section" style={{ marginTop: 8 }}>
      <div className="section-head">
        <h2>Activity</h2>
        <span className="count">{board ? `${board.claim_count} claims filed` : ""}</span>
      </div>

      {error && <ErrorNote error={error} />}
      {loading && !board && <Loading />}
      {!loading && !error && claims.length === 0 && isLive && (
        <Empty>No claims have been filed yet.</Empty>
      )}
      {!isLive && !loading && <Empty>The protocol is not reachable.</Empty>}

      {claims.map((c) => (
        <Link key={c.claim_id} to={`/app/u/${c.unit_id}`}>
          <div className="row">
            <div>
              <div className="id">{c.claim_id}</div>
              <div className="sub mono">
                {c.unit_id} · {shortAddr(c.beneficiary)}
              </div>
            </div>
            <ClaimStatusPill status={c.status} />
            <DecisionPill decision={c.decision} />
            <div className="sub">
              {fmtGen(c.bond)} GEN · {fmtTime(c.filed_at)}
            </div>
          </div>
        </Link>
      ))}
    </section>
  );
}
