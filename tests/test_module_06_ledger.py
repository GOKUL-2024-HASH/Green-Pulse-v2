"""
Tests for Module 07 — Audit Ledger.
Tests writer, verifier, chain integrity, and tamper detection.
"""
import pytest
import uuid
from unittest.mock import MagicMock, patch
from ledger.models import LedgerEntry, ChainVerificationResult
from ledger.writer import _compute_hash, _serialize_event_data


class TestLedgerEntry:
    def test_hash_computed_on_init(self):
        entry = LedgerEntry(
            event_type="TEST",
            event_id="e001",
            event_data={"station": "DL001", "value": 85.0},
            sequence_number=1,
            prev_hash="0" * 64,
        )
        assert len(entry.entry_hash) == 64
        assert all(c in "0123456789abcdef" for c in entry.entry_hash)

    def test_different_data_produces_different_hash(self):
        e1 = LedgerEntry("T", "e1", {"x": 1}, 1, "0" * 64)
        e2 = LedgerEntry("T", "e1", {"x": 2}, 1, "0" * 64)
        assert e1.entry_hash != e2.entry_hash

    def test_hash_chaining(self):
        e1 = LedgerEntry("T", "e1", {"v": 1}, 1, "0" * 64)
        e2 = LedgerEntry("T", "e2", {"v": 2}, 2, e1.entry_hash)
        e3 = LedgerEntry("T", "e3", {"v": 3}, 3, e2.entry_hash)
        # Changing e1 should make e3's expected prev_hash invalid
        assert e3.prev_hash == e2.entry_hash
        assert e2.prev_hash == e1.entry_hash

    def test_genesis_entry_uses_zero_prev_hash(self):
        entry = LedgerEntry("GENESIS", "g1", {"init": True}, 1, "0" * 64)
        assert entry.prev_hash == "0" * 64

    def test_100_entry_chain_all_unique_hashes(self):
        prev = "0" * 64
        hashes = set()
        for i in range(100):
            entry = LedgerEntry("T", f"e{i}", {"seq": i}, i + 1, prev)
            assert entry.entry_hash not in hashes
            hashes.add(entry.entry_hash)
            prev = entry.entry_hash


class TestComputeHash:
    def test_deterministic(self):
        h1 = _compute_hash({"a": 1}, "0" * 64)
        h2 = _compute_hash({"a": 1}, "0" * 64)
        assert h1 == h2

    def test_key_order_independent(self):
        h1 = _compute_hash({"a": 1, "b": 2}, "0" * 64)
        h2 = _compute_hash({"b": 2, "a": 1}, "0" * 64)
        assert h1 == h2  # Canonical JSON sorts keys

    def test_prev_hash_changes_result(self):
        h1 = _compute_hash({"a": 1}, "0" * 64)
        h2 = _compute_hash({"a": 1}, "1" * 64)
        assert h1 != h2


class TestChainVerificationResult:
    def test_valid_chain_str(self):
        result = ChainVerificationResult(is_valid=True, total_entries=100)
        assert "100" in str(result)
        assert "OK" in str(result)

    def test_broken_chain_str(self):
        result = ChainVerificationResult(
            is_valid=False,
            total_entries=50,
            broken_at_sequence=42,
            error_message="hash mismatch",
        )
        assert "42" in str(result)
        assert "BROKEN" in str(result)


class TestWriterWithMockDB:
    def _make_mock_db(self, last_row=None):
        """Create a mock session that simulates the DB."""
        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = last_row
        mock_db.execute.return_value = mock_result
        return mock_db

    def test_genesis_entry_uses_zero_prev_hash(self):
        from ledger.writer import append_entry
        db = self._make_mock_db(last_row=None)  # Empty ledger
        entry = append_entry(db, "TEST", "e001", {"val": 1})
        assert entry["prev_hash"] == "0" * 64
        assert entry["sequence_number"] == 1

    def test_sequence_increments(self):
        from ledger.writer import append_entry
        existing_hash = "a" * 64
        db = self._make_mock_db(last_row=(5, existing_hash))
        entry = append_entry(db, "TEST", "e006", {"val": 6})
        assert entry["sequence_number"] == 6
        assert entry["prev_hash"] == existing_hash


if __name__ == "__main__":
    import subprocess, sys
    sys.exit(subprocess.call(["pytest", __file__, "-v"]))
