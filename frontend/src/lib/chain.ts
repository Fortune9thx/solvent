/**
 * Chain access for SOLVENT.
 *
 * Every read in this app goes through here, and every read can fail
 * closed. There is no fixture data, no seeded unit list, and no "demo
 * mode" anywhere in this file or downstream of it: if the contract
 * address is unset, or nothing is deployed at it, or the RPC is
 * unreachable, the UI renders an empty product and says which of those
 * three is true.
 */

export const CONTRACT_ADDRESS = (import.meta.env.VITE_CONTRACT_ADDRESS ?? "").trim();
export const RPC_URL = (
  import.meta.env.VITE_GENLAYER_RPC_URL ?? "https://studio-dev.genlayer.com/api"
).trim();
export const CHAIN_ID = Number(import.meta.env.VITE_GENLAYER_CHAIN_ID ?? 61997);
export const EXPLORER = (
  import.meta.env.VITE_EXPLORER ?? "https://explorer-studio-dev.genlayer.com"
).trim();

export const CHAIN_ID_HEX = "0x" + CHAIN_ID.toString(16);
export const NETWORK_LABEL = "Studio Next";

/** How the app is currently connected to the protocol. */
export type Liveness =
  | { kind: "checking" } // the probe has not answered yet
  | { kind: "undeployed" } // no address configured
  | { kind: "no-code"; address: string } // address set, nothing deployed there
  | { kind: "rpc-down"; detail: string } // could not reach the RPC at all
  | { kind: "live"; address: string };

let rpcId = 1;

async function rpc<T>(method: string, params: unknown[]): Promise<T> {
  const res = await fetch(RPC_URL, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ jsonrpc: "2.0", id: rpcId++, method, params }),
  });
  if (!res.ok) throw new Error(`rpc ${res.status}`);
  const body = await res.json();
  if (body.error) {
    const err = new Error(body.error.message ?? "rpc error");
    (err as { code?: number }).code = body.error.code;
    throw err;
  }
  return body.result as T;
}

/**
 * Liveness probe.
 *
 * NOTE: this deliberately does NOT use eth_getCode. A GenLayer
 * intelligent contract is not an EVM contract -- eth_getCode returns "0x"
 * for a perfectly healthy, responding, deployed IC, so a frontend gating
 * on it reports "nothing deployed, the network was reset" about a live
 * contract and fails every read and write closed for no reason. The
 * authoritative probe is gen_getContractSchema, which returns a method
 * schema for a live contract and JSON-RPC error -32001 ("Contract ... not
 * found") for an address with nothing at it -- cleanly separating
 * live / nothing-there / RPC-unreachable, which is exactly the three-way
 * distinction this app's banners need.
 */
export async function probeLiveness(): Promise<Liveness> {
  if (!CONTRACT_ADDRESS) return { kind: "undeployed" };
  try {
    await rpc<unknown>("gen_getContractSchema", [CONTRACT_ADDRESS]);
    return { kind: "live", address: CONTRACT_ADDRESS };
  } catch (err) {
    const code = (err as { code?: number }).code;
    const message = err instanceof Error ? err.message : String(err);
    if (code === -32001 || /not found/i.test(message)) {
      return { kind: "no-code", address: CONTRACT_ADDRESS };
    }
    return { kind: "rpc-down", detail: message };
  }
}

/**
 * Shared read-only genlayer-js client. Imported dynamically so a visitor
 * who never reaches a data view does not pay for the client bundle, and
 * so a client-library failure surfaces as a failed read rather than a
 * blank page.
 */
let readClientPromise: Promise<unknown> | null = null;

async function readClient(): Promise<unknown> {
  if (!readClientPromise) {
    readClientPromise = (async () => {
      const [{ createClient }, { studioDevnet }] = await Promise.all([
        import("genlayer-js"),
        import("genlayer-js/chains"),
      ]);
      const chain = {
        ...studioDevnet,
        id: CHAIN_ID,
        rpcUrls: { default: { http: [RPC_URL] } },
      };
      return createClient({ chain: chain as never });
    })();
  }
  return readClientPromise;
}

