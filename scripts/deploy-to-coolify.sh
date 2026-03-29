#!/usr/bin/env bash
set -euo pipefail

# ─── Deploy Active Alpha to Coolify ────────────────────────────────────────
# Updates the existing Coolify app (alpha) to point to NlcoIas/active-alpha
# and configures it for docker-compose deployment.
#
# The docker-compose stack is self-contained: backend + db + redis.
# The DB runs inside the compose stack (not the standalone alpha-db).
#
# Prerequisites:
#   - ~/claude/websites/coolify/.env.coolify exists
#   - GitHub repo NlcoIas/active-alpha exists and is pushed
#   - Existing Coolify app UUID: rau2gjhl9fp16k2w49i2cqlb
#
# Usage: ./scripts/deploy-to-coolify.sh [--dry-run]
# ─────────────────────────────────────────────────────────────────────────

DRY_RUN=false
for arg in "$@"; do
  case $arg in
    --dry-run) DRY_RUN=true ;;
  esac
done

# ─── Load Coolify config ────────────────────────────────────────────────────
COOLIFY_ENV="$HOME/claude/websites/coolify/.env.coolify"
if [ ! -f "$COOLIFY_ENV" ]; then
  echo "Error: $COOLIFY_ENV not found"
  exit 1
fi
source "$COOLIFY_ENV"

API="$COOLIFY_API_URL"
AUTH="Authorization: Bearer $COOLIFY_TOKEN"

APP_UUID="rau2gjhl9fp16k2w49i2cqlb"

api_get() {
  curl -sf -H "$AUTH" -H "Content-Type: application/json" "$API$1"
}

api_patch() {
  if [ "$DRY_RUN" = true ]; then
    echo "  [DRY RUN] PATCH $1"
    echo "  [DRY RUN] Body: $(echo "$2" | head -c 200)"
    return 0
  fi
  curl -sf -X PATCH -H "$AUTH" -H "Content-Type: application/json" -d "$2" "$API$1"
}

echo "═══════════════════════════════════════════════════"
echo "  Active Alpha → Coolify Deploy"
echo "  App UUID: $APP_UUID"
if [ "$DRY_RUN" = true ]; then
  echo "  Mode: DRY RUN"
fi
echo "═══════════════════════════════════════════════════"

# ─── Step 1: Update app to point to new repo ────────────────────────────────
echo ""
echo "→ Step 1: Update git repository to NlcoIas/active-alpha..."
api_patch "/applications/$APP_UUID" '{
  "git_repository": "NlcoIas/active-alpha",
  "git_branch": "master",
  "build_pack": "dockercompose",
  "docker_compose_location": "/docker-compose.yml",
  "base_directory": "/"
}' > /dev/null 2>&1 || true
echo "  Done."

# ─── Step 2: Update domain routing to nginx on port 80 ───────────────────────
echo ""
echo "→ Step 2: Set docker_compose_domains → nginx:80..."
api_patch "/applications/$APP_UUID" '{
  "docker_compose_domains": {"nginx": {"domain": "http://alpha.nicolasschaerer.ch"}},
  "ports_exposes": "80"
}' > /dev/null 2>&1 || true
echo "  Domain: http://alpha.nicolasschaerer.ch → nginx:80"
echo "  nginx routes: /api/* → backend:8000, /* → frontend:3000"
echo "  (Cloudflare Tunnel handles HTTPS)"

# ─── Step 3: Set environment variables ───────────────────────────────────────
echo ""
echo "→ Step 3: Setting environment variables..."

# Generate secrets
DB_PASSWORD=$(openssl rand -base64 32 | tr -d '=+/' | head -c 32)
ADMIN_KEY=$(openssl rand -base64 32 | tr -d '=+/' | head -c 32)

ENV_DATA=$(cat <<ENDJSON
{"data": [
  {"key": "DATABASE_URL", "value": "postgresql+asyncpg://alpha:${DB_PASSWORD}@db:5432/active_alpha", "is_literal": true},
  {"key": "DATABASE_URL_SYNC", "value": "postgresql+psycopg2://alpha:${DB_PASSWORD}@db:5432/active_alpha", "is_literal": true},
  {"key": "POSTGRES_DB", "value": "active_alpha", "is_literal": true},
  {"key": "POSTGRES_USER", "value": "alpha", "is_literal": true},
  {"key": "POSTGRES_PASSWORD", "value": "${DB_PASSWORD}", "is_literal": true},
  {"key": "REDIS_URL", "value": "redis://redis:6379/0", "is_literal": true},
  {"key": "FMP_API_KEY", "value": "${FMP_API_KEY:-SET_ME}", "is_literal": true},
  {"key": "ADMIN_API_KEY", "value": "${ADMIN_KEY}", "is_literal": true},
  {"key": "ENVIRONMENT", "value": "production", "is_literal": true},
  {"key": "LOG_LEVEL", "value": "INFO", "is_literal": true}
]}
ENDJSON
)

api_patch "/applications/$APP_UUID/envs/bulk" "$ENV_DATA" > /dev/null 2>&1 || true
echo "  DATABASE_URL: postgresql+asyncpg://alpha:***@db:5432/active_alpha"
echo "  REDIS_URL: redis://redis:6379/0"
echo "  ADMIN_API_KEY: (generated)"
echo "  ENVIRONMENT: production"
echo ""
echo "  IMPORTANT: Set FMP_API_KEY manually in Coolify if not in env."

# ──�� Step 4: Trigger deployment ──────────────────────────────────────────────
echo ""
echo "→ Step 4: Triggering deployment..."
if [ "$DRY_RUN" = true ]; then
  echo "  [DRY RUN] Would deploy $APP_UUID"
else
  DEPLOY_RESULT=$(api_get "/deploy?uuid=$APP_UUID&force=true")
  DEPLOY_UUID=$(echo "$DEPLOY_RESULT" | python3 -c "
import sys, json
d = json.load(sys.stdin)
deploys = d.get('deployments', [])
print(deploys[0]['deployment_uuid'] if deploys else '')
" 2>/dev/null || echo "")

  if [ -n "$DEPLOY_UUID" ]; then
    echo "  Deployment triggered: $DEPLOY_UUID"
  else
    echo "  Warning: Could not auto-trigger. Deploy manually from Coolify dashboard."
  fi
fi

# ─── Step 5: Verify (after deploy completes) ────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════"
echo "  Deployment prepared for Active Alpha"
echo ""
echo "  Live URL:  https://alpha.nicolasschaerer.ch"
echo "  Health:    https://alpha.nicolasschaerer.ch/health"
echo "  Ready:     https://alpha.nicolasschaerer.ch/ready"
echo "  API docs:  https://alpha.nicolasschaerer.ch/docs"
echo ""
echo "  After deploy completes, verify:"
echo "    curl -s https://alpha.nicolasschaerer.ch/health"
echo "    curl -s https://alpha.nicolasschaerer.ch/ready"
echo "═══════════════════════════════════════════════════"
