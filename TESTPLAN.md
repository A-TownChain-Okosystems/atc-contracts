# Testplan — atc-contracts

**Standard:** ATC-STD-BUG-002/003-konform · **Test-Runner:** pytest (Python 3.11)
**Status:** Tests: 59/59 GRÜN (alle Klassen aus ATC-ORG-AUDIT-002 P1-001 abgedeckt)

## Abgedeckte Testklassen

| Klasse | Datei | Deckung |
|---|---|---|
| Unit | test_base_contract.py, test_atcoin.py | Initialisierung, Address-Gen, Metadaten |
| Integration | test_smart_contract_registry.py | Deploy/Get/List/Call-Invokation |
| Negative | test_atcoin.py, test_governance_contract.py | Insufficient balance/allowance, leere Titel, invalid options |
| Authorization | test_atc8300_token.py, test_genesis_token.py, test_bridge_contract.py | only_owner-Guards (mint/lock/pause/snapshot) |
| State Transition | test_bridge_contract.py, test_governance_contract.py | locked→minted→released, ACTIVE→PASSED→EXECUTED |
| Failure/Revert | test_base_contract.py, test_atcoin.py | Paused-State friert Operationen atomar ein |
| Gas/Resource | test_atcoin.py | Max-Supply-Cap-Invariante (21M), Burn-Permanent-Supply |
| Property/Invariant | test_atc8300_token.py, test_atc_spec_semantics.py | Fee-Routing 0.001→Owner, Snapshot-Unveränderlichkeit, Py↔Atc-Parität |
| Security | test_bridge_contract.py, test_genesis_token.py | Limits (MIN/MAX), Chain-Whitelist, Permanent Lock, Pause-Guards |

## Ausführung

```bash
pip install -r requirements.txt pytest
pytest tests/ -q
```

## Offene Punkte

1. **ATCLang-VM-Bytecode-Ausführung:** Derzeit wird die Python-Kontraktlogik
   getestet plus semantische Struktur-Validierung der `.atc`-Quellen. Sobald
   der `atcvm`-Interpreter für Verträge freigegeben ist, erweitert
   `test_atc_spec_semantics.py` direkt auf Bytecode-Ausführung.
2. **Coverage-Messung:** `pytest --cov` nach CI-Etablierung (ci.yml).
