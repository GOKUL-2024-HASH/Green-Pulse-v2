"""
Ledger hash chain data models for GreenPulse 2.0.
Provides dataclasses used by ledger/writer.py and ledger/verifier.py.
"""

import hashlib
import json
import datetime
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Optional


@dataclass
class LedgerEntry:
    """Represents a single entry in the audit ledger."""
    event_type: str
    event_id: str
    event_data: Dict[str, Any]
    sequence_number: int
    prev_hash: str
    entry_hash: str = field(default="")
    created_at: datetime.datetime = field(default_factory=datetime.datetime.utcnow)

    def compute_hash(self) -> str:
        """
        Compute SHA256 over canonical JSON of event_data + prev_hash.
        Deterministic: sorts keys, uses separators for compactness.
        """
        payload = json.dumps(self.event_data, sort_keys=True, separators=(',', ':'))
        raw = f"{payload}{self.prev_hash}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def __post_init__(self):
        if not self.entry_hash:
            self.entry_hash = self.compute_hash()


@dataclass
class ChainVerificationResult:
    """Result of running the full ledger chain verification."""
    is_valid: bool
    total_entries: int
    broken_at_sequence: Optional[int] = None
    error_message: Optional[str] = None

    def __str__(self) -> str:
        if self.is_valid:
            return f"Chain OK — {self.total_entries} entries verified"
        return (
            f"Chain BROKEN at sequence {self.broken_at_sequence}: "
            f"{self.error_message}"
        )
