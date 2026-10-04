#!/usr/bin/env bash
# Runs the platform offline (Docker), creates sample projects through the API, clones every generated
# repository to OUT_DIR and validates each CloudFormation template with cfn-lint (AWS resource schemas).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
API="${API:-http://localhost:8010}"
OUT_DIR="${OUT_DIR:-$ROOT/../cloudinfra-generated}"
STATE_DIR="${CLOUDINFRA_STATE_DIR:-$ROOT/var/state}"
OWNER="${GITHUB_OWNER:-acme-platform}"
RUN_ID="$(date +%s)"
FRESH="${1:-}"

cd "$ROOT"
CLOUDINFRA_STATE_DIR="$STATE_DIR" docker compose --profile full up -d --build api worker >/dev/null
until curl -fs "$API/healthz" >/dev/null; do sleep 1; done
if [ "$FRESH" = "--fresh" ]; then
  # Clears generated projects only; reference data (environments, accounts, networks) stays.
  docker compose exec -T db psql -q -U cloudinfra -d cloudinfra -c \
    "TRUNCATE release_decisions, releases, job_steps, jobs, projects RESTART IDENTITY CASCADE;"
  rm -rf "$STATE_DIR/github" "$STATE_DIR/aws"
fi
mkdir -p "$OUT_DIR"

count=$(python3 -c "import json;print(len(json.load(open('scripts/offline/projects.json'))))")
for i in $(seq 0 $((count - 1))); do
  payload=$(python3 -c "import json,sys;print(json.dumps(json.load(open('scripts/offline/projects.json'))[$i]))")
  name=$(python3 -c "import json,sys;print(json.loads(sys.argv[1])['project_name'])" "$payload")
  if [ -d "$STATE_DIR/github/$OWNER/$name-infra.git" ]; then
    echo "• $name: already provisioned"
  else
    job=$(curl -fs -X POST "$API/v1/projects" -H "Content-Type: application/json" \
          -H "Idempotency-Key: offline-$name-$RUN_ID" -d "$payload" | python3 -c "import json,sys;print(json.load(sys.stdin)['job_id'])")
    while :; do
      state=$(curl -fs "$API/v1/jobs/$job" | python3 -c "import json,sys;print(json.load(sys.stdin)['state'])")
      case "$state" in succeeded) break ;; failed|compensated) echo "✗ $name: job $state"; exit 1 ;; esac
      sleep 1
    done
    echo "• $name: provisioned (job $job)"
  fi
  rm -rf "$OUT_DIR/$name-infra"
  git clone -q "$STATE_DIR/github/$OWNER/$name-infra.git" "$OUT_DIR/$name-infra"
done

cp infra/platform/platform.yaml "$OUT_DIR/platform.yaml"
echo
echo "Validating templates with cfn-lint $(cd backend && uv run --quiet cfn-lint --version | awk '{print $2}')"
status=0
for template in "$OUT_DIR"/*-infra/template.yaml "$OUT_DIR/platform.yaml"; do
  if (cd backend && uv run --quiet cfn-lint --format parseable "$template"); then
    echo "  ✓ ${template#$OUT_DIR/}"
  else
    echo "  ✗ ${template#$OUT_DIR/}"; status=1
  fi
done
echo
echo "Repositories: $OUT_DIR"
exit $status
