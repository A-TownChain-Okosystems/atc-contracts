"""Registry-Operations- und Invokations-Tests fuer SmartContractRegistry."""
import pytest
from blockchain.contracts.base.base_contract import BaseContract
from blockchain.contracts.atc001.genesis_token import GenesisToken
from smart_contract_registry import SmartContractRegistry


class DummyContract(BaseContract):
    def name(self): return "Dummy"
    def ping(self): return "pong"


def test_deploy_get_list_call():
    reg = SmartContractRegistry()
    log = reg.deploy(DummyContract("alice"), deployer="alice")
    assert log["name"] == "Dummy"
    addr = log["address"]
    assert reg.get(addr).name() == "Dummy"
    assert len(reg.list_all()) == 1
    assert reg.call(addr, "ping") == "pong"
    assert len(reg.get_deploy_log()) == 1


def test_get_unknown_raises():
    reg = SmartContractRegistry()
    with pytest.raises(KeyError):
        reg.get("ATC_CONTRACT_unknown")


def test_call_missing_method_raises():
    reg = SmartContractRegistry()
    log = reg.deploy(DummyContract("alice"), deployer="alice")
    with pytest.raises(AttributeError):
        reg.call(log["address"], "does_not_exist")
