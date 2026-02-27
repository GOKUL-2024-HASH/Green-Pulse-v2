# GreenPulse 2.0 — Enterprise Air Quality Compliance
> **Intelligent Monitoring. Immutable Auditing. Regulatory Excellence.**

GreenPulse 2.0 is a next-generation regulatory platform designed for environmental authorities. It transforms raw sensor data into actionable legal evidence, ensuring that air quality violations are detected, classified, and processed with absolute integrity.

---

## 🛠️ Technology Stack

### **Frontend**
- **React 18**: Modern, responsive dashboard.
- **Recharts**: Dynamic charting for compliance trends.
- **Axios**: Global JWT management for secure API communication.

### **Backend**
- **FastAPI**: High-performance Python 3.11 web framework.
- **JWT & RBAC**: Role-Based Access Control (Admin/Officer).
- **SQLAlchemy & Alembic**: Robust ORM with automated schema migrations.

### **Data & Infrastructure**
- **PostgreSQL**: Primary relational storage.
- **Redis**: Low-latency caching.
- **Docker Compose**: Full orchestration of 5 microservices.

---

## 📐 System Architecture

<!-- 
ARCHITECTURAL DIAGRAM SPACE 
(Insert Mermaid or Image here)
-->

The system operates as a continuous real-time loop:
1.  **Ingestion**: Pipeline polls WAQI API every 5 minutes.
2.  **Rolling Windows**: Values are buffered into 1h, 8h, and 24h averages.
3.  **Classification**: Readings are checked against CPCB NAAQS 2009 limits.
4.  **Audit Ledger**: Every event is hashed into an immutable chain.

---

## 🚀 Quick Start (Docker)

1.  **Clone the Repository**
2.  **Configure Environment**
    ```bash
    cp .env.example .env
    # Add your WAQI_TOKEN and other secrets
    ```
3.  **Fire up the Microservices**
    ```bash
    docker compose up --build -d
    ```
4.  **Apply Database Migrations**
    ```bash
    docker compose exec api alembic upgrade head
    ```
5.  **Access the Dashboard**
    Navigate to `http://localhost:3000`
    - **User**: `admin@greenpulse.in`
    - **Pass**: `admin123`

---

## 📄 Documentation
For detailed deployment steps and technical notes, see [DEPLOYMENT.md](./DEPLOYMENT.md).

---
**GreenPulse 2.0** — *Engineering a Cleaner Future, One Byte at a Time.*
