#!/usr/bin/env node
/**
 * Post-deploy verification. Reads deploy/deployments.json and confirms, over
 * the RPC, that the address is a live contract and that its frozen constants
 * are what we expect. Free (no gas). Fails closed: any mismatch exits 1.
 */
import { createClient } from "genlayer-js";
import { studioDevnet } from "genlayer-js/chains";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const doc = JSON.parse(readFileSync(join(__dirname, "deployments.json"), "utf-8"));
const address = doc.studio_next?.address;
if (!address) {
  console.error("No address recorded in deploy/deployments.json");
  process.exit(1);
}

const client = createClient({ chain: studioDevnet });

console.log(`Verifying ${address} on chain ${studioDevnet.id}...`);
const schema = await client.getContractSchema(address);
const methodNames = Object.keys(schema?.methods ?? {});
console.log(`Schema OK: ${methodNames.length} methods`);
console.log(methodNames.sort().join(", "));

for (const [fn, expect] of [
  ["get_config", null],
  ["get_policy", null],
  ["get_solvency", null],
  ["get_board", null],
]) {
  const raw = await client.readContract({ address, functionName: fn, args: [] });
  const parsed = JSON.parse(String(raw));
  console.log(`\n${fn}:`);
  console.log(JSON.stringify(parsed, null, 2));
  if (expect) console.log(`expected: ${JSON.stringify(expect)}`);
}

const cfg = JSON.parse(String(await client.readContract({ address, functionName: "get_config", args: [] })));
const checks = [
  [cfg.unit_face === "100000000000000000000", `unit_face == 100 GEN (got ${cfg.unit_face})`],
  [cfg.max_units === "5", `max_units == 5 (got ${cfg.max_units})`],
  [cfg.claim_bond === "5000000000000000000", `claim_bond == 5 GEN (got ${cfg.claim_bond})`],
  [cfg.fee_bps === 500, `fee_bps == 500 (got ${cfg.fee_bps})`],
  [cfg.max_judge_attempts === 3, `max_judge_attempts == 3 (got ${cfg.max_judge_attempts})`],
  [cfg.expiry_window_seconds === 259200, `expiry_window_seconds == 259200 (got ${cfg.expiry_window_seconds})`],
  [cfg.treasury.toLowerCase() === "0xc6e6d3b2accaececeb40ad4bd3df123ddcb4e537", `treasury (got ${cfg.treasury})`],
  [Array.isArray(cfg.decisions) && cfg.decisions.length === 4, `4 discrete decisions (got ${JSON.stringify(cfg.decisions)})`],
];

let ok = true;
console.log("\nChecks:");
for (const [pass, label] of checks) {
  console.log(`  ${pass ? "PASS" : "FAIL"}  ${label}`);
  if (!pass) ok = false;
}

if (!ok) {
  console.error("\nVerification FAILED.");
  process.exit(1);
}
console.log("\nVerification PASSED.");
