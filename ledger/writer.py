"""
Audit Ledger Writer — GreenPulse 2.0

INSERT-only. Computes SHA256 hash chain across all entries.
Genesis entry uses prev_hash = "0" * 64.
"""

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger(__name__)


def _serialize_event_data(event_data: Dict[str, Any]) -> str:
    """Canonical JSON serialization (sorted keys, no extra spaces)."""
    return json.dumps(event_data, sort_keys=True, separators=(",", ":"), default=str)


def _compute_hash(event_data: Dict[str, Any], prev_hash: str) -> str:
    """
    Compute SHA256(canonical_JSON(event_data) + prev_hash).
    """
    payload = _serialize_event_data(event_data) + prev_hash
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _get_last_entry(db: Session) -> Optional[dict]:
    """
    Fetch the last entry in the audit_ledger ordered by sequence_number.
    Returns a dict with sequence_number and entry_hash, or None if empty.
    """
    result = db.execute(text(
        "SELECT sequence_number, entry_hash FROM audit_ledger "
        "ORDER BY sequence_number DESC LIMIT 1"
    ))
    row = result.fetchone()
    if row:
        return {"sequence_number": row[0], "entry_hash": row[1]}
    return None


def append_entry(
    db: Session,
    event_type: str,
    event_id: str,
    event_data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Append a new immutable entry to the audit ledger.

    Computes prev_hash from the last entry (or genesis if first entry).
    Computes entry_hash = SHA256(event_data + prev_hash).
    Inserts the new row — never updates or deletes.

    Args:
        db: SQLAlchemy session.
        event_type: e.g. "COMPLIANCE_EVENT", "OFFICER_ACTION", "REPORT_GENERATED"
        event_id: Identifier of the originating entity (UUID string).
        event_data: Dict of structured event metadata.

    Returns:
        Dict with the inserted entry's fields.

    Raises:
        RuntimeError: If the insert fails (e.g. DB constraint violation).
    """
    last = _get_last_entry(db)

    if last is None:
        # Genesis entry
        prev_hash = "0" * 64
        sequence_number = 1
    else:
        prev_hash = last["entry_hash"]
        sequence_number = last["sequence_number"] + 1

    entry_hash = _compute_hash(event_data, prev_hash)
    entry_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    try:
        db.execute(text("""
            INSERT INTO audit_ledger
                (id, sequence_number, event_type, event_id, event_data, prev_hash, entry_hash, created_at)
            VALUES
                (:id, :seq, :etype, :eid, cast(:edata as json), :prev, :ehash, :created_at)
        """), {
            "id": entry_id,
            "seq": sequence_number,
            "etype": event_type,
            "eid": event_id,
            "edata": _serialize_event_data(event_data),
            "prev": prev_hash,
            "ehash": entry_hash,
            "created_at": now,
        })
        db.commit()

        logger.info(
            "Audit ledger entry appended: seq=%d type=%s id=%s hash=%s...",
            sequence_number, event_type, event_id, entry_hash[:16]
        )

        return {
            "id": entry_id,
            "sequence_number": sequence_number,
            "event_type": event_type,
            "event_id": event_id,
            "event_data": event_data,
            "prev_hash": prev_hash,
            "entry_hash": entry_hash,
            "created_at": now.isoformat(),
        }

    except Exception as e:
        db.rollback()
        logger.error("Failed to append audit ledger entry: %s", e)
        raise RuntimeError(f"Audit ledger write failed: {e}") from e
