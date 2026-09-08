"""Import-Shim: bildet das legacy-Package blockchain.contracts.* auf das Repo-Root ab.

Quellcode bleibt unveraendert (keine Eingriffe); die Vertrags-Module importieren
einander via `blockchain.contracts.*` und werden hier unter identischen
dotted names registriert.
"""
import os, sys, types, importlib.util

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


def _parent(name: str) -> None:
    if name not in sys.modules:
        m = types.ModuleType(name)
        m.__path__ = []
        sys.modules[name] = m


def _register(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, os.path.join(REPO_ROOT, rel))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


for pkg in ["blockchain", "blockchain.contracts",
            "blockchain.contracts.base", "blockchain.contracts.atcoin",
            "blockchain.contracts.atc8300", "blockchain.contracts.governance",
            "blockchain.contracts.bridge", "blockchain.contracts.atc001"]:
    _parent(pkg)

_register("blockchain.contracts.base.base_contract", os.path.join("base", "base_contract.py"))
_register("blockchain.contracts.atcoin.atcoin", os.path.join("atcoin", "atcoin.py"))
_register("blockchain.contracts.atc8300.atc8300_token", os.path.join("atc8300", "atc8300_token.py"))
_register("blockchain.contracts.governance.governance_contract", os.path.join("governance", "governance_contract.py"))
_register("blockchain.contracts.bridge.bridge_contract", os.path.join("bridge", "bridge_contract.py"))
_register("blockchain.contracts.atc001.genesis_token", os.path.join("contracts", "atc001", "genesis_token.py"))
