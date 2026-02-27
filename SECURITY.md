# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 2.0.x   | ✅ Yes     |
| < 2.0   | ❌ No      |

## Reporting a Vulnerability

**Do not open a public GitHub Issue for security vulnerabilities.**

Contact the maintainers privately (see the repository's About section for contact info) with:
- A clear description of the vulnerability
- Steps to reproduce
- Potential impact
- Optional: suggested fix

We aim to acknowledge reports within **48 hours** and provide a remediation timeline within **7 business days**.

## Security Design

| Area | Implementation |
|------|---------------|
| Authentication | JWT Bearer tokens with configurable expiry |
| Password Hashing | `bcrypt` with per-user salts via `passlib` |
| Audit Chain | SHA-256 hash chain — each ledger entry includes a hash of the previous entry; tampering is mathematically detectable |
| Credentials | Never committed — always configured via `.env` (see `.env.example`) |
| RBAC | Role-based access control (officer / supervisor / admin) enforced at the API layer |

## Known Limitations

- The `SECRET_KEY` for JWT signing is a shared symmetric key. For production, rotate regularly and store in a secrets manager (AWS Secrets Manager / HashiCorp Vault).
- The `.env` file must never be committed — it is listed in `.gitignore`.
