"""
blockchain/bridge/bridge_contract.py
Cross-Chain Bridge — ATC Lock/Unlock Mechanismus
Issue #10: Cross-Chain Bridge

Features:
  - lock_atc: ATC auf A-TownChain sperren → Wrapped ATC auf EVM/Solana
  - unlock_atc: Wrapped ATC verbrennen → ATC entsperren
  - lock_nft: Shivamon NFT sperren → Portiertes NFT auf anderer Chain
  - unlock_nft: Portiertes NFT verbrennen → Original zurück
  - Multi-Sig: 3-of-5 Bridge-Authorities
  - Emergency Pause: sofortige Sperre
  - Daily Limit: max. 5.000.000 ATC/Tag
"""
import time, hashlib, json
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from blockchain.contracts.base.base_contract import BaseContract


class BridgeChain(Enum):
    ATC_NATIVE = "atc_native"   # A-TownChain (Substrate/Python)
    ETHEREUM   = "ethereum"     # Ethereum / KAI-OS EVM (Chain-ID 9000)
    SOLANA     = "solana"       # Solana Devnet/Mainnet


class LockStatus(Enum):
    PENDING   = "PENDING"    # Warte auf Relayer
    CONFIRMED = "CONFIRMED"  # Bridge abgeschlossen
    FAILED    = "FAILED"
    RELEASED  = "RELEASED"   # Zurück-Bridge abgeschlossen


@dataclass
class BridgeLock:
    lock_id:           str
    asset_type:        str           # "ATC" | "NFT"
    token_id:          str           # ATC-Betrag (str) oder NFT-Token-ID
    sender:            str           # ATC-Adresse
    recipient:         str           # Ziel-Adresse (ETH/Solana)
    source_chain:      str           # BridgeChain.value
    target_chain:      str
    amount:            float         # ATC-Betrag (0.0 für NFTs)
    created_at:        int
    status:            str = "PENDING"
    tx_hash:           str = ""      # Source-Chain TX
    bridge_tx_hash:    str = ""      # Ziel-Chain TX
    relayer_sigs:      list = field(default_factory=list)
    completed_at:      int = 0

    def to_dict(self):
        return {
            "lock_id":        self.lock_id,
            "asset_type":     self.asset_type,
            "token_id":       self.token_id,
            "sender":         self.sender,
            "recipient":      self.recipient,
            "source_chain":   self.source_chain,
            "target_chain":   self.target_chain,
            "amount":         self.amount,
            "created_at":     self.created_at,
            "status":         self.status,
            "tx_hash":        self.tx_hash,
            "bridge_tx_hash": self.bridge_tx_hash,
            "signatures":     len(self.relayer_sigs),
            "completed_at":   self.completed_at,
        }