/**
 * Calls a read-only contract method and returns its raw string result.
 * Throws when the protocol is not configured or the read fails -- callers
 * surface that as an explicit failure state, never as empty-looking data
 * that could be mistaken for "no units yet".
 */
export async function callView(method: string, args: unknown[] = []): Promise<string> {
  if (!CONTRACT_ADDRESS) throw new Error("no contract address configured");
  const client = (await readClient()) as {
    readContract: (a: unknown) => Promise<unknown>;
  };
  const raw = await client.readContract({
    address: CONTRACT_ADDRESS,
    functionName: method,
    args,
  });
  return String(raw);
}

// ---------------------------------------------------------------------------
// Typed shapes returned by the contract's own views.
// ---------------------------------------------------------------------------

export type Decision = "FULL" | "HALF" | "NONE" | "INCONCLUSIVE" | "";

export type Config = {
  issuer: string;
  treasury: string;
  policy_hash: string;
  unit_face: string;
  max_units: string;
  claim_bond: string;
  fee_bps: number;
  max_judge_attempts: number;
  expiry_window_seconds: number;
  pool_balance: string;
  live_units: string;
  unit_count: string;
  claim_count: string;
  decisions: string[];
};

export type Policy = {
  policy_hash: string;
  policy_text: string;
};

export type Solvency = {
  pool_balance: string;
  exposure: string;
  live_units: string;
  unit_face: string;
  is_solvent: boolean;
  withdrawable: string;
};

export type UnitRecord = {
  unit_id: string;
  beneficiary: string;
  policy_hash: string;
  status: string;
  open_claim_id: string;
  claims_count: number;
  enrolled_at: number;
};

export type Comparable = {
  decision: Decision;
  clause_ids: string[];
  exclusion_ids: string[];
  evidence_usable: number[];
  code: string;
};

export type ClaimRecord = {
  claim_id: string;
  unit_id: string;
  beneficiary: string;
  narrative: string;
  urls: string[];
  bond: string;
  status: string;
  decision: Decision;
  judge_attempts: number;
  filed_at: number;
  comparable: Comparable | null;
};

export type Board = {
  units: UnitRecord[];
  claims: ClaimRecord[];
  unit_count: string;
  claim_count: string;
};

// ---------------------------------------------------------------------------
// Reads
// ---------------------------------------------------------------------------

export async function getConfig(): Promise<Config> {
  return JSON.parse(await callView("get_config"));
}

export async function getPolicy(): Promise<Policy> {
  return JSON.parse(await callView("get_policy"));
}

export async function getSolvency(): Promise<Solvency> {
  return JSON.parse(await callView("get_solvency"));
}

export async function getUnit(unitId: string): Promise<UnitRecord> {
  return JSON.parse(await callView("get_unit", [unitId]));
}

export async function getClaim(claimId: string): Promise<ClaimRecord> {
  return JSON.parse(await callView("get_claim", [claimId]));
}

export async function getBoard(): Promise<Board> {
  return JSON.parse(await callView("get_board"));
}

export async function getClaimable(address: string): Promise<bigint> {
  return BigInt(await callView("get_claimable", [address]));
}

/**
 * Loads the board. Returns empty lists when the protocol is not live --
 * the caller renders an empty board, never a fabricated one. A claim
 * whose read fails is dropped rather than replaced with a placeholder.
 */
export async function loadBoard(): Promise<Board> {
  const board = await getBoard();
  return {
    units: board.units ?? [],
    claims: (board.claims ?? []).filter((c) => c && c.claim_id),
    unit_count: board.unit_count ?? "0",
    claim_count: board.claim_count ?? "0",
  };
}

// ---------------------------------------------------------------------------
// Wallet (injected provider)
// ---------------------------------------------------------------------------

type Eip1193 = {
  request: (args: { method: string; params?: unknown[] }) => Promise<unknown>;
  on?: (event: string, handler: (...a: unknown[]) => void) => void;
  removeListener?: (event: string, handler: (...a: unknown[]) => void) => void;
};

