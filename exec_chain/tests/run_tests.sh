#!/usr/bin/env bash
# Copyright (c) 2026 Michael Wroblewski - Apache-2.0
# EXEC-CHAIN-Testrunner (ATC-95-Testmigration, atc-contracts#5):
#   .atc-Testvertrag + Vektor -> EXEC-CHAIN-Assembler -> .ops -> ATVM-Ausfuehrung
# Evidenz: Exit 0 = alle Tests PASS, Exit 1 = mind. ein FAIL (fail-closed).
#
# Nutzung:
#   ATC_VM_RUNNER=/pfad/zum/atc-vm-runner ./exec_chain/tests/run_tests.sh
set -u
BASE="$(cd "$(dirname "$0")" && pwd)"
VM_RUNNER="${ATC_VM_RUNNER:-atc-vm-runner}"
BUILD_DIR="${BASE}/build"
mkdir -p "$BUILD_DIR"

if ! command -v "$VM_RUNNER" >/dev/null 2>&1; then
  echo "ERROR: atc-vm-runner nicht gefunden (ATC_VM_RUNNER setzen)" >&2
  exit 2
fi

total=0; failed=0
for atc in "$BASE"/t*.atc; do
  name="$(basename "$atc" .atc)"
  vec="$BASE/vectors/${name%%_*}.json"
  ops_file="$BUILD_DIR/$name.ops"
  total=$((total + 1))
  # Phase 1: Assembler (fail-fast, simuliert gegen Vektor)
  if ! python3 "$BASE/../assemble.py" --contract "$atc" --vector "$vec" --out "$BUILD_DIR" >/dev/null 2>&1; then
    echo "FAIL  $name (Assembler)"
    failed=$((failed + 1))
    continue
  fi
  # Phase 2: ATVM-Ausfuehrung mit Vektorpruefung
  expect="$(python3 -c "import json;print(json.load(open('$vec'))['expected'])")"
  if "$VM_RUNNER" --ops "$ops_file" --expect "$expect" >/dev/null 2>&1; then
    echo "PASS  $name ($(grep -vc '^#' "$ops_file") Ops, expected=$expect)"
  else
    echo "FAIL  $name (ATVM, expected=$expect)"
    failed=$((failed + 1))
  fi
done

# ─── Bytecode-Fixtures: Verhaltensfluesse direkt auf der ATVM ────────────
# (Contract-Execution-Inkrement 1: Storage/Caller/Permissions — die .ops-
#  Programme sind hand-gestellte Bytecode-Tests, kein Assembler-Output.)
for ops_f in "$BASE"/ops/*.ops; do
  name="$(basename "$ops_f" .ops)"
  vec="$BASE/ops/$name.json"
  total=$((total + 1))
  flags="$(python3 - "$vec" << 'PYV'
import json, sys
v = json.load(open(sys.argv[1]))
parts = []
for k, val in v.get("set_slot", {}).items():
    parts += ["--set-slot", f"{k}:{val}"]
for k, val in v.get("expect_slot", {}).items():
    parts += ["--expect-slot", f"{k}:{val}"]
if "caller" in v:
    parts += ["--caller", str(v["caller"])]
parts += ["--expect", str(v["expected"])]
print(" ".join(parts))
PYV
)"
  if "$VM_RUNNER" --ops "$ops_f" $flags >/dev/null 2>&1; then
    echo "PASS  $name (Bytecode, ATVM + Storage-Evidenz)"
  else
    echo "FAIL  $name (Bytecode)"
    failed=$((failed + 1))
  fi
done

echo "=============================="
echo "EXEC-CHAIN-Tests: $((total - failed))/$total PASS"
[ "$failed" -eq 0 ] || exit 1
