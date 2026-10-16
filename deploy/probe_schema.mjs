#!/usr/bin/env node
/**
 * FREE, no-gas pre-deploy check: client.getContractSchemaForCode(code)
 * fails instantly and deterministically if the network cannot resolve this
 * contract's runner / Depends hash right now -- cheaper and faster than
 * finding out via a real, gas-costing deploy attempt. Run this BEFORE any
 * real deployContract() call, for both a minimal probe and the real bundle.
 *
 * Usage: node deploy/probe_schema.mjs <path-to-contract.py>
 */
import { createClient } from "genlayer-js";
import { studioDevnet } from "genlayer-js/chains";
import { readFileSync } from "node:fs";

const path = process.argv[2];
if (!path) {
  console.error("usage: node deploy/probe_schema.mjs <path-to-contract.py>");
  process.exit(1);
}

const code = readFileSync(path, "utf-8");
const client = createClient({ chain: studioDevnet });

console.log(`Probing getContractSchemaForCode for ${path} (${code.length} bytes) on chain ${studioDevnet.id}...`);
try {
  const schema = await client.getContractSchemaForCode(code);
  const methods = schema?.methods ?? schema?.abi ?? schema;
  console.log("OK -- schema resolved.");
  console.log(JSON.stringify(schema, null, 2));
  void methods;
} catch (err) {
  console.error("FAILED:", err?.message ?? err);
  process.exit(1);
}
