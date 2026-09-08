"""Provenance- und Locking-Tests fuer GenesisToken (ATC-001)."""
import pytest
from blockchain.contracts.atc001.genesis_token import GenesisToken


def test_genesis_provenance():
    g = GenesisToken("creator")
    assert g.holder() == "creator"
    assert g.supply() == GenesisToken.GENESIS_SUPPLY == 21_000_000.0
    ev = g.get_events("Genesis")
    assert len(ev) == 1
    assert ev[0]["data"]["hash"] == GenesisToken.GENESIS_HASH


def test_transfer_changes_holder_and_owner():
    g = GenesisToken("creator")
    g.transfer("creator", "new-holder")
    assert g.holder() == "new-holder"
    assert g.owner == "new-holder"


def test_permanent_lock():
    g = GenesisToken("creator")
    with pytest.raises(PermissionError):
        g.lock("mallory")
    g.lock("creator")
    with pytest.raises(RuntimeError):
        g.transfer("creator", "anyone")
    assert g.holder() == "creator"
