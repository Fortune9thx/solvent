#!/usr/bin/env node
/**
 * Deploy contracts/build/Solvent.bundled.py to GenLayer Studio Next (chain
 * 61997) through the `genlayer` CLI, using the CLI's unlocked `bradbury-deploy`
 * keystore. On success it records the address in deploy/deployments.json.
 *
 * Why we drive the CLI's JS entry directly instead of shelling out:
 *   1. The constructor's policy_text is a multi-word string and the numeric
 *      args must arrive as strings. A spawn with an argv array (no shell)
 *      delivers them verbatim, with no quoting ambiguity.
 *   2. Consensus v0.6 rejects a zero/missing fee distribution with
 *      FeeValueMustBeNonZero(1) CLIENT-SIDE -- before broadcast, though the
 *      error text reads like an on-chain revert. The fee object below is the
 *      proven, complete distribution (see docs/architecture notes); passing
 *      it as JSON through a shell is exactly the kind of quoting that breaks.
 *
 * Run `node deploy/probe_schema.mjs contracts/build/Solvent.bundled.py`
 * (free, no gas) first. This script is a real, funds-moving action.
 */
import { spawnSync } from "node:child_process";
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = join(__dirname, "..");
const CONTRACT_PATH = join(REPO_ROOT, "contracts", "build", "Solvent.bundled.py");
const DEPLOYMENTS_PATH = join(__dirname, "deployments.json");

const CLI =
  process.env.GENLAYER_CLI ??
  "C:/Users/HP/nodejs/node_modules/genlayer/dist/index.js";
const RPC = "https://studio-dev.genlayer.com/api";

const TREASURY = "0xC6E6d3b2acCaECeCeB40Ad4bD3dF123DDCB4e537";
const POLICY_TEXT =
  "Coverage is owed when the beneficiary proves, from independently fetched " +
  "HTTPS evidence, that the named service breached its published availability " +
  "target. Force majeure and scheduled maintenance are excluded.";
const UNIT_FACE = "100000000000000000000"; // 100 GEN
const MAX_UNITS = "5";
const CLAIM_BOND = "5000000000000000000"; // 5 GEN
const FEE_BPS = "500"; // 5%

// Complete, non-zero fee distribution for consensus v0.6. A bare or partial
// distribution fails client-side with FeeValueMustBeNonZero(1).
const FEES = {
  distribution: {
    rotations: [0],
    appealRounds: 0,
    totalMessageFees: 0,
    executionConsumed: 0,
    receiptFeeMaxGasPrice: "300000000",
    storageFeeMaxGasPrice: "300000000",
    maxPriceGenPerTimeUnit: "2",
    executionBudgetPerRound: "94643100000000",
    leaderTimeunitsAllocation: "100",
    validatorTimeunitsAllocation: "200",
  },
  feeValue: "94643100002588",
};

if (!existsSync(CONTRACT_PATH)) {
  console.error(`${CONTRACT_PATH} not found -- run "python contracts/build_bundle.py" first`);
  process.exit(1);
}

const args = [
  CLI,
  "deploy",
  "--contract",
  CONTRACT_PATH,
  "--rpc",
  RPC,
  "--fees",
  JSON.stringify(FEES),
  "--args",
  TREASURY,
  POLICY_TEXT,
  UNIT_FACE,
  MAX_UNITS,
  CLAIM_BOND,
  FEE_BPS,
];

console.log("Deploying SOLVENT to Studio Next (chain 61997)...");
console.log(`Treasury: ${TREASURY}`);
const proc = spawnSync(process.execPath, args, { encoding: "utf-8" });
const out = (proc.stdout ?? "") + (proc.stderr ?? "");
console.log(out);

if (proc.status !== 0) {
  console.error(`genlayer CLI exited with status ${proc.status}`);
  process.exit(proc.status ?? 1);
}

// The CLI echoes the args (including the treasury address) before the result,
// so prefer an explicit "deploy"/"contract" mention; fall back to the last
// 40-hex address in the output.
const matches = [...out.matchAll(/0x[0-9a-fA-F]{40}/g)].map((m) => m[0]);
const labelled =
  out.match(/deployed(?:\s+at| to)?\s*:?\s*(0x[0-9a-fA-F]{40})/i)?.[1] ??
  out.match(/contract(?:\s+address)?\s*:?\s*(0x[0-9a-fA-F]{40})/i)?.[1];
const address = labelled ?? matches[matches.length - 1];
const txHash = out.match(/Transaction Hash'?:?\s*'?(0x[0-9a-fA-F]{64})/i)?.[1] ?? "";

if (!address) {
  console.error("Could not read the deployed contract address from the CLI output.");
  process.exit(1);
}

console.log(`\nDeployed at: ${address}`);

const doc = existsSync(DEPLOYMENTS_PATH)
  ? JSON.parse(readFileSync(DEPLOYMENTS_PATH, "utf-8"))
  : { studio_next: { superseded: [] } };
doc.studio_next.address = address;
doc.studio_next.deploy_tx = txHash;
doc.studio_next.treasury = TREASURY;
doc.studio_next.deployed_at = new Date().toISOString();
writeFileSync(DEPLOYMENTS_PATH, JSON.stringify(doc, null, 2) + "\n");
console.log(`Wrote ${DEPLOYMENTS_PATH}`);
