#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SEED_DIR="$SCRIPT_DIR/seed"
API_DIR="$REPO_ROOT/apps/api"

usage() {
  echo "Usage: $0 [--live] [--domain DOMAIN] [--dry-run]"
  echo ""
  echo "  --live          Fetch live gov sources before ingesting (default: seed CSVs only)"
  echo "  --domain NAME   Filter to a specific domain (tax|epf|business|education|health|immigration)"
  echo "  --dry-run       Show what would be done without executing"
  echo ""
  echo "Requires: OPENAI_API_KEY, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY in apps/api/.env"
}

LIVE=false
DOMAIN=""
DRY_RUN=false

while [[ $# -gt 0 ]]; do
  case $1 in
    --live)     LIVE=true; shift ;;
    --domain)   DOMAIN="$2"; shift 2 ;;
    --dry-run)  DRY_RUN=true; shift ;;
    -h|--help)  usage; exit 0 ;;
    *) echo "Unknown option: $1"; usage; exit 1 ;;
  esac
done

load_env() {
  if [ -f "$API_DIR/.env" ]; then
    set -a
    # shellcheck disable=SC1090
    source "$API_DIR/.env"
    set +a
  fi
}

load_env

echo "=== NakTahu AI — Ingest Pipeline ==="
echo "Seed dir : $SEED_DIR"
echo "Live fetch: $LIVE"
echo "Domain   : ${DOMAIN:-all}"
echo "Dry run  : $DRY_RUN"
echo ""

# Step 1: optional live fetch
if [ "$LIVE" = true ]; then
  FETCH_CMD="python '$SCRIPT_DIR/fetch_gov_docs.py'"
  [ -n "$DOMAIN" ] && FETCH_CMD="$FETCH_CMD --domain $DOMAIN"
  [ "$DRY_RUN" = true ] && FETCH_CMD="$FETCH_CMD --dry-run"
  echo "--- Fetching live sources ---"
  eval "$FETCH_CMD"
  echo ""
fi

# Step 2: ingest seed CSVs into Supabase via apps/api ingest script
if [ "$DRY_RUN" = true ]; then
  echo "--- [dry-run] Would ingest CSVs from: $SEED_DIR ---"
  ls "$SEED_DIR"/*.csv 2>/dev/null || echo "(no CSV files found)"
  exit 0
fi

echo "--- Ingesting seed CSVs ---"
cd "$API_DIR"

INGEST_CMD="python -m scripts.ingest --dir '$SEED_DIR'"
[ -n "$DOMAIN" ] && {
  case "$DOMAIN" in
    tax)         FILE="lhdn_tax.csv" ;;
    epf)         FILE="kwsp_epf.csv" ;;
    business)    FILE="ssm_business.csv" ;;
    education)   FILE="kpm_education.csv" ;;
    health)      FILE="moh_health.csv" ;;
    immigration) FILE="imi_immigration.csv" ;;
    *)           echo "Unknown domain: $DOMAIN"; exit 1 ;;
  esac
  INGEST_CMD="python -m scripts.ingest --file '$SEED_DIR/$FILE'"
}

eval "$INGEST_CMD"

echo ""
echo "=== Done. All chunks uploaded to Supabase. ==="
