"""ERR-009 Preventive Control — musterweiter Gate-Test (ATC-ERR-0001, ERR-Familie).

Praevention fuer das Fehlermuster 'abstrakte Basisklassen-Methode nicht
implementiert' (ATC-ERR-PATTERN-009): Statisch prueft dieser Test JEDE Klasse
im Repository, die von einer Klasse mit @abstractmethod erbt — unvollstaendige
Implementierungen lassen den kompletten Build rot werden.

Haette vor dem GovernanceContract-Fix (08.09.2026, Issue #99) FAILED geliefert
und haette den Bug vor dem Registry-Crash gefunden.
"""
import ast, os, glob
import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _scan(root):
    abstract_defs, class_defs, inherits = {}, {}, []
    for path in glob.glob(f"{root}/**/*.py", recursive=True):
        if "__pycache__" in path or "/.git/" in path or "/tests/" in path:
            continue
        try:
            tree = ast.parse(open(path, encoding="utf-8").read())
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                methods, abstracts = set(), set()
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        methods.add(item.name)
                        for dec in item.decorator_list:
                            if "abstractmethod" in ast.unparse(dec):
                                abstracts.add(item.name)
                abstract_defs.setdefault(node.name, set()).update(abstracts)
                class_defs.setdefault(node.name, set()).update(methods)
                for b in node.bases:
                    inherits.append((os.path.relpath(path, root), node.name, ast.unparse(b).split("(")[0].strip()))
    violations = []
    for path, cls, base in inherits:
        if base in abstract_defs and base != cls:
            missing = abstract_defs[base] - class_defs.get(cls, set())
            if missing:
                violations.append(f"{path}: Klasse {cls} erbt {base}, implementiert aber nicht: {sorted(missing)}")
    return violations


def test_no_unimplemented_abstract_methods_anywhere():
    """Muster-Gate: keine Klasse im Repo darf abstrakte Methoden unimplementiert lassen."""
    violations = _scan(REPO_ROOT)
    assert not violations, (
        "ATC-ERR-PATTERN-009-Verstoss (abstrakte Methode nicht implementiert):\n"
        + "\n".join(violations)
    )


def test_base_contract_subclasses_are_instantiable():
    """Direkter Instanziierungs-Gate: jede konkrete BaseContract-Subklasse muss
    instanziierbar sein (GovernanceContract-Bug war genau das Gegenteil)."""
    import sys, importlib.util, types
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from conftest import _register  # Shim laedt alle Vertragsmodule
    from blockchain.contracts.governance.governance_contract import GovernanceContract
    from blockchain.contracts.atc8300.atc8300_token import ATC8300Token
    from blockchain.contracts.atc001.genesis_token import GenesisToken
    for cls in (GovernanceContract, ATC8300Token, GenesisToken):
        assert not cls.__abstractmethods__, f"{cls.__name__} hat unimplementierte abstrakte Methoden: {cls.__abstractmethods__}"
