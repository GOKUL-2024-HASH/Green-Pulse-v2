# Changelog

All notable changes to GreenPulse 2.0 are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [2.0.1] - 2026-02-27

### Fixed
- **Critical:** Corrected `Station.station_id` → `Station.id` typo in `api/main.py` seeder that silently rolled back all DB seeding on startup, leaving `stations` table empty after every volume wipe.
- **Critical:** Pathway daemon thread (`pw.run()`) was silently crashing in Docker, preventing rolling-window emission. Resolved with a real-time SQL `AVG()` fallback computing 1hr/8hr/24hr windows inside the APScheduler poll job.
- `bcrypt` downgraded `4.1.2` → `4.0.1` to fix `passlib==1.7.4` incompatibility causing 401 Unauthorized on all logins.
- Removed null-byte UTF-16 encoding corruption from `.gitignore`.

---

## [2.0.0] - 2026-02-26

### Added
- **Live WAQI Data Ingestion:** Pipeline polls the World Air Quality Index API every 5 minutes for 5 monitoring stations across Delhi and Mumbai.
- **Pathway 0.29.1 Streaming Engine:** Temporal sliding-window graph (`pw.io.python.ConnectorSubject`, `pw.stdlib.temporal.sliding`, `pw.reducers.avg`) computing 1hr, 8hr, and 24hr rolling averages.
- **NAAQS 2009 Compliance Classifier:** Three-tier classification (MONITOR → FLAG → VIOLATION) for PM2.5, PM10, NO2, SO2, CO, O3 against CPCB limits.
- **Immutable SHA-256 Audit Ledger:** Cryptographic hash chain for tamper-proof regulatory records.
- **FastAPI Backend:** JWT authentication, RBAC (admin/officer), RESTful endpoints for violations, officer actions, stations, and PDF reports.
- **React 18 Dashboard:** Live-refreshing KPI cards, violations table, Recharts trend charts, officer intervention panel.
- **5-Container Docker Orchestration:** api, dashboard, pipeline, postgres, redis via `docker-compose.yml`.
- **Alembic Migrations:** Automated schema versioning.
- **APScheduler Integration:** Replaces manual `while/sleep` loop with structured interval scheduling.
- **Automated DB Seeding:** Admin user and 5 monitoring stations seeded on fresh deployments.
