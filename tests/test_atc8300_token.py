"""Authorization-, Fee-, Snapshot- und Revert-Tests fuer ATC8300Token."""
import pytest
from blockchain.contracts.atc8300.atc8300_token import ATC8300Token


@pytest.fixture
def token():
    t = ATC8300Token(owner="alice")
    t.mint("alice", "bob", 1000.0)
    return t


def test_metadata():
    t = ATC8300Token("alice")
    assert t.name() == "ATCoin"
    assert t.total_supply() == 0.0


def test_mint_owner_only(token):
    with pytest.raises(PermissionError):
        token.mint("mallory", "mallory", 10.0)
    assert token.balance_of("mallory") == 0.0


def test_mint_positive_amounts_only(token):
    with pytest.raises(ValueError):
        token.mint("alice", "bob", 0.0)
    with pytest.raises(ValueError):
        token.mint("alice", "bob", -5.0)


def test_transfer_with_fee_routing(token):
    res = token.transfer("bob", "carol", 100.0)
    assert token.balance_of("bob") == pytest.approx(899.999)
    assert token.balance_of("carol") == pytest.approx(100.0)
    assert token.balance_of("alice") == pytest.approx(0.001)  # Fee -> Owner


def test_transfer_insufficient_funds(token):
    with pytest.raises(ValueError):
        token.transfer("bob", "carol", 1000.0)


def test_burn_and_state(token):
    res = token.burn("bob", 400.0)
    assert res["success"] is True
    assert token.balance_of("bob") == pytest.approx(600.0)
    assert token.total_supply() == pytest.approx(600.0)


def test_burn_insufficient(token):
    with pytest.raises(ValueError):
        token.burn("bob", 1001.0)


def test_snapshot_owner_only_and_immutable(token):
    snap = token.snapshot("alice")
    assert snap["supply"] == 1000.0
    token.transfer("bob", "carol", 50.0)
    frozen = token.get_snapshot(snap["id"])
    assert frozen["balances"]["bob"] == 1000.0  # Snapshot bleibt unveraendert
    with pytest.raises(PermissionError):
        token.snapshot("mallory")
