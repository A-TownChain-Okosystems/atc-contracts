"""Semantische Spezifikations-Tests: .atc-Vertraege (ATCLang-Quellen) gegen Struktur-Invarianten.

Diese Tests validieren die ATCLang-Spezifikationsdateien ohne VM-Abhaengigkeit:
Paritaet Python-Implementierung <-> .atc-Spezifikation, Struktur-Marker und
Basis-Invarianten. Bei Verfuegbarkeit der ATCLang-VM kann der Harness um
Bytecode-Ausfuehrung erweitert werden.
"""
import os
import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTRACT_DIRS = ["base", "atcoin", "atc8300", "governance", "bridge",
                 "contracts/atc001"]
ROOT_CONTRACTS = ["smart_contracts", "smart_contract_registry"]


def _atc_files():
    found = []
    for root, _dirs, files in os.walk(REPO_ROOT):
        if ".git" in root:
            continue
        for f in files:
            if f.endswith(".atc"):
                found.append(os.path.join(root, f))
    return found


def test_atc_files_exist():
    files = _atc_files()
    assert len(files) >= 10, f"zu wenige .atc-Dateien: {len(files)}"


def test_atc_files_nonempty_and_structured():
    """Jede .atc-Datei ist entweder ATCLang-Quelle (Marker) oder Redirect-Stub
    (Archiv-Migration mit Zielangabe). Leere/strukturlose Dateien sind Findings."""
    markers = ("contract ", "const ", "struct ", "state ")
    stub_hints = ("ARCHIVED", "verschoben", "Migration")
    for path in _atc_files():
        content = open(path, encoding="utf-8").read()
        assert content.strip(), f"leere .atc-Datei: {path}"
        has_markers = any(m in content for m in markers)
        is_stub = any(h in content for h in stub_hints) and ".atc" in content
        assert has_markers or is_stub, f"keine ATCLang-Marker und kein Stub-Hinweis: {path}"


@pytest.mark.parametrize("dirname", CONTRACT_DIRS)
def test_python_atc_parity_modules(dirname):
    d = os.path.join(REPO_ROOT, dirname)
    pys = {f[:-3] for f in os.listdir(d) if f.endswith(".py") and f != "__init__.py"}
    atcs = {f[:-4] for f in os.listdir(d) if f.endswith(".atc")}
    # Zusaetzliche reine Spez-Doku-Dateien (z.B. atc8300.atc) sind erlaubt:
    atcs = {a for a in atcs if a in pys or a.startswith(tuple(pys))}
    assert pys and atcs, f"{dirname}: leeres Verzeichnis"
    assert pys == atcs, f"{dirname}: Paritaet verletzt (py={pys}, atc={atcs})"


def test_python_atc_parity_root_contracts():
    for base in ROOT_CONTRACTS:
        assert os.path.exists(os.path.join(REPO_ROOT, base + ".py"))
        assert os.path.exists(os.path.join(REPO_ROOT, base + ".atc"))
