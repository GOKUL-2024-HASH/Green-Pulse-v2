# Contributing to GreenPulse 2.0

Thank you for your interest in contributing!

---

## Development Setup

### Prerequisites
- Docker Desktop ≥ 24.x
- Python 3.11+
- Node.js 18+
- A [WAQI API token](https://aqicn.org/api/)

### Steps

```bash
git clone https://github.com/GOKUL-2024-HASH/Green-Pulse-v2.git
cd Green-Pulse-v2
cp .env.example .env
# Edit .env – add WAQI_API_TOKEN, SECRET_KEY
docker compose up --build -d
docker compose exec api alembic upgrade head
# Dashboard at http://localhost:3000  (admin@greenpulse.in / admin123)
```

---

## Branching Strategy

| Branch | Purpose |
|--------|---------|
| `main` | Stable production-ready code |
| `feature/<name>` | New features |
| `fix/<name>` | Bug fixes |
| `chore/<name>` | Tooling / docs |

---

## Pull Request Process

1. One PR per feature/fix.
2. Reference any related issues: `Closes #<number>`.
3. All CI checks must pass before review.
4. Request at least one maintainer review.

---

## Code Standards

### Python (api / pipeline)
- PEP 8 + `black` formatting. Max line length 120.
- All public functions must have docstrings and type hints.
- No bare `except:` — always catch specific exceptions.

```bash
black api/ pipeline/
flake8 api/ pipeline/ --max-line-length=120
```

### JavaScript (dashboard)
- Functional components + React Hooks only.
- Follow ESLint rules in `dashboard/.eslintrc`.

---

## Running Tests

```bash
docker compose exec api pytest tests/ -v
docker compose exec api pytest tests/ --cov=api --cov-report=term-missing
```

---

## Reporting Bugs

Open a GitHub Issue with version, reproduction steps, expected vs actual behaviour, and relevant `docker compose logs <service>` output.
