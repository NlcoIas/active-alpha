# Security Audit — Active Alpha

Date: 2026-03-29
Auditor: Claude (automated)
Scope: Full-stack application (FastAPI backend + Next.js frontend + PostgreSQL + Redis + Docker + Nginx)

## Summary

- CRITICAL: 0
- HIGH: 2
- MEDIUM: 5
- LOW: 5

No critical vulnerabilities found. Two high-severity issues should be fixed before production deployment.

---

## Findings

### [HIGH] API key comparison vulnerable to timing attacks

- **Location**: `backend/app/dependencies.py:99`
- **Description**: The admin API key is compared using Python's `!=` operator (`x_api_key != settings.admin_api_key`), which is vulnerable to timing side-channel attacks. An attacker can statistically determine the correct key character by character by measuring response times.
- **Recommendation**: Use `secrets.compare_digest()` for constant-time comparison:
  ```python
  import secrets
  if not secrets.compare_digest(x_api_key, settings.admin_api_key):
      raise HTTPException(...)
  ```

### [HIGH] No rate limiting on any public endpoint

- **Location**: `backend/app/main.py` (global), `backend/app/routers/backtests.py:86`
- **Description**: No rate limiting middleware or per-endpoint throttling is configured anywhere in the application. The `POST /api/v1/backtests/run` endpoint is particularly concerning because it runs computationally expensive backtest simulations with no authentication, allowing denial-of-service through resource exhaustion. All other public read endpoints are also unprotected.
- **Recommendation**: Add rate limiting using `slowapi` or a Redis-based limiter. At minimum:
  - `POST /backtests/run`: 5 requests/minute/IP
  - General API reads: 60 requests/minute/IP
  - Pipeline trigger (admin): already auth-gated, but consider rate limiting too

---

### [MEDIUM] FastAPI docs/OpenAPI exposed in production

- **Location**: `backend/app/main.py:90`, `nginx/nginx.conf:30-46`
- **Description**: The FastAPI instance does not disable `docs_url`, `redoc_url`, or `openapi_url`. The Nginx config explicitly proxies `/docs`, `/openapi.json`, and `/redoc` to the backend. This exposes full API documentation in production, giving attackers a complete map of all endpoints, parameters, and schemas.
- **Recommendation**: Conditionally disable docs in production:
  ```python
  docs_url="/docs" if settings.environment != "production" else None,
  redoc_url="/redoc" if settings.environment != "production" else None,
  openapi_url="/openapi.json" if settings.environment != "production" else None,
  ```
  Also remove the `/docs`, `/redoc`, and `/openapi.json` location blocks from the production Nginx config.

### [MEDIUM] SQL echo enabled in development leaks query details

- **Location**: `backend/app/database.py:16`
- **Description**: `echo=settings.environment == "development"` logs all SQL queries to stdout when `ENVIRONMENT=development`. If someone accidentally deploys with `ENVIRONMENT=development` (the config default), all SQL including parameter values will be logged, potentially exposing sensitive data in log aggregation systems.
- **Recommendation**: Default the `environment` setting to `"production"` in `config.py` (line 41), so development mode must be explicitly opted into rather than being the default. Alternatively, tie echo to a separate `DB_ECHO` env var.

### [MEDIUM] f-string used in SQL query construction (code smell)

- **Location**: `backend/app/services/backtest_engine.py:114`
- **Description**: The query uses `text(f"""...{fund_filter}...""")` which inserts a variable into the SQL string via f-string interpolation. While the interpolated value is a hardcoded static string (`"AND f.ticker = ANY(:fund_tickers)"` or `""`), never user data, this pattern is fragile and a maintenance hazard. A future developer could inadvertently interpolate user input.
- **Recommendation**: Refactor to build the SQL string via concatenation of static parts, then wrap in `text()`:
  ```python
  base_sql = "... WHERE d.snapshot_date >= :start_date ..."
  if fund_tickers:
      base_sql += " AND f.ticker = ANY(:fund_tickers)"
      params["fund_tickers"] = fund_tickers
  query = text(base_sql)
  ```
  Or better, use the ORM query builder entirely.

### [MEDIUM] Default database credentials in config defaults

- **Location**: `backend/app/config.py:12-13`
- **Description**: The `database_url` and `database_url_sync` defaults contain `postgres:postgres` credentials. While these are overridden by environment variables in production, if the `.env` file is missing or the env vars are not set, the application will attempt to connect with default credentials. The `docker-compose.yml` also defaults `POSTGRES_PASSWORD` to `postgres` if not set.
- **Recommendation**: Remove default credentials from `config.py` -- make `database_url` a required field with no default, so the app fails fast if not configured. In `docker-compose.yml`, require `POSTGRES_PASSWORD` to be set (remove the `:-postgres` fallback).

### [MEDIUM] Permissions-Policy header not set

- **Location**: `frontend/next.config.ts`, `nginx/nginx.conf`
- **Description**: Neither the Next.js security headers nor the Nginx config set a `Permissions-Policy` header (formerly `Feature-Policy`). This header controls access to browser APIs like camera, microphone, geolocation, etc.
- **Recommendation**: Add to `next.config.ts` security headers:
  ```
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" }
  ```

---

### [LOW] allow_methods and allow_headers wildcards in CORS config

