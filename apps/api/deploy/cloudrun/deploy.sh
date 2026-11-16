#!/usr/bin/env bash
set -euo pipefail

PROJECT="${GCP_PROJECT:?set GCP_PROJECT}"
REGION="${REGION:-asia-southeast1}"
SERVICE="${SERVICE:-naktahu-api}"
ENV_FILE="${ENV_FILE:-.env.cloudrun}"
API_DIR="$(cd "$(dirname "$0")/../.." && pwd)"

SECRET_VARS=(
  ANTHROPIC_API_KEY DATABASE_URL ILMU_API_KEY JWT_SECRET LANGSMITH_API_KEY
  METRICS_AUTH_TOKEN NEMOTRON_API_KEY OPENAI_API_KEY REDIS_URL RESEND_API_KEY
  SUPABASE_SECRET_KEY SUPABASE_SERVICE_ROLE_KEY TAVILY_API_KEY WANDB_API_KEY
)
PLAIN_VARS=(
  CORS_ORIGINS ELIGIBILITY_USE_NEMOTRON EMBEDDING_PROFILE EMBEDDING_WRITE_PROFILES ENV
  ILMU_BASE_URL ILMU_CHAT_MODEL ILMU_EMBEDDING_MODEL LANGSMITH_PROJECT
  NEMOTRON_FAST_MODEL NEMOTRON_REASONING_MODEL RESEND_FROM_EMAIL
  SUPABASE_STORAGE_BUCKET SUPABASE_URL WANDB_PROJECT
)

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

gcloud config set project "$PROJECT" >/dev/null
gcloud services enable run.googleapis.com secretmanager.googleapis.com \
  cloudbuild.googleapis.com artifactregistry.googleapis.com

PROJECT_NUMBER="$(gcloud projects describe "$PROJECT" --format='value(projectNumber)')"
RUNTIME_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

SECRET_FLAGS=()
for name in "${SECRET_VARS[@]}"; do
  value="${!name:-}"
  if [[ -z "$value" ]]; then
    echo "missing $name in $ENV_FILE" >&2
    exit 1
  fi
  secret_id="naktahu-$(echo "$name" | tr '[:upper:]_' '[:lower:]-')"
  if gcloud secrets describe "$secret_id" >/dev/null 2>&1; then
    printf '%s' "$value" | gcloud secrets versions add "$secret_id" --data-file=- >/dev/null
  else
    printf '%s' "$value" | gcloud secrets create "$secret_id" --data-file=- >/dev/null
  fi
  gcloud secrets add-iam-policy-binding "$secret_id" \
    --member="serviceAccount:${RUNTIME_SA}" \
    --role=roles/secretmanager.secretAccessor >/dev/null
  SECRET_FLAGS+=("${name}=${secret_id}:latest")
done

PLAIN_FLAGS=""
for name in "${PLAIN_VARS[@]}"; do
  value="${!name:-}"
  if [[ -z "$value" ]]; then
    echo "missing $name in $ENV_FILE" >&2
    exit 1
  fi
  PLAIN_FLAGS+="@${name}=${value}"
done

# '^@^' makes '@' the delimiter, because CORS_ORIGINS contains commas.
# Memory 1Gi matches Railway's measured ~0.6 GB for two uvicorn workers plus headroom.
# --cpu-boost shortens the cold start caused by importing LangChain/LangGraph.
gcloud run deploy "$SERVICE" \
  --source "$API_DIR" \
  --region "$REGION" \
  --allow-unauthenticated \
  --memory 1Gi \
  --cpu 1 \
  --cpu-boost \
  --min-instances "${MIN_INSTANCES:-0}" \
  --max-instances "${MAX_INSTANCES:-3}" \
  --concurrency 40 \
  --timeout 300 \
  --port 8080 \
  --set-env-vars "^@^${PLAIN_FLAGS#@}" \
  --set-secrets "$(IFS=,; echo "${SECRET_FLAGS[*]}")"
