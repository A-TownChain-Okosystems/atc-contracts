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

echo "=============================="
echo "EXEC-CHAIN-Tests: $((total - failed))/$total PASS"
[ "$failed" -eq 0 ] || exit 1
