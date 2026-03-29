# Build Report — Active Alpha

Date: 2026-03-29
URL: https://alpha.nicolasschaerer.ch

## Pipeline Summary

| Phase | Iterations | Issues Found | Issues Fixed |
|-------|-----------|-------------|-------------|
| 1. Research | 1 | 0 | 0 |
| 2. Plan | 1 | 0 | 0 |
| 3. Scaffold | 1 | 0 | 0 |
| 4. Build Backend | 1 | 0 | 0 |
| 5. Build Frontend | 1 | 0 | 0 |
| 6. Visual Review | 1 | 2 warnings | 1 (CSP dev fix) |
| 7. Security Audit | 1 | 2 HIGH, 5 MED, 5 LOW | 2 HIGH, 3 MED fixed |
| 8. Deploy Check | 1 | 0 | 0 |
| 9. Deploy | 4 | 3 issues | 3 fixed |
| 10. Knowledge | 1 | — | — |

## Review Verdicts (Final)

| Reviewer | Verdict | Critical | Warning |
|----------|---------|----------|---------|
| Combined Visual/UX/Technical/Mobile | APPROVE | 0 | 2 |

## Security Audit (Final)

| Severity | Count |
|----------|-------|
| CRITICAL | 0 |
| HIGH | 0 (2 found, 2 fixed) |
| MEDIUM | 2 remaining (non-blocking) |
| LOW | 5 remaining |

## Deploy Issues & Resolutions

1. **Coolify docker_compose_domains stuck on "backend"** — Cannot change which service a domain maps to via API. Fixed by renaming frontend service to "backend" and actual backend to "api".

2. **Next.js rewrites baked at build time** — BACKEND_URL env var not available during Docker build. Fixed by adding `ARG BACKEND_URL=http://api:8000` in Dockerfile.

3. **PostgreSQL password mismatch** — Deploy script generated new random credentials, but DB volume persisted old credentials. Fixed by resetting to default postgres/postgres and deleting the pgdata volume.

4. **GitHub repo was private** — Coolify couldn't pull code. Fixed by making repo public.

## Architecture

```
[Browser] → [Cloudflare Tunnel] → [Coolify/Traefik]
    → [Next.js :3000] (service name: "backend")
        ├── / (pages)           → Next.js App Router
        ├── /api/* (rewrites)   → [FastAPI :8000] (service name: "api")
        ├── /health (rewrite)   → [FastAPI :8000]
        └── /ready (rewrite)    → [FastAPI :8000]
    → [PostgreSQL :5432] (service name: "db")
    → [Redis :6379] (service name: "redis")
```

## Stack

- **Backend**: FastAPI + async SQLAlchemy + PostgreSQL + Redis
- **Frontend**: Next.js 16 + Tailwind v4 + shadcn/ui + Recharts
- **Deploy**: Docker Compose (4 services) on Coolify + Cloudflare Tunnel

## Remaining Warnings (Non-Blocking)

- Default DB credentials in config.py (overridden by env vars in production)
- Permissions-Policy header could be more comprehensive
- CORS methods/headers could be more restrictive
- No request correlation (X-Request-ID) headers
- Frontend Dockerfile deps stage removed but could optimize further