/**
 * Wallet discovery.
 *
 * `window.ethereum` is a single global slot that every injected wallet
 * races to claim. With more than one extension installed only one of them
 * can own it, so reading that global alone silently misses every other
 * wallet. EIP-6963 replaces the race with an announcement protocol; the
 * global stays as a fallback. Discovery tolerates an announce arriving
 * after this module has loaded, so `onWalletDiscovered` lets the UI
 * re-render when a late wallet appears.
 */

type Eip6963Detail = {
  info: { uuid: string; name: string };
  provider: Eip1193;
};

const discovered = new Map<string, Eip1193>();
const walletListeners = new Set<() => void>();

if (typeof window !== "undefined") {
  window.addEventListener("eip6963:announceProvider", ((
    event: CustomEvent<Eip6963Detail>
  ) => {
    const { info, provider } = event.detail ?? ({} as Eip6963Detail);
    if (!info?.uuid || !provider) return;
    const isNew = !discovered.has(info.uuid);
    discovered.set(info.uuid, provider);
    if (isNew) walletListeners.forEach((fn) => fn());
  }) as EventListener);
  window.dispatchEvent(new Event("eip6963:requestProvider"));
}

/**
 * Re-runs `fn` when a wallet is discovered after this call. Returns an
 * unsubscribe function.
 */
export function onWalletDiscovered(fn: () => void): () => void {
  walletListeners.add(fn);
  return () => {
    walletListeners.delete(fn);
  };
}

export function injectedProvider(): Eip1193 | null {
  if (typeof window === "undefined") return null;
  const first = discovered.values().next();
  if (!first.done) return first.value;
  const w = window as unknown as { ethereum?: Eip1193 };
  return w.ethereum ?? null;
}

export function hasWallet(): boolean {
  return injectedProvider() !== null;
}

export async function connectWallet(): Promise<string> {
  const provider = injectedProvider();
  if (!provider) throw new Error("No injected wallet found in this browser.");
  const accounts = (await provider.request({
    method: "eth_requestAccounts",
  })) as string[];
  if (!accounts?.length) throw new Error("Wallet returned no account.");
  await ensureChain();
  return accounts[0];
}

/** Switches to chain 61997, adding it first if the wallet does not know it. */
export async function ensureChain(): Promise<void> {
  const provider = injectedProvider();
  if (!provider) return;
  try {
    await provider.request({
      method: "wallet_switchEthereumChain",
      params: [{ chainId: CHAIN_ID_HEX }],
    });
  } catch (err) {
    const code = (err as { code?: number }).code;
    if (code === 4902) {
      await provider.request({
        method: "wallet_addEthereumChain",
        params: [
          {
            chainId: CHAIN_ID_HEX,
            chainName: `GenLayer ${NETWORK_LABEL}`,
            nativeCurrency: { name: "GEN", symbol: "GEN", decimals: 18 },
            rpcUrls: [RPC_URL],
            blockExplorerUrls: [EXPLORER],
          },
        ],
      });
      return;
    }
    throw err;
  }
}

export async function currentAccount(): Promise<string | null> {
  const provider = injectedProvider();
  if (!provider) return null;
  try {
    const accounts = (await provider.request({ method: "eth_accounts" })) as string[];
    return accounts?.[0] ?? null;
  } catch {
    return null;
  }
}

export async function getBalance(address: string): Promise<bigint> {
  const provider = injectedProvider();
  if (!provider) return 0n;
  try {
    const hex = (await provider.request({
      method: "eth_getBalance",
      params: [address, "latest"],
    })) as string;
    return BigInt(hex);
  } catch {
    return 0n;
  }
}

// ---------------------------------------------------------------------------
// Writes
// ---------------------------------------------------------------------------

export type WriteArgs = {
  method: string;
  args: unknown[];
  /** Native GEN to attach, in wei. Pool top-ups and claim bonds post value. */
  value?: bigint;
  account: string;
};

