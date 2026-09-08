"""Lifecycle-, Authorization-, Quorum- und Timelock-Tests fuer GovernanceContract."""
import time
import pytest
from blockchain.contracts.governance.governance_contract import GovernanceContract


@pytest.fixture
def gov():
    g = GovernanceContract(owner="gov-owner", total_supply=21_000_000.0)
    g.set_balance_oracle({"alice": 3_000_000.0, "bob": 100_000.0, "nobody": 0.0})
    return g


def _make(gov, options=("yes", "no"), period=60):
    res = gov.create_proposal("gov-owner", "Test", "Beschreibung", list(options),
                              voting_period_secs=period)
    assert res["success"] is True
    return gov.proposal_ids[-1]


def test_create_proposal_validation(gov):
    with pytest.raises(ValueError):
        gov.create_proposal("gov-owner", "", "d", ["yes", "no"])
    with pytest.raises(ValueError):
        gov.create_proposal("gov-owner", "T", "d", ["nur-eine"])
    with pytest.raises(ValueError):
        gov.create_proposal("gov-owner", "T", "d", [f"opt{i}" for i in range(11)])


def test_vote_lifecycle_and_weight(gov):
    pid = _make(gov)
    res = gov.vote("alice", pid, 0)
    assert res["success"] is True
    assert res["weight"] == 3_000_000.0


def test_vote_double_vote_rejected(gov):
    pid = _make(gov)
    gov.vote("alice", pid, 0)
    with pytest.raises(ValueError):
        gov.vote("alice", pid, 1)


def test_vote_invalid_option_and_zero_balance(gov):
    pid = _make(gov)
    with pytest.raises(ValueError):
        gov.vote("alice", pid, 5)
    with pytest.raises(PermissionError):
        gov.vote("nobody", pid, 0)


def test_finalize_quorum_and_timelock(gov):
    pid = _make(gov, period=1)
    gov.vote("alice", pid, 0)
    gov.vote("bob", pid, 0)
    time.sleep(1.05)
    res = gov.finalize_proposal(pid)
    assert res["success"] is True
    assert gov.proposals[pid].status == "PASSED"
    # Timelock (48h) blockiert sofortige Ausfuehrung
    with pytest.raises(ValueError):
        gov.execute_proposal("gov-owner", pid)
    # Nach (simuliertem) Timelock-Ablauf: Ausfuehrung erfolgreich
    gov.proposals[pid].timelock_end = int(time.time()) - 1
    res = gov.execute_proposal("gov-owner", pid)
    assert res["success"] is True
    assert gov.proposals[pid].status == "EXECUTED"


def test_finalize_quorum_rejected(gov):
    pid = _make(gov, period=1)
    gov.vote("bob", pid, 0)  # 100k < 10% von 21M = 2.1M
    time.sleep(1.05)
    res = gov.finalize_proposal(pid)
    assert res["success"] is False
    assert gov.proposals[pid].status == "REJECTED"