- **Location**: `backend/app/main.py:105-106`
- **Description**: While the `allow_origins` list is correctly restricted to specific domains, `allow_methods` and `allow_headers` use wildcards. This is more permissive than necessary for this application, which only uses GET and POST with standard JSON headers.
- **Recommendation**: Restrict to used methods and headers:
  ```python
  allow_methods=["GET", "POST", "OPTIONS"],
  allow_headers=["Content-Type", "X-API-Key"],
  ```

### [LOW] Backtest endpoint has no authentication

- **Location**: `backend/app/routers/backtests.py:86-87`
- **Description**: `POST /api/v1/backtests/run` is a public, unauthenticated endpoint that triggers database queries and CPU-intensive computation (pandas/numpy simulation). Beyond rate limiting (covered above), consider whether this should require some form of lightweight auth or CAPTCHA.
- **Recommendation**: At minimum, add rate limiting (see HIGH finding above). Optionally, add a lightweight auth mechanism or require a session token.

### [LOW] Health endpoint exposes version information

- **Location**: `backend/app/routers/health.py:27`
- **Description**: The `/health` endpoint returns `{"status": "ok", "version": "0.1.0"}`. Exposing the application version can help attackers identify known vulnerabilities for that specific version.
- **Recommendation**: Remove the version field from the health endpoint response, or restrict it to authenticated requests.

### [LOW] No request correlation (X-Request-ID)

- **Location**: `backend/app/main.py` (global)
- **Description**: The application does not generate or propagate request IDs. This makes it harder to trace malicious requests through logs and correlate attack patterns across the Nginx, FastAPI, and database layers.
- **Recommendation**: Add middleware that generates a UUID for each request and includes it in the response headers and all log messages.

### [LOW] Frontend Dockerfile has unused build stage

- **Location**: `frontend/Dockerfile:1-8`
- **Description**: Stage 1 (`deps`) runs `npm ci --only=production` but these dependencies are never copied into the final image -- Stage 2 (`builder`) runs `npm ci` again with all deps. The `deps` stage is dead code. This is not a security risk per se, but unnecessary stages increase build surface.
- **Recommendation**: Remove the unused `deps` stage from the frontend Dockerfile.

---

## Passed Checks

### Secrets/Credentials
- No hardcoded secrets in source code (API keys read from env vars via pydantic-settings)
- `.env`, `.env.local`, `.env.production` are all in `.gitignore`
- `.env.example` uses placeholder values only (`your_fmp_api_key_here`, `your_admin_api_key_here`)
- `.env.production.example` uses `CHANGE_ME` placeholders appropriately
- No `.env` files found in the project directory

### Input Validation
- All API endpoints use Pydantic v2 schemas with field constraints (`ge`, `le`, `Literal`)
- All query parameters use FastAPI `Query()` with validation constraints
- Backtest config validates all fields with ranges and literal types
- All database access uses SQLAlchemy ORM or parameterized `text()` queries
- No string concatenation of user data into SQL
- No f-string SQL injection patterns found

### Authentication/Authorization
- Admin pipeline endpoints (`POST /pipeline/run`, `GET /pipeline/runs`) protected with `require_api_key` dependency
- API key validated from `X-API-Key` header
- Server returns 503 if admin key not configured (fail-closed)
- No sensitive data (passwords, tokens, internal IDs) exposed in API responses

### Docker Security
- Both Dockerfiles use non-root users (`appuser` for backend, `nextjs` for frontend)
- Multi-stage builds minimize attack surface
- No secrets in Dockerfiles
- Health checks present in both Dockerfiles
- PostgreSQL port not exposed to host (uses `expose` not `ports`)
- Redis port not exposed to host
- Only Nginx port 80 exposed to host

### Security Headers (Next.js)
- `X-Frame-Options: DENY` set
- `X-Content-Type-Options: nosniff` set
- `Referrer-Policy: strict-origin-when-cross-origin` set
- CSP configured with appropriate directives
- `unsafe-eval` only allowed in development mode
- No HSTS in Next.js config (correct -- Cloudflare owns it at edge)

### Security Headers (Nginx)
- `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy` set as defense-in-depth

### CORS
- Not wildcard -- explicit origin allowlist: `localhost:3000` (dev) and `alpha.nicolasschaerer.ch` (prod)
- `allow_credentials=True` correctly paired with specific origins

### Error Handling
- Global exception handler catches all unhandled exceptions and returns generic "Internal server error"
- No stack traces exposed to clients
- HTTP exceptions return standardized `ErrorResponse` shape
- Logger records full exception details server-side only

### Path Traversal / Command Injection
- No file system access or process spawning in router code
- No file upload endpoints
- No user-controlled file paths

### Frontend Security
- No unsafe HTML rendering found
- No dynamic code evaluation found
- API client uses `fetch` with JSON serialization (no raw HTML injection risk)
- All API parameters constructed via `URLSearchParams` (proper encoding)

### Dependencies
- Python dependencies (`requirements.txt`): All mainstream, well-maintained packages. No known critical CVEs for the pinned minimum versions.
- Node dependencies (`package.json`): All mainstream packages (Next.js 16, React 19, Zod 4, shadcn 4). No known critical CVEs.
- No unnecessary or suspicious dependencies in either stack.