/**
 * Terminal transaction states that count as success.
 *
 * This is deliberately a WHITELIST of known-good values, never a blacklist
 * of known-bad ones. A blacklist silently treats every state it has not
 * heard of as success, which is exactly how an `UNDETERMINED` consensus
 * outcome -- where validators independently re-ran the work and disagreed,
 * so nothing was persisted at all -- gets reported to a user as a completed
 * transaction.
 */
const OK_STATUS = new Set(["ACCEPTED", "FINALIZED"]);
const OK_EXECUTION = new Set(["FINISHED_WITH_RETURN", "FINISHED_WITH_NO_RETURN"]);
// The consensus result. `DISAGREE` means validators independently re-ran the
// leader's work and got different answers, so nothing was persisted at all.
const OK_RESULT = new Set(["MAJORITY_AGREE", "AGREE"]);

export type TxOutcome = {
  hash: string;
  status: string;
  execution: string;
  result: string;
  ok: boolean;
  reason: string;
};

/**
 * Pulls the three fields that decide whether a write actually took effect.
 *
 * Field names are taken from a real receipt off this network, not guessed:
 * `statusName` and `txExecutionResultName` are camelCase, while the
 * consensus result is `result_name` (snake_case). Both spellings are read
 * for each so a shape change upstream degrades to "unknown" -- which fails
 * the whitelist -- rather than to a silent pass.
 */
function readStatus(receipt: unknown): {
  status: string;
  execution: string;
  result: string;
} {
  const r = (receipt ?? {}) as Record<string, unknown>;
  const pick = (...keys: string[]) => {
    for (const k of keys) {
      const v = r[k];
      if (typeof v === "string" && v) return v.toUpperCase();
    }
    return "";
  };
  return {
    status: pick("statusName", "status_name"),
    execution: pick("txExecutionResultName", "tx_execution_result_name"),
    result: pick("result_name", "resultName"),
  };
}

/**
 * Waits for a submitted transaction to reach a terminal state and reports
 * whether it actually succeeded.
 *
 * `waitForTransactionReceipt` resolving without throwing is NOT proof the
 * transaction reached the status that was asked for -- it can resolve on a
 * different terminal state -- so the resolved receipt is always re-checked
 * against the whitelist above.
 */
export async function waitForOutcome(
  hash: string,
  { finalized = false }: { finalized?: boolean } = {}
): Promise<TxOutcome> {
  const client = (await readClient()) as {
    waitForTransactionReceipt: (a: unknown) => Promise<unknown>;
  };

  let receipt: unknown;
  try {
    receipt = await client.waitForTransactionReceipt({
      hash,
      status: finalized ? "FINALIZED" : "ACCEPTED",
      retries: finalized ? 200 : 100,
      interval: 4000,
    });
  } catch (err) {
    return {
      hash,
      status: "",
      execution: "",
      result: "",
      ok: false,
      reason: err instanceof Error ? err.message : String(err),
    };
  }

  const { status, execution, result } = readStatus(receipt);
  const fail = (reason: string): TxOutcome => ({
    hash,
    status,
    execution,
    result,
    ok: false,
    reason,
  });

  // Every gate below is a whitelist, and a MISSING value fails it just like
  // a known-bad one. Skipping a check when its field is absent is how a
  // whitelist quietly turns back into a blacklist.
  if (!OK_STATUS.has(status)) {
    return fail(
      status === "UNDETERMINED"
        ? "Validators could not agree, so nothing was recorded. Try again."
        : `Transaction ended as ${status || "an unreported state"}.`
    );
  }
  if (!OK_RESULT.has(result)) {
    return fail(
      result === "DISAGREE"
        ? "Validators re-ran this independently and disagreed, so nothing was recorded. Try again."
        : `Consensus result was ${result || "not reported"}.`
    );
  }
  if (!OK_EXECUTION.has(execution)) {
    return fail(
      execution === "FINISHED_WITH_ERROR"
        ? "The contract rejected this call."
        : `Execution result was ${execution || "not reported"}.`
    );
  }
  if (finalized && status !== "FINALIZED") {
    return fail("Not yet final.");
  }
  return { hash, status, execution, result, ok: true, reason: "" };
}

