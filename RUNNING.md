# Running GreenPulse 2.0

## Prerequisites
- Docker Desktop ≥ 24.x running
- `.env` file configured (copy from `.env.example`)

---

## Starting the System

```bash
# Build and start all 5 containers in the background
docker compose up --build -d

# Apply database schema migrations
docker compose exec api alembic upgrade head
```

Dashboard: http://localhost:3000  
API Docs:  http://localhost:8000/docs

**Default login:** `admin@greenpulse.in` / `admin123`

---

## Useful Commands

```bash
# View logs for a specific service
docker compose logs pipeline --follow
docker compose logs api --follow

# Check container health
docker compose ps

# Connect to the database directly
docker compose exec postgres psql -U greenpulse -d greenpulse_db

# Run the test suite
docker compose exec api pytest tests/ -v

# Stop all containers (keeps data)
docker compose down

# Stop + wipe all data volumes (fresh start)
docker compose down -v
```

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Login returns 401 | Run `docker compose down -v && docker compose up -d && docker compose exec api alembic upgrade head` to reseed |
| Dashboard shows no data | Wait 5–10 min for the first pipeline poll cycle, or check `docker compose logs pipeline` |
| Migration fails | Ensure postgres container is healthy: `docker compose ps` |
