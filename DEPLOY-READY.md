# Deploy Readiness — Active Alpha

Date: 2026-03-29
Status: **READY**

## Checklist

| Check | Status |
|-------|--------|
| Backend Dockerfile (multi-stage, non-root, healthcheck, curl) | PASS |
| Frontend Dockerfile (multi-stage, standalone, non-root, healthcheck) | PASS |
| docker-compose.yml (nginx + frontend + backend + db + redis) | PASS |
| nginx reverse proxy config (/api/* → backend, /* → frontend) | PASS |
| `output: "standalone"` in next.config.ts | PASS |
| Security headers (CSP, X-Frame, Referrer, Permissions-Policy — NO HSTS) | PASS |
| `.env.example` and `.env.production.example` complete | PASS |
| No hardcoded secrets in source | PASS |
| Alembic migrations present (`d7e897fc076a_initial_schema`) | PASS |
| `npm run build` passes (frontend) | PASS |
| Backend imports successfully | PASS |
| CORS: explicit origin allowlist (not wildcard) | PASS |
| Rate limiting on backtest endpoint (5/min/IP) | PASS |
| API key comparison uses `secrets.compare_digest()` | PASS |
| FastAPI docs disabled in production | PASS |
| DNS CNAME exists (alpha.nicolasschaerer.ch → tunnel) | PASS |
| Deploy script configured for docker-compose on nginx:80 | PASS |

## Architecture

```
[Browser] → [Cloudflare Tunnel] → [nginx:80]
    ├── /api/*     → [backend:8000] (FastAPI)
    ├── /health    → [backend:8000]
    └── /*         → [frontend:3000] (Next.js)
```

## Remaining Non-Blocking Items

- MEDIUM: Default DB credentials in config (overridden by env vars in production)
- LOW: No request correlation headers
- LOW: CORS methods/headers could be more restrictive