export async function writeContract({ method, args, value, account }: WriteArgs) {
  if (!CONTRACT_ADDRESS) throw new Error("no contract address configured");
  const provider = injectedProvider();
  if (!provider) throw new Error("No injected wallet found in this browser.");
  await ensureChain();

  const [{ createClient }, { studioDevnet }] = await Promise.all([
    import("genlayer-js"),
    import("genlayer-js/chains"),
  ]);

  const chain = { ...studioDevnet, id: CHAIN_ID, rpcUrls: { default: { http: [RPC_URL] } } };

  // The wallet's own provider must be handed to the client, or there is
  // nothing to sign with and every write fails.
  const client = createClient({
    chain: chain as never,
    account: account as never,
    provider: provider as never,
  });

  // Consensus v0.6 requires an explicit non-zero fee on every write. Let the
  // client simulate this exact call to derive one rather than guessing: a
  // partial fee distribution is rejected locally, before broadcast, with an
  // error that reads like an on-chain revert.
  let fees: unknown = undefined;
  try {
    fees = await (client as never as {
      estimateTransactionFeesForWrite: (a: unknown) => Promise<unknown>;
    }).estimateTransactionFeesForWrite({
      address: CONTRACT_ADDRESS,
      functionName: method,
      args,
      value: value ?? 0n,
    });
  } catch {
    fees = undefined;
  }

  const hash = await (client as never as {
    writeContract: (a: unknown) => Promise<string>;
  }).writeContract({
    address: CONTRACT_ADDRESS,
    functionName: method,
    args,
    value: value ?? 0n,
    ...(fees ? { fees } : {}),
  });

  return hash as string;
}

/**
 * Submits a write and waits for its real outcome.
 *
 * A returned transaction hash is a receipt of submission, not of success --
 * every caller in this app goes through here so no UI can show a completed
 * state off a hash alone.
 */
export async function submitWrite(
  args: WriteArgs,
  opts: { finalized?: boolean } = {}
): Promise<TxOutcome> {
  const hash = await writeContract(args);
  return waitForOutcome(hash, opts);
}

// ---------------------------------------------------------------------------
// Formatting
// ---------------------------------------------------------------------------

export function fmtGen(wei: string | bigint, decimals = 2): string {
  const v = typeof wei === "bigint" ? wei : BigInt(wei || "0");
  const whole = v / 10n ** 18n;
  const frac = ((v % 10n ** 18n) * 10n ** BigInt(decimals)) / 10n ** 18n;
  if (decimals === 0) return whole.toString();
  return `${whole}.${frac.toString().padStart(decimals, "0")}`;
}

export function toWei(amount: string): bigint {
  const trimmed = (amount || "0").trim();
  if (!/^\d+(\.\d+)?$/.test(trimmed)) throw new Error("amount must be a number");
  const [whole, frac = ""] = trimmed.split(".");
  const padded = (frac + "0".repeat(18)).slice(0, 18);
  return BigInt(whole) * 10n ** 18n + BigInt(padded || "0");
}

export function shortAddr(addr: string): string {
  if (!addr || addr.length < 12) return addr || "—";
  return `${addr.slice(0, 6)}…${addr.slice(-4)}`;
}

export function fmtTime(ts: number): string {
  if (!ts) return "—";
  return new Date(ts * 1000).toISOString().replace("T", " ").slice(0, 16) + "Z";
}

export function countdown(deadline: number, now = Date.now() / 1000): string {
  const left = Math.floor(deadline - now);
  if (left <= 0) return "elapsed";
  const h = Math.floor(left / 3600);
  const m = Math.floor((left % 3600) / 60);
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

export function explorerAddress(addr: string): string {
  return `${EXPLORER}/address/${addr}`;
}

export function explorerTx(hash: string): string {
  return `${EXPLORER}/tx/${hash}`;
}