class BridgeContract(BaseContract):
    """
    A-TownChain Cross-Chain Bridge.
    Unterstützte Chains: ATC Native ↔ Ethereum ↔ Solana
    Sicherheit: 3-of-5 Multi-Sig, Daily Limit, Emergency Pause
    """

    # Sicherheits-Parameter
    MULTISIG_THRESHOLD = 3      # 3-of-5 Signaturen erforderlich
    MAX_TX_AMOUNT      = 1_000_000.0   # Max 1M ATC pro TX
    DAILY_LIMIT        = 5_000_000.0   # Max 5M ATC pro Tag
    LOCK_TIMEOUT       = 24 * 3600     # 24h bis TX verfällt

    def __init__(self, owner: str):
        super().__init__(owner, contract_id="ATC_BRIDGE_V1")
        self.locks:          dict[str, BridgeLock] = {}
        self.authorities:    list[str] = [owner]    # Bridge-Multi-Sig-Keys
        self.locked_balances: dict[str, float] = {} # gesperrte ATC
        self.locked_nfts:    list[str] = []         # gesperrte Token-IDs
        self._daily_volume:  dict[str, float] = {}  # date_str → volume
        self._atc_balances:  dict[str, float] = {}
        self._nft_contract   = None

    # ── Setup ──────────────────────────────────────────
    def add_authority(self, caller: str, authority: str) -> dict:
        """Fügt eine Bridge-Authority hinzu (max. 5)."""
        self.only_owner(caller)
        if len(self.authorities) >= 5:
            raise ValueError("Maximal 5 Bridge-Authorities erlaubt")
        if authority in self.authorities:
            raise ValueError("Authority bereits registriert")
        self.authorities.append(authority)
        self._emit("AuthorityAdded", {"authority": authority})
        return {"success": True, "authorities": self.authorities}

    def set_balance_oracle(self, balances: dict):
        self._atc_balances = balances

    def set_nft_contract(self, nft_contract):
        self._nft_contract = nft_contract

    # ── ATC Lock (→ EVM/Solana) ────────────────────────
    def lock_atc(
        self, sender: str, amount: float,
        recipient: str, target_chain: str
    ) -> dict:
        """
        Sperrt ATC auf A-TownChain.
        Relayer mintet Wrapped-ATC auf Ziel-Chain.
        """
        self.when_not_paused()
        self._validate_amount(amount, sender)

        # Balance abziehen
        balance = self._atc_balances.get(sender, 0.0)
        if balance < amount:
            raise ValueError(f"Unzureichendes Guthaben: {balance:.4f} < {amount:.4f} ATC")

        self._atc_balances[sender] = balance - amount
        self.locked_balances[sender] = self.locked_balances.get(sender, 0.0) + amount
        self._track_daily_volume(amount)

        lock_id = self._gen_lock_id(sender, amount, target_chain)
        lock = BridgeLock(
            lock_id      = lock_id,
            asset_type   = "ATC",
            token_id     = str(amount),
            sender       = sender,
            recipient    = recipient,
            source_chain = BridgeChain.ATC_NATIVE.value,
            target_chain = target_chain,
            amount       = amount,
            created_at   = int(time.time()),
        )
        self.locks[lock_id] = lock
        self._emit("ATCLocked", {
            "lock_id":      lock_id,
            "sender":       sender,
            "amount":       amount,
            "target_chain": target_chain,
            "recipient":    recipient,
        })
        return {"success": True, "lock": lock.to_dict(),
                "message": f"Relayer wird {amount} Wrapped-ATC auf {target_chain} minting..."}

    # ── ATC Unlock (← EVM/Solana) ──────────────────────
    def unlock_atc(
        self, lock_id: str, relayer_signatures: list
    ) -> dict:
        """
        Entsperrt ATC nach Wrapped-ATC-Burn auf Ziel-Chain.
        Benötigt 3-of-5 Relayer-Signaturen.
        """
        self.when_not_paused()
        lock = self.locks.get(lock_id)
        if not lock:
            raise KeyError(f"Lock {lock_id} nicht gefunden")
        if lock.status != LockStatus.PENDING.value:
            raise ValueError(f"Lock nicht ausstehend: {lock.status}")
        if int(time.time()) - lock.created_at > self.LOCK_TIMEOUT:
            lock.status = LockStatus.FAILED.value
            # Refund
            self._atc_balances[lock.sender] = self._atc_balances.get(lock.sender, 0.0) + lock.amount
            self.locked_balances[lock.sender] = self.locked_balances.get(lock.sender, 0.0) - lock.amount
            raise TimeoutError(f"Lock {lock_id} abgelaufen — ATC zurückerstattet")

        # Multi-Sig Verifikation
        valid_sigs = [s for s in relayer_signatures if s in self.authorities]
        if len(valid_sigs) < self.MULTISIG_THRESHOLD:
            raise PermissionError(
                f"Unzureichende Signaturen: {len(valid_sigs)} von {self.MULTISIG_THRESHOLD} erforderlich"
            )

        # ATC entsperren
        recipient = lock.sender   # ATC geht zurück an Original-Sender
        self._atc_balances[recipient] = self._atc_balances.get(recipient, 0.0) + lock.amount
        self.locked_balances[lock.sender] = max(
            0.0, self.locked_balances.get(lock.sender, 0.0) - lock.amount
        )

        lock.status       = LockStatus.RELEASED.value
        lock.relayer_sigs = valid_sigs
        lock.completed_at = int(time.time())

        self._emit("ATCUnlocked", {
            "lock_id":   lock_id,
            "recipient": recipient,
            "amount":    lock.amount,
        })
        return {"success": True, "lock": lock.to_dict(),
                "released_to": recipient, "amount": lock.amount}

    # ── NFT Lock ───────────────────────────────────────
    def lock_nft(
        self, sender: str, token_id: str,
        recipient: str, target_chain: str
    ) -> dict:
        """Sperrt Shivamon NFT für Chain-Transfer."""
        self.when_not_paused()
        if token_id in self.locked_nfts:
            raise ValueError(f"NFT {token_id} ist bereits gesperrt")

        # Ownership prüfen
        if self._nft_contract:
            nft = self._nft_contract.tokens.get(token_id)
            if not nft or nft.owner != sender:
                raise PermissionError(f"Nicht Eigentümer von {token_id}")
            # NFT zum Bridge-Contract transferieren
            self._nft_contract.transfer(token_id, sender, self.address)

        self.locked_nfts.append(token_id)
        lock_id = self._gen_lock_id(sender, 0, target_chain + token_id)
        lock = BridgeLock(
            lock_id      = lock_id,
            asset_type   = "NFT",
            token_id     = token_id,
            sender       = sender,
            recipient    = recipient,
            source_chain = BridgeChain.ATC_NATIVE.value,
            target_chain = target_chain,
            amount       = 0.0,
            created_at   = int(time.time()),
        )
        self.locks[lock_id] = lock
        self._emit("NFTLocked", {
            "lock_id":      lock_id,
            "token_id":     token_id,
            "sender":       sender,
            "target_chain": target_chain,
        })
        return {"success": True, "lock": lock.to_dict(),
                "message": f"NFT {token_id} gesperrt. Relayer mintet auf {target_chain}..."}

    # ── NFT Unlock ─────────────────────────────────────
    def unlock_nft(self, lock_id: str, relayer_signatures: list) -> dict:
        """Gibt gesperrtes NFT frei (nach Burn auf Ziel-Chain)."""
        self.when_not_paused()
        lock = self.locks.get(lock_id)
        if not lock or lock.asset_type != "NFT":
            raise KeyError(f"NFT-Lock {lock_id} nicht gefunden")
        if lock.status != LockStatus.PENDING.value:
            raise ValueError(f"Lock nicht ausstehend: {lock.status}")

        valid_sigs = [s for s in relayer_signatures if s in self.authorities]
        if len(valid_sigs) < self.MULTISIG_THRESHOLD:
            raise PermissionError(f"Unzureichende Signaturen: {len(valid_sigs)}/3")

        # NFT zurückgeben
        if self._nft_contract and lock.token_id in self.locked_nfts:
            self._nft_contract.transfer(lock.token_id, self.address, lock.sender)
            self.locked_nfts.remove(lock.token_id)

        lock.status       = LockStatus.RELEASED.value
        lock.relayer_sigs = valid_sigs
        lock.completed_at = int(time.time())

        self._emit("NFTUnlocked", {
            "lock_id":   lock_id,
            "token_id":  lock.token_id,
            "recipient": lock.sender,
        })
        return {"success": True, "lock": lock.to_dict()}

    # ── Confirm (Relayer signiert) ─────────────────────
    def confirm_bridge(self, relayer: str, lock_id: str, bridge_tx_hash: str) -> dict:
        """Relayer bestätigt erfolgreichen Bridge-Vorgang."""
        if relayer not in self.authorities:
            raise PermissionError(f"{relayer} ist keine Bridge-Authority")
        lock = self.locks.get(lock_id)
        if not lock:
            raise KeyError(f"Lock {lock_id} nicht gefunden")
        if relayer not in lock.relayer_sigs:
            lock.relayer_sigs.append(relayer)
        lock.bridge_tx_hash = bridge_tx_hash
        if len(lock.relayer_sigs) >= self.MULTISIG_THRESHOLD:
            lock.status       = LockStatus.CONFIRMED.value
            lock.completed_at = int(time.time())
        self._emit("BridgeConfirmed", {
            "lock_id":        lock_id,
            "relayer":        relayer,
            "bridge_tx_hash": bridge_tx_hash,
            "signatures":     len(lock.relayer_sigs),
        })
        return {"success": True, "lock": lock.to_dict()}

    # ── Queries ────────────────────────────────────────
    def get_lock(self, lock_id: str) -> dict:
        l = self.locks.get(lock_id)
        return l.to_dict() if l else {"error": "Nicht gefunden"}

    def get_pending_locks(self) -> list:
        return [l.to_dict() for l in self.locks.values()
                if l.status == LockStatus.PENDING.value]

    def get_locked_balance(self, address: str) -> float:
        return self.locked_balances.get(address, 0.0)

    def get_stats(self) -> dict:
        pending   = sum(1 for l in self.locks.values() if l.status == "PENDING")
        confirmed = sum(1 for l in self.locks.values() if l.status == "CONFIRMED")
        total_locked = sum(self.locked_balances.values())
        return {
            "total_locks":       len(self.locks),
            "pending":           pending,
            "confirmed":         confirmed,
            "locked_nfts":       len(self.locked_nfts),
            "total_locked_atc":  total_locked,
            "authorities":       len(self.authorities),
            "multisig_threshold": self.MULTISIG_THRESHOLD,
            "daily_limit_atc":   self.DAILY_LIMIT,
            "max_tx_atc":        self.MAX_TX_AMOUNT,
        }

    # ── Helpers ────────────────────────────────────────
    def _validate_amount(self, amount: float, sender: str):
        if amount <= 0:
            raise ValueError("Betrag muss > 0 sein")
        if amount > self.MAX_TX_AMOUNT:
            raise ValueError(f"Überschreitet TX-Limit: {amount} > {self.MAX_TX_AMOUNT} ATC")
        today = time.strftime("%Y-%m-%d")
        daily = self._daily_volume.get(today, 0.0)
        if daily + amount > self.DAILY_LIMIT:
            raise ValueError(f"Daily Limit überschritten: {daily + amount} > {self.DAILY_LIMIT} ATC")

    def _track_daily_volume(self, amount: float):
        today = time.strftime("%Y-%m-%d")
        self._daily_volume[today] = self._daily_volume.get(today, 0.0) + amount

    def _gen_lock_id(self, sender: str, amount: float, extra: str) -> str:
        seed = f"{sender}{amount}{extra}{time.time_ns()}"
        return "LOCK-" + hashlib.sha256(seed.encode()).hexdigest()[:12].upper()
