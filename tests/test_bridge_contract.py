"""Lock-Mint/Burn-Release-, Limit- und Security-Tests fuer BridgeContract (ATC-5000)."""
import pytest
from blockchain.contracts.bridge.bridge_contract import BridgeContract, ChainId, BridgeTxStatus


@pytest.fixture
def bridge():
    return BridgeContract(owner="bridge-owner")


def test_lock_mint_burn_release(bridge):
    tx = bridge.lock_and_bridge("alice", "bob-eth", 1000.0, ChainId.ETH)
    assert tx.status == BridgeTxStatus.LOCKED
    assert tx.amount == pytest.approx(999.0)  # 0.1% Fee abgezogen
    assert tx.fee == pytest.approx(1.0)
    assert bridge.confirm_mint(tx.id, "0xabc") is True
    assert bridge.get_tx(tx.id).status == BridgeTxStatus.MINTED
    assert bridge.burn_and_release(tx.id, "alice") is True
    assert bridge.get_tx(tx.id).status == BridgeTxStatus.RELEASED


def test_limits_and_chains(bridge):
    with pytest.raises(ValueError):
        bridge.lock_and_bridge("a", "b", 9.99, ChainId.ETH)     # unter MIN_AMOUNT
    with pytest.raises(ValueError):
        bridge.lock_and_bridge("a", "b", 1_000_001.0, ChainId.ETH)  # ueber MAX_AMOUNT
    with pytest.raises(ValueError):
        bridge.lock_and_bridge("a", "b", 100.0, "solana-mainnet")  # nicht unterstuetzt


def test_pause_security(bridge):
    with pytest.raises(PermissionError):
        bridge.pause("mallory")
    bridge.pause("bridge-owner")
    with pytest.raises(RuntimeError):
        bridge.lock_and_bridge("a", "b", 100.0, ChainId.BSC)
    bridge.resume("bridge-owner")
    tx = bridge.lock_and_bridge("a", "b", 100.0, ChainId.BSC)
    assert tx.status == BridgeTxStatus.LOCKED
