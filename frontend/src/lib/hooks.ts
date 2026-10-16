import { useCallback, useEffect, useState } from "react";
import {
  getClaimable,
  getConfig,
  getPolicy,
  getSolvency,
  loadBoard,
  type Board,
  type Config,
  type Policy,
  type Solvency,
} from "./chain";

export type ProtocolData = {
  config: Config | null;
  policy: Policy | null;
  solvency: Solvency | null;
  board: Board | null;
  loading: boolean;
  error: string;
  reload: () => void;
};

/**
 * Loads the whole read-only surface once. Every field starts null and stays
 * null on failure -- callers render empty/unknown states, never fixtures.
 */
export function useProtocolData(): ProtocolData {
  const [config, setConfig] = useState<Config | null>(null);
  const [policy, setPolicy] = useState<Policy | null>(null);
  const [solvency, setSolvency] = useState<Solvency | null>(null);
  const [board, setBoard] = useState<Board | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [nonce, setNonce] = useState(0);

  const reload = useCallback(() => setNonce((n) => n + 1), []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    Promise.all([getConfig(), getPolicy(), getSolvency(), loadBoard()])
      .then(([cfg, pol, sol, brd]) => {
        if (cancelled) return;
        setConfig(cfg);
        setPolicy(pol);
        setSolvency(sol);
        setBoard(brd);
      })
      .catch((err) => {
        if (cancelled) return;
        setConfig(null);
        setPolicy(null);
        setSolvency(null);
        setBoard(null);
        setError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [nonce]);

  return { config, policy, solvency, board, loading, error, reload };
}

/** The caller's own credited balance, refreshed on demand. */
export function useClaimable(account: string | null) {
  const [owed, setOwed] = useState<bigint | null>(null);
  const [error, setError] = useState("");
  const [nonce, setNonce] = useState(0);
  const reload = useCallback(() => setNonce((n) => n + 1), []);

  useEffect(() => {
    let cancelled = false;
    if (!account) {
      setOwed(null);
      return;
    }
    setError("");
    getClaimable(account)
      .then((v) => {
        if (!cancelled) setOwed(v);
      })
      .catch((err) => {
        if (!cancelled) {
          setOwed(null);
          setError(err instanceof Error ? err.message : String(err));
        }
      });
    return () => {
      cancelled = true;
    };
  }, [account, nonce]);

  return { owed, error, reload };
}
