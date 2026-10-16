@echo off
REM Deploy SOLVENT to GenLayer Studio Next (chain 61997) via the unlocked
REM `bradbury-deploy` keystore. The CLI has no 61997 preset, so --rpc is
REM passed explicitly. Every constructor argument is quoted so the CLI treats
REM it as a string (the ctor's ABI is all-string; large wei values have no
REM integer JSON type).
REM
REM Run `node deploy/probe_schema.mjs contracts/build/Solvent.bundled.py`
REM (free, no gas) before this. This is a real, funds-moving action.
genlayer deploy ^
  --contract contracts/build/Solvent.bundled.py ^
  --rpc https://studio-dev.genlayer.com/api ^
  --fee-preset standard ^
  --args "0xC6E6d3b2acCaECeCeB40Ad4bD3dF123DDCB4e537" "Coverage is owed when the beneficiary proves, from independently fetched HTTPS evidence, that the named service breached its published availability target. Force majeure and scheduled maintenance are excluded." "100000000000000000000" "5" "5000000000000000000" "500"
