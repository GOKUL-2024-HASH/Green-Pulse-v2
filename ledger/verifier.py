"""
Audit Ledger Verifier — GreenPulse 2.0

Traverses the entire audit_ledger chain and verifies:
1. sequence_numbers are contiguous
2. Each entry's prev_hash matches the previous entry's entry_hash
3. Each entry's entry_hash = SHA256(event_data + prev_hash)

Runs automatically on API startup.
"""

import hashlib
import json
import logging
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import text

from ledger.models import ChainVerificationResult

logger = logging.getLogger(__name__)


def _recompute_hash(event_data_json: str, prev_hash: str) -> str:
    """Recompute the expected hash from stored event_data JSON string."""
    # Normalize: if event_data_json is already a string, use it directly.
    # If it's a dict (psycopg2 auto-parsed JSON), re-serialize canonically.
    if isinstance(event_data_json, dict):
        canonical = json.dumps(event_data_json, sort_keys=True, separators=(",", ":"), default=str)
    else:
        # Re-parse and re-serialize to normalize whitespace and key ordering
        try:
            parsed = json.loads(event_data_json)
            canonical = json.dumps(parsed, sort_keys=True, separators=(",", ":"), default=str)
        except (json.JSONDecodeError, TypeError):
            canonical = str(event_data_json)

    payload = canonical + prev_hash
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def verify_chain(db: Session) -> ChainVerificationResult:
    """
    Traverse the entire audit ledger and verify hash chain integrity.

    Args:
        db: SQLAlchemy session.

    Returns:
        ChainVerificationResult with is_valid flag and any broken sequence number.
    """
    result = db.execute(text(
        "SELECT sequence_number, event_data, prev_hash, entry_hash "
        "FROM audit_ledger "
        "ORDER BY sequence_number ASC"
    ))
    rows = result.fetchall()

    if not rows:
        logger.info("Audit ledger is empty — chain trivially valid")
        return ChainVerificationResult(is_valid=True, total_entries=0)

    expected_prev_hash = "0" * 64
    expected_sequence = rows[0][0]  # start from the actual first sequence in the ledger

    for row in rows:
        seq, event_data, prev_hash, stored_hash = row

        # Check sequence continuity
        if seq != expected_sequence:
            msg = f"Sequence gap: expected {expected_sequence}, got {seq}"
            logger.error("Chain integrity violation: %s", msg)
            return ChainVerificationResult(
                is_valid=False,
                total_entries=seq,
                broken_at_sequence=seq,
                error_message=msg,
            )

        # Check prev_hash linkage
        if prev_hash != expected_prev_hash:
            msg = (
                f"prev_hash mismatch at seq {seq}: "
                f"expected {expected_prev_hash[:16]}..., "
                f"got {prev_hash[:16]}..."
            )
            logger.error("Chain integrity violation: %s", msg)
            return ChainVerificationResult(
                is_valid=False,
                total_entries=seq,
                broken_at_sequence=seq,
                error_message=msg,
            )

        # Recompute and verify entry_hash
        computed_hash = _recompute_hash(event_data, prev_hash)
        if computed_hash != stored_hash:
            msg = (
                f"entry_hash mismatch at seq {seq}: "
                f"computed {computed_hash[:16]}..., "
                f"stored {stored_hash[:16]}..."
            )
            logger.error("Chain integrity violation (TAMPERED ENTRY): %s", msg)
            return ChainVerificationResult(
                is_valid=False,
                total_entries=seq,
                broken_at_sequence=seq,
                error_message=msg,
            )

        # Advance chain state
        expected_prev_hash = stored_hash
        expected_sequence += 1

    total = len(rows)
    logger.info("Audit ledger chain verified: %d entries all valid", total)
    return ChainVerificationResult(is_valid=True, total_entries=total)
