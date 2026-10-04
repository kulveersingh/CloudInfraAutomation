# CloudInfraAutomation

Self-service platform that turns a selection of AWS services into a CloudFormation template, a GitHub repository
and a deployment pipeline, with tag-based isolation, DR/HA across any region pair and approvals for STAGE/PROD.
Design: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) (Word version in `docs/`).

## Layout

| Path | What |
|---|---|
| `backend/` | Python 3.12 FastAPI API, synthesis engine, provisioning worker (one image, two ECS services) |
| `frontend/` | React + TypeScript console (Vite), served by nginx on ECS |
| `infra/platform/platform.yaml` | CloudFormation for the platform on AWS: ECS Fargate + Aurora PostgreSQL + ALB |
| `mock-ui/` | Clickable design mock (invented data) |
| `docs/` | Architecture, diagrams, approval flows |

## Run locally (Docker Desktop)

Everything runs offline: GitHub and AWS are replaced by local adapters that create real git repositories under
`var/github/` and record bootstrap stacks under `var/aws/`.

**Option A — everything in containers (mirrors ECS):**

```bash
docker compose --profile full up -d --build
open http://localhost:8080          # console; API on http://localhost:8010
```

**Option B — from source (for development):**

```bash
docker compose up -d db                              # PostgreSQL 16 (Aurora PostgreSQL compatible)
cd backend
uv sync
uv run alembic upgrade head && uv run python -m app.seed
LOCAL_STATE_DIR=../var uv run uvicorn app.main:app --port 8010          # API
LOCAL_STATE_DIR=../var uv run python -m app.provisioning.worker         # worker (second terminal)
cd ../frontend && npm install && npm run dev                            # console on http://localhost:5173
```

Port 8010 is used for the API because 8000 is often taken on developer machines.

## Tests (TDD, 100% coverage enforced)

```bash
cd backend && uv run pytest            # needs the db container; fails below 100% line+branch coverage
cd frontend && npm test                # Vitest; fails below 100% coverage
```

## Deploy the platform to AWS

1. Build and push `backend/` and `frontend/` images to ECR (ARM64).
2. Deploy `infra/platform/platform.yaml` with your VPC, private subnets, ACM certificate and image URIs.
3. The API task runs migrations and seeds reference data on start; open the `ConsoleUrl` output.

GitHub App and AWS adapters for real accounts are the next phase; until then the stack runs in `local` mode.

## Offline end-to-end run and template validation

Runs the platform in Docker, creates sample projects (single region, DR, HA, no-VPC and schema-driven
services incl. Aurora PostgreSQL) through the API, clones every generated repository and validates
each CloudFormation template with cfn-lint against the AWS resource schemas (no AWS account needed).

```bash
./scripts/offline/run-and-validate.sh --fresh   # --fresh clears earlier generated projects
ls ../cloudinfra-generated                      # one working clone per generated repo + platform.yaml
```

Sample projects are in `scripts/offline/projects.json`. Generated bare repositories live in
`var/state/github` (override with `CLOUDINFRA_STATE_DIR`, clones with `OUT_DIR`).

With AWS credentials (`aws login` or SSO), the same templates can also be checked by the CloudFormation API;
this creates nothing:

```bash
./scripts/offline/validate-with-aws.sh
```
