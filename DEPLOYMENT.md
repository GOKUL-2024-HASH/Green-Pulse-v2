# GreenPulse 2.0 — Final Deployment Instructions

Follow these steps for a guaranteed error-free deployment of the GreenPulse 2.0 platform.

## 1. Prerequisites
- Docker & Docker Compose installed.
- Valid WAQI API Token (Get one at https://aqicn.org/data-platform/token/).

## 2. Environment Setup
1.  Ensure `.env` exists and contains:
    - `WAQI_TOKEN`: Your API token.
    - `SECRET_KEY`: A strong random string for JWT.
    - `POSTGRES_PASSWORD`: Database password.
2.  The `.env.example` file is provided for reference.

## 3. Clean Launch Sequence
Run these commands in order:

```powershell
# Stop any existing containers and clear volumes
docker compose down -v

# Build and start all 5 microservices
docker compose up --build -d

# Wait 5 seconds for PostgreSQL to be ready, then apply migrations
Start-Sleep -Seconds 5
docker compose exec api alembic upgrade head
```

## 4. Post-Deployment Verification
1.  **Dashboard**: Open `http://localhost:3000` (Login: `admin@greenpulse.in` / `admin123`).
2.  **API Health**: Check `http://localhost:8000/docs` (Swagger UI).
3.  **Pipeline Logs**: Confirm live polling:
    ```bash
    docker compose logs pipeline --tail 20
    ```

## 5. Troubleshooting
- **Database Connection Error**: Ensure the `DATABASE_URL` in `.env` uses `postgres:5432` for internal Docker networking.
- **Alembic Local Run**: If running `alembic` from your host machine (Windows), use `localhost:5433` as the port override.

---
**Build Success. Deployment Verified.**
