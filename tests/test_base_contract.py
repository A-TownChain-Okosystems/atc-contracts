"""Unit-, Authorization-, State- und Revert-Tests fuer BaseContract."""
import pytest
from blockchain.contracts.base.base_contract import BaseContract


class DemoContract(BaseContract):
    def name(self) -> str:
        return "DemoContract"


@pytest.fixture
def contract():
    return DemoContract(owner="alice")


def test_init_and_address(contract):
    assert contract.owner == "alice"
    assert contract.address.startswith("ATC_CONTRACT_")
    assert contract.paused is False


def test_address_unique():
    a, b = DemoContract("alice"), DemoContract("alice")
    assert a.address != b.address


def test_info_metadata(contract):
    info = contract.info()
    assert isinstance(info, dict)
    assert info["owner"] == "alice"
    assert info["paused"] is False
    assert info["events"] == 0
    assert "address" in info and "created_at" in info


def test_only_owner_ok(contract):
    assert contract.only_owner("alice") is True


def test_only_owner_denied(contract):
    with pytest.raises(PermissionError):
        contract.only_owner("mallory")


def test_pause_requires_owner(contract):
    with pytest.raises(PermissionError):
        contract.pause("mallory")
    assert contract.paused is False


def test_pause_emits_event(contract):
    contract.pause("alice")
    assert contract.paused is True
    events = contract.get_events("Paused")
    assert len(events) == 1
    assert events[0]["data"]["by"] == "alice"


def test_unpause_requires_owner(contract):
    contract.pause("alice")
    with pytest.raises(PermissionError):
        contract.unpause("mallory")
    assert contract.paused is True


def test_unpause_emits_event(contract):
    contract.pause("alice")
    contract.unpause("alice")
    assert contract.paused is False
    assert len(contract.get_events("Unpaused")) == 1


def test_when_not_paused_ok(contract):
    contract.when_not_paused()  # wirft nicht


def test_when_not_paused_reverts(contract):
    contract.pause("alice")
    with pytest.raises(RuntimeError):
        contract.when_not_paused()


def test_get_events_filter(contract):
    contract.pause("alice")
    contract.unpause("alice")
    assert len(contract.get_events()) == 2
    assert len(contract.get_events("Paused")) == 1
    assert contract.get_events("Nonexistent") == []


def test_event_payload(contract):
    events = contract.get_events()
    contract.pause("alice")
    ev = contract.get_events("Paused")[0]
    assert ev["event"] == "Paused"
    assert ev["contract"] == contract.address
