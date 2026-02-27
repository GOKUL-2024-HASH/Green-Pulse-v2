#!/usr/bin/env python3
"""
smoke_test.py — GreenPulse 2.0 End-to-End Smoke Test

Tests the full lifecycle:
  1. API health
  2. Authentication (login / me)
  3. Station listing
  4. Synthetic compliance event insertion
  5. Violations listing and detail
  6. Officer action recording
  7. Report generation
  8. Audit ledger (chain integrity)

All against the live Docker services.
"""

import sys
import uuid
import hashlib
import json
import os
import httpx
from sqlalchemy import create_engine, text

CHECKS = []


def check(name, fn):
    try:
        result = fn()
        ok = bool(result) if not isinstance(result, bool) else result
        if ok:
            print(f"  ✅  {name}")
            CHECKS.append((name, True, None))
        else:
            print(f"  ❌  {name}: returned falsy")
            CHECKS.append((name, False, "returned falsy"))
    except Exception as e:
        print(f"  ❌  {name}: {e}")
        CHECKS.append((name, False, str(e)))


def main():
    api = "http://localhost:8000"
    db_url = os.environ.get(
        "DATABASE_URL",
        "postgresql://greenpulse:greenpulse123@localhost:5433/greenpulse_db",
    )

    engine = create_engine(db_url, pool_pre_ping=True)
    client = httpx.Client(timeout=20)
    token = None
    event_id = None

    print()
    print("=" * 60)
    print("  GreenPulse 2.0 — End-to-End Smoke Test")
    print("=" * 60)
    print()
    print("── Infrastructure ───────────────────────────────────────")

    # 1. API Health
    def api_health():
        r = client.get(f"{api}/api/health")
        return r.status_code == 200 and r.json()["status"] == "ok"
    check("API /api/health → 200 OK", api_health)

    # 2. DB connection
    def db_conn():
        with engine.connect() as conn:
            row = conn.execute(text("SELECT 1")).fetchone()
            return row[0] == 1
    check("PostgreSQL connection", db_conn)

    print()
    print("── Authentication ───────────────────────────────────────")

    # 3. Login
    def do_login():
        nonlocal token
        form = {"username": "admin@greenpulse.in", "password": "admin123"}
        r = client.post(f"{api}/api/auth/login", data=form)
        if r.status_code == 200:
            token = r.json()["access_token"]
            return True
        return False
    check("POST /api/auth/login → JWT token", do_login)

    headers = {"Authorization": f"Bearer {token}"} if token else {}

    def get_me():
        r = client.get(f"{api}/api/auth/me", headers=headers)
        return r.status_code == 200 and r.json()["email"] == "admin@greenpulse.in"
    check("GET /api/auth/me → admin profile", get_me)

    print()
    print("── Data Seeding & Stations ─────────────────────────────")

    # 4. Stations
    def stations_listed():
        r = client.get(f"{api}/api/stations/", headers=headers)
        return r.status_code == 200 and len(r.json()) >= 1
    check("GET /api/stations/ → at least 1 station", stations_listed)

    print()
    print("── Compliance Event Lifecycle ──────────────────────────")

    # 5. Insert synthetic compliance event directly into DB
    def insert_event():
        nonlocal event_id
        eid = uuid.uuid4()
        event_id = str(eid)
        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO compliance_events (
                    id, station_id, pollutant, tier, status,
                    observed_value, limit_value, exceedance_percent,
                    averaging_period, rule_name, legal_reference,
                    window_start, window_end
                ) VALUES (
                    :id, 'DL001', 'PM2.5', 'VIOLATION', 'PENDING_OFFICER_REVIEW',
                    120.0, 60.0, 100.0,
                    '24hr', 'PM2.5 24-hr NAAQS', 'CPCB NAAQS 2009',
                    NOW() - INTERVAL '24 hours', NOW()
                )
            """), {"id": eid})
        return True
    check("INSERT synthetic PM2.5 violation (DL001)", insert_event)

    # 6. Violations listing
    def violations_listed():
        r = client.get(f"{api}/api/violations/", headers=headers)
        data = r.json()
        return r.status_code == 200 and data["total"] >= 1
    check("GET /api/violations/ → total >= 1", violations_listed)

    # 7. Violation detail
    def violation_detail():
        r = client.get(f"{api}/api/violations/{event_id}", headers=headers)
        data = r.json()
        return r.status_code == 200 and data["station_id"] == "DL001"
    check("GET /api/violations/{id} → station=DL001", violation_detail)

    # 8. Violations summary
    def violations_summary():
        r = client.get(f"{api}/api/violations/summary", headers=headers)
        data = r.json()
        return r.status_code == 200 and data["total"] >= 1
    check("GET /api/violations/summary → counts", violations_summary)

    print()
    print("── Officer Action ───────────────────────────────────────")

    # 9. Record an officer action
    def record_action():
        payload = {
            "compliance_event_id": event_id,
            "action_type": "ESCALATE",
            "reason": "Smoke test verification — auto-escalated",
            "notes": "Created by smoke_test.py"
        }
        r = client.post(f"{api}/api/actions/", json=payload, headers=headers)
        data = r.json() if r.status_code == 201 else {}
        return r.status_code == 201 and data.get("event_status") == "ESCALATED"
    check("POST /api/actions/ → event status=ESCALATED", record_action)

    print()
    print("── Report Generation ────────────────────────────────────")

    # 10. Generate report
    def gen_report():
        r = client.post(f"{api}/api/reports/generate/{event_id}", headers=headers)
        return r.status_code == 201 and r.json()["html_length"] > 1000
    check("POST /api/reports/generate/{id} → HTML > 1kB", gen_report)

    print()
    print("── Audit Ledger Integrity ───────────────────────────────")

    # 11. Ledger chain
    def ledger_integrity():
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from sqlalchemy.orm import Session
        from ledger.verifier import verify_chain
        db = Session(engine)
        try:
            result = verify_chain(db)
            return result.is_valid
        finally:
            db.close()
    check("audit_ledger hash chain integrity", ledger_integrity)

    # ── Summary ──────────────────────────────────────────────────────────────
    print()
    print("=" * 60)
    passed = sum(1 for _, ok, _ in CHECKS if ok)
    failed = len(CHECKS) - passed
    print(f"  Results: {passed}/{len(CHECKS)} checks passed")
    if failed == 0:
        print("  ✅  ALL CHECKS PASSED — System healthy")
    else:
        print(f"  ❌  {failed} CHECKS FAILED")
        for name, ok, err in CHECKS:
            if not ok:
                print(f"       • {name}: {err}")
    print("=" * 60)

    client.close()
    engine.dispose()

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
