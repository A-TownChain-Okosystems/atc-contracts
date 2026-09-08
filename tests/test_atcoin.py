"""Unit-, State-, Supply- und Security-Tests fuer ATCoin (ATC-8300)."""
from decimal import Decimal
import pytest
from blockchain.contracts.atcoin.atcoin import ATCoin, ATC_MAX_SUPPLY


@pytest.fixture
def coin():
    c = ATCoin()
    c.mint("alice", Decimal("1000"))
    return c


def test_initial_state():
    c = ATCoin()
    assert c.total_supply == Decimal("0")
    assert c.max_supply == Decimal(str(ATC_MAX_SUPPLY)) == Decimal("21000000")


def test_mint_increases_supply(coin):
    assert coin.balance_of("alice") == Decimal("1000")
    assert coin.total_supply == Decimal("1000")


def test_mint_respects_max_supply():
    c = ATCoin()
    res = c.mint("alice", Decimal(str(ATC_MAX_SUPPLY)))
    assert res["success"] is True
    res2 = c.mint("alice", Decimal("1"))
    assert res2["success"] is False
    assert "error" in res2


def test_transfer_moves_funds(coin):
    res = coin.transfer("alice", "bob", Decimal("100"))
    assert res["success"] is True
    assert coin.balance_of("alice") == Decimal("900")
    assert coin.balance_of("bob") == Decimal("100")


def test_transfer_insufficient_balance(coin):
    res = coin.transfer("alice", "bob", Decimal("1001"))
    assert res["success"] is False
    assert "Insufficient" in res["error"]


def test_transfer_paused_reverts(coin):
    coin.pause()
    res = coin.transfer("alice", "bob", Decimal("10"))
    assert res["success"] is False
    assert "paused" in res["error"]


def test_approve_and_allowance(coin):
    assert coin.approve("alice", "bob", Decimal("500")) is True
    assert coin.allowance("alice", "bob") == Decimal("500")
    assert coin.allowance("alice", "mallory") == Decimal("0")


def test_transfer_from_within_allowance(coin):
    coin.approve("alice", "bob", Decimal("300"))
    res = coin.transfer_from("bob", "alice", "carol", Decimal("200"))
    assert res["success"] is True
    assert coin.balance_of("carol") == Decimal("200")
    assert coin.allowance("alice", "bob") == Decimal("100")


def test_transfer_from_allowance_exceeded(coin):
    coin.approve("alice", "bob", Decimal("50"))
    res = coin.transfer_from("bob", "alice", "carol", Decimal("51"))
    assert res["success"] is False
    assert "Allowance" in res["error"]


def test_burn_reduces_supply(coin):
    res = coin.burn("alice", Decimal("400"))
    assert res["success"] is True
    assert coin.balance_of("alice") == Decimal("600")
    assert coin.total_supply == Decimal("600")


def test_burn_insufficient_balance(coin):
    res = coin.burn("alice", Decimal("1001"))
    assert res["success"] is False
    assert "Insufficient" in res["error"]


def test_burn_paused_reverts(coin):
    coin.pause()
    res = coin.burn("alice", Decimal("10"))
    assert res["success"] is False


def test_snapshot_and_tx_history(coin):
    snap = coin.snapshot()
    assert snap is not None
    coin.transfer("alice", "bob", Decimal("10"))
    hist = coin.get_tx_history("alice")
    assert len(hist) >= 1


def test_to_dict(coin):
    d = coin.to_dict()
    assert isinstance(d, dict)
    assert "total_supply" in d
