# CloudInfraAutomation — Architecture

**Status:** v2.31, approved; implementation in progress. No code is written until this design is approved.
**Date:** 2026-10-05
**Scope:** A web feature where a user selects their **Portfolio → Product/Platform** (the project is the repo they are creating) and the AWS services they need. The platform then generates a CloudFormation template and a GitHub Actions pipeline, creates a new **infrastructure repository**, and deploys the stack through a series of **environments, each in its own AWS account**. The environments and their account numbers are **configurable in the application** (default set: Sandbox, DEV, TEST, QA/STAGE, PROD). What each project can touch in AWS is controlled by **tags**: a project can never change another project's resources. Developers deploy their own code (Python, Java, Go, Rust, …) to ECS, Lambda, EKS and Step Functions from separate **application repositories** that read a published infrastructure contract (§9). Every solution is **DR-capable**: it can run in one region, as DR (primary active, secondary standby) or as an HA pair (both active), with **any region pair chosen in the UI** (default us-east-1 / us-east-2) (§10).

**Changes in v2:** added the org registry and tagging strategy (§4); permissions based on tags (§4.5–4.8); multi-account, five-environment model (§5); promotion pipeline (§8). Payload, provisioning, security and scaling sections are updated to match.
**Changes in v2.31:** MC-3c: the Google Cloud landing-zone deployments in Terraform JSON, inputs, seed script, workflow and README, validated with Terraform 1.5.7 (§22.10 notes).
**Changes in v2.30:** MC-3b: the Google Cloud landing-zone design: provider answers, project ids, folders and projects, the control snapshot and pack mappings, checks and advice, templates per cloud (§22.10 notes).
**Changes in v2.29:** MC-3a: neutral landing-zone answers with provider answers, pack mappings per cloud, unit naming from the provider, one landing zone per cloud (§22.10 notes).
**Changes in v2.28:** MC-3 design (§22.10): the Google Cloud landing zone (folders, project factory, Org Policy/IAM deny/SCC pack mappings, Shared VPC with an NCC star topology, VPC Service Controls per environment, vault project), and the neutral split of landing-zone answers and control packs.
**Changes in v2.27:** MC-2e: the UI picks the cloud (wizard, Admin regions and networks), follows the chosen cloud's regions, catalog, type search, networks, words and main file, and shows preview notes; MC-2 is complete (§22.9.7 notes).
**Changes in v2.26:** MC-2d: Google Cloud release risk from Terraform plans; teardown inventory from the configuration; Bucket-Locked and Backup and DR vault backups in the vault project; restore with import (§22.9.7 notes).
**Changes in v2.25:** MC-2c: Google Cloud provisioning, read-back and Change infrastructure end to end; ownership labels through a per-provider tag policy; deployments named `cloudinfra-{project}-{region}`; removal wording in change previews (§22.9.7 notes).
**Changes in v2.24:** MC-2b implemented: Google Cloud Terraform JSON generation with curated services, exact-resource bindings, Eventarc triggers, lint against the provider schema, preview notes and the Infrastructure Manager workflow (§22.9.7 notes).
**Changes in v2.23:** MC-2 design (§22.9): Google Cloud projects on Terraform JSON and Infrastructure Manager, Workload Identity Federation, exact-resource IAM, locked-bucket teardown backups, and a cloud picker.
**Changes in v2.22:** multi-cloud (§22): a cloud-neutral core with AWS, Google Cloud and Azure provider plug-ins; native IaC per cloud; neutral service kinds, control packs and backup strategies; phased delivery.
**Changes in v2.21:** teardown (§21.9): remove an environment or decommission a project, backup-first into a vault locked for 60 days (deleted only manually by super users), with a teardown record and restore.
**Changes in v2.20:** Change infrastructure for projects (§21.8): edit a read-back project in the wizard; the platform opens a pull request with the regenerated, signed files and records the new revision when it is merged.
**Changes in v2.19:** service settings (§6.4.1): each curated block declares its settings, which are validated, used as defaults and shown as fields in the Services step.
**Changes in v2.18:** read-back (§21): generated repositories carry a signed manifest, so the platform can verify a repo is its own, detect hand edits and load the design back into the UI for editing.
**Changes in v2.17:** implementation started. The control plane runs on ECS Fargate with Aurora PostgreSQL (§2.2a), and the same containers run locally on Docker Desktop.
**Changes in v2.16:** cost centers are admin-configurable for the whole organization (§4.2.1): an org default, then per portfolio, per product and optional project overrides, with inheritance, validation, audit and automatic re-tagging.
**Changes in v2.15:** Appendix A (§19): a complete set of approval and workflow diagrams (landscape, release in default mode, release decision flow, override, sharing routing, access request, infrastructure change request, configuration change, DR failover, recertification, application release) plus an approval summary table.
**Changes in v2.14:** all sharing is granted through a sharing approval workflow (§4.11.6). Covers share offers, access requests, agreements, renewal and revocation, with risk-based routing, optional auto-approval within an approved tag offer, recertification and audit.
**Changes in v2.13:** sharing by tags (§4.11.1). Providers set `org:share-scope` (product / portfolio / organization) and `org:share-access` on a resource, and any consumer in any account whose tags match (same environment, inside the organization) can connect self-service. Agreements remain for everything tags cannot express.
**Changes in v2.12:** cross-account access (§4.11). Infrastructure can use assets in other AWS accounts (S3, SQS, SNS, KMS, DynamoDB, secrets, events, private APIs) through approved sharing agreements. Both sides are generated with tag conditions, inside the organization by default, with expiry, revocation and audit.
**Changes in v2.11:** any region pair is allowed. Users pick the primary and secondary regions in the UI (pre-filled with us-east-1 / us-east-2). Admins manage enabled regions in the UI. Adds per-pair availability and replication checks, us-east-1 placement for CloudFront certificates/WAF, and region changes after creation (§10.9).
**Changes in v2.10:** runtime isolation by tags (§4.10). Every component can only talk to resources with the same project and environment tag values, enforced by four layers generated into the template: the runtime role's policy, the permissions boundary, a same-tag resource policy on the target, and an SCP.
**Changes in v2.9:** multi-region resilience (§10): every template is DR-capable. Projects choose single region, DR (deployed to us-east-1 and us-east-2, only us-east-1 active) or HA pair (both active). Adds per-service replication rules, a global stack, a two-region pipeline, failover/failback, DR drills and a multi-region control plane. Sections 10–17 renumbered to 11–18.
**Changes in v2.8:** the catalog now covers every project-scoped AWS service, including all major databases, in every combination (§6.8). It is generated from AWS's own schemas and authorization data, with curated secure blocks for common services, generic connection kinds, database defaults (network, Secrets Manager credentials, RDS Proxy, snapshots), layered stacks, and pairwise + real-deploy testing.
**Changes in v2.7:** runtime infrastructure is AWS services only; email notifications use Amazon SES (no SMTP option).
**Changes in v2.6:** technology policy added: AWS + GitHub + open source only (§1). Commercial products removed or replaced (CMDB/ITSM, chat tools, paid GitHub security features). Approvals now work on any GitHub plan via platform-executed releases (§8.3.1); GitHub Enterprise features are optional.
**Changes in v2.5:** infrastructure and solution code are now explicitly independent (§9.9): contract-first development, placeholder artifacts, expand → migrate → contract changes, optional bindings, local/ephemeral testing, and a responsibilities table. Product teams no longer have to sign off on infrastructure changes.
**Changes in v2.4:** added developer consumption (§9): infrastructure contract published per environment, application repos linked to compute slots, golden-path build/deploy workflows per language and compute type (Lambda, ECS, EKS, Step Functions), and least-privilege application deploy roles. Sections 9–16 renumbered to 10–17.
**Changes in v2.3:** STAGE and PROD require GitHub reviewer approval before deployment, using a plan → approve → apply-reviewed-change-set flow that cannot be turned off (§8.3). Added a layered quality-gate strategy for STAGE and PROD (§8.4). Added the release console: promotion and approval workflow in the platform UI, with approvals submitted to GitHub as the reviewer (§8.5).
**Changes in v2.2:** the hierarchy is now three levels, Portfolio → Product/Platform → Project. The team level and the `org:team` tag are removed.
**Changes in v2.1:** environment names, their order and their AWS account numbers can now be configured by platform admins in the application (§5.5). Nothing about environments is hardcoded.

---

## Contents

1. [Goals, non-goals and design principles](#1-goals-non-goals-and-design-principles)
2. [System architecture](#2-system-architecture)
3. [Request payload and data model](#3-request-payload-and-data-model)
4. [Org registry, tagging strategy and tag-based permissions](#4-org-registry-tagging-strategy-and-tag-based-permissions)
5. [Multi-account environment strategy](#5-multi-account-environment-strategy)
6. [CloudFormation generation engine](#6-cloudformation-generation-engine)
7. [GitHub repository provisioning](#7-github-repository-provisioning)
8. [Deployment pipeline (GitHub Actions + OIDC, configurable environments)](#8-deployment-pipeline-github-actions--oidc-configurable-environments)
9. [Developer consumption: application repositories](#9-developer-consumption-application-repositories)
10. [Multi-region resilience: DR and HA](#10-multi-region-resilience-dr-and-ha)
11. [Security model](#11-security-model)
12. [Scalability and multi-tenancy](#12-scalability-and-multi-tenancy)
13. [Error handling, idempotency and rollback](#13-error-handling-idempotency-and-rollback)
14. [Observability](#14-observability)
15. [Where an LLM fits (and where it must not)](#15-where-an-llm-fits-and-where-it-must-not)
16. [Proposed repository layout](#16-proposed-repository-layout)
17. [Decisions needed from you](#17-decisions-needed-from-you)
18. [Implementation phases](#18-implementation-phases)
19. [Appendix A: Approval and workflow diagrams](#19-appendix-a-approval-and-workflow-diagrams)
20. [Landing zone workflow: AWS Organizations OU structure with Control Tower controls](#20-landing-zone-workflow-aws-organizations-ou-structure-with-control-tower-controls)
21. [Read-back: editing generated repositories in the UI](#21-read-back-editing-generated-repositories-in-the-ui)
22. [Multi-cloud: one platform for AWS, Google Cloud and Azure](#22-multi-cloud-one-platform-for-aws-google-cloud-and-azure)

---

## 1. Goals, non-goals and design principles

### Goals
- A user picks their Portfolio → Product/Platform from dropdowns, names the project, selects services (for example, a Python Lambda triggered by an S3 bucket), and gets a working repository deployed in one click.
- **Tags decide what a project may touch.** Every resource is tagged with its portfolio, product, project and environment. The IAM roles a project uses can only create resources with *their own* tags and can only change resources that already carry *their own* tags.
- **Configurable environments, one account each:** environments (default: Sandbox, DEV, TEST, QA/STAGE, PROD) and their unique AWS account numbers are managed in the application by platform admins. A project is promoted through them in the configured order by a gated pipeline, using the same built artifact each time.
- Generated infrastructure is **least-privilege by construction**: no `*` actions or `*` resources in any IAM role the app template creates.
- Each push safely updates the existing stack, nothing is replaced unless intended, and failures are cleaned up or clearly reported.
- Supports many portfolios, products and projects at once without hitting GitHub or AWS API limits.

### Non-goals (v1)
- Free-form CloudFormation authoring. Users compose from a catalog that covers **every project-scoped AWS resource type** (curated Tier 1 + schema-driven Tier 2, §6.8); account- and organization-wide resources are excluded.
- Creating new AWS accounts from the project wizard. The landing zone (AWS Organizations OUs, Control Tower controls, policies) is managed by a **separate admin-only workflow** (§20); projects only *use* its accounts.
- Editing the Portfolio/Product lists in this UI. They come from the org registry (§4.2), which is the master; maintained in the platform admin screen or imported via CSV/REST.

### Design principles
| Principle | What it means here |
|---|---|
| **Tags are the permission boundary, names are the backstop** | Permissions are written once, using tag conditions, and reused by every project. **At runtime, components can only talk to resources with the same project and environment tag values**, enforced on both the caller's role and the target's resource policy (§4.10). Resource names are still prefixed by project, as a second line of defense for AWS actions that don't support tag conditions. |
| **The platform owns the tags, not the repo** | The tag values a project may use are fixed on its IAM roles by the platform. A user who edits the repo to claim another product's tags is denied by AWS. |
| **Account per environment** | PROD is separated from everything else by an account boundary, not just by tags. |
| **Build once, deploy many** | The same artifact (zip + template) moves DEV → TEST → STAGE → PROD. Only parameters change per environment. |
| **Deterministic over generative** | Templates and IAM come from a versioned, tested catalog of building blocks, never from free-form LLM output. |
| **Short-lived credentials everywhere** | OIDC for GitHub Actions → AWS, GitHub App installation tokens, STS AssumeRole between accounts. No long-lived keys by default. |
| **Infrastructure and solution code are independent** | Every solution has two parts: infrastructure (platform-owned) and solution code (product-owned). They live in separate repos with separate pipelines, versions, release schedules and approvals, joined only by a versioned contract. Neither team waits for the other (§9.9). |
| **Async and safe to retry** | Long-running provisioning is orchestrated as a series of steps, each safe to repeat (keyed by the request ID), with undo steps for anything that fails partway. |

### Technology policy: AWS + GitHub + open source only

The platform is built **in-house**. Its only commercial dependencies are the two systems it exists to automate: **AWS** (the target cloud, including its native services) and **GitHub** (source control and Actions). Every other component is either written by us or is **open-source software**. No other commercial product, SaaS or paid add-on is required.

**AWS services only for runtime infrastructure:** everything the platform runs on, and everything it creates, is an AWS service: compute, storage, database, workflow, email (Amazon SES), secrets, monitoring. No non-AWS infrastructure (mail servers, self-hosted databases, external SaaS) is created or required.

**Rules:**
- No feature may *require* a paid GitHub tier. Features that only exist on GitHub Enterprise are **optional add-ons**, and every one of them has a built-in equivalent (§8.3.1).
- Integrations with commercial tools (chat, ITSM, CMDB, portals) are **never required**. The platform exposes **generic, signed outgoing webhooks and a REST API**, so an organization can connect any tool it likes without the platform depending on it.
- Open-source licenses allowed by default: Apache-2.0, MIT, BSD, MPL-2.0; LGPL as unmodified libraries. AGPL and "source-available" licenses (BSL, SSPL, Elastic, the Semgrep Rules License, etc.) are excluded unless approved (D26).

**Open-source components chosen:**

| Purpose | Choice | License |
|---|---|---|
| Backend API / models | FastAPI, pydantic | MIT |
| GitHub client / AWS SDK / secret encryption | PyGithub, boto3, PyNaCl | LGPL-3.0 (library), Apache-2.0, Apache-2.0 |
| Web UI | React, TypeScript | MIT, Apache-2.0 |
| CloudFormation lint / policy | cfn-lint, cfn-guard | MIT-0, Apache-2.0 |
| IaC security scan | Checkov | Apache-2.0 |
| Gate policy engine (G4/G5 rules as code) | Open Policy Agent (OPA) / Conftest | Apache-2.0 |
| SAST per language | bandit (Python), SpotBugs + Find Security Bugs (Java), gosec (Go), cargo-audit + clippy (Rust), eslint-plugin-security (Node.js) | Apache-2.0 / LGPL-2.1 / Apache-2.0 / Apache-2.0+MIT / Apache-2.0 |
| Dependency / vulnerability scanning | OSV-Scanner, Trivy | Apache-2.0 |
| SBOM | Syft | Apache-2.0 |
| Secret scanning (PR check + pre-commit hook) | gitleaks | MIT |
| Artifact signing and provenance | cosign (Sigstore) **with keys in AWS KMS** (no dependency on public Sigstore services); SLSA/in-toto provenance format | Apache-2.0 |
| Kubernetes GitOps / admission policy | Argo CD, Kyverno | Apache-2.0 |
| Local AWS emulation | moto (server mode), AWS SAM CLI; LocalStack **Community** edition optional | Apache-2.0 |
| Telemetry | OpenTelemetry (export to CloudWatch/X-Ray) | Apache-2.0 |
| Developer portal (optional) | Backstage | Apache-2.0 |
| Dependency update PRs | Dependabot (built into GitHub, free on all plans); Renovate as an alternative if license approved | — / AGPL-3.0 |

**Removed or replaced compared with earlier drafts:**

| Earlier mention | Replaced by |
|---|---|
| ServiceNow / external CMDB as source of truth | **Platform registry is the master**, with CSV/REST import (§4.2) |
| ITSM change tickets | **Built-in change record** in the release console (§8.5); external ITSM optional via outgoing webhook |
| Slack / Microsoft Teams notifications | **In-app inbox** + **email via Amazon SES** + optional generic **signed webhooks** |
| CodeQL (needs paid GitHub Advanced Security for private repos) | Language SAST tools above |
| GitHub secret scanning push protection (paid for private repos) | gitleaks in PR checks and pre-commit hooks |
| GitHub artifact attestations (paid for private repos) | cosign + AWS KMS signatures, verified by the gate |
| GitHub environment required reviewers / custom deployment protection rules (Enterprise for private repos) | **Built-in approval with platform-executed release** (§8.3.1); GitHub features used additionally only if available |

---

## 2. System architecture

### 2.0 Architecture overview

![Architecture overview](diagrams/architecture-overview.png)

The numbered flows are explained under the diagram. A Word version of this whole document, with all diagrams, is in [CloudInfraAutomation-Architecture.docx](CloudInfraAutomation-Architecture.docx).

### 2.1 Component diagram

```mermaid
flowchart LR
  subgraph Client["Client"]
    UI["Web UI (React)<br/>Portfolio → Product/Platform dropdowns<br/>service catalog · connections · preview"]
  end

  subgraph Platform["Platform account (Infrastructure OU)"]
    direction TB
    API["Project API<br/>(stateless, behind ALB/API GW + SSO)"]
    REG[("Org registry + environment config<br/>portfolios · products ·<br/>environments · account bindings · entitlements")]
    SYN["Synthesis engine<br/>catalog → template + code + workflow"]
    VAL["Validation gate<br/>schema · cfn-lint · cfn-guard ·<br/>IAM & tag linter"]
    SFN["Orchestrator<br/>(Step Functions, undo-on-failure)"]
    WRK["Step workers"]
    DDB[("Jobs & idempotency<br/>DynamoDB")]
    WH["Webhook receiver<br/>workflow_run · deployment"]
  end

  subgraph Shared["Shared Services account"]
    ART[("Artifact bucket per region<br/>immutable, org-readable by project tag")]
  end

  subgraph Org["AWS Organizations"]
    SCP["SCPs + Tag Policies<br/>(per OU)"]
    SS["StackSets<br/>account bootstrap → all workload accounts"]
  end

  subgraph Accounts["Workload accounts (one per environment)"]
    SBX["Sandbox"]
    DEV["DEV"]
    TST["TEST"]
    STG["QA/STAGE"]
    PRD["PROD"]
  end

  subgraph GitHub["GitHub"]
    GHAPI["REST / GraphQL API"]
    REPO["New repo + 5 environments"]
    GHA["Actions runner"]
  end

  UI --> API
  API <--> REG
  API --> SYN --> VAL
  API --> SFN --> WRK
  API <--> DDB
  WRK <--> DDB
  WRK -->|"installation token"| GHAPI --> REPO
  WRK -->|"AssumeRole → project bootstrap (tagged roles)"| Accounts
  REPO --> GHA
  GHA -->|"upload once"| ART
  GHA -->|"OIDC per environment → deploy"| Accounts
  Accounts -->|"read code (tag-scoped)"| ART
  SS --> Accounts
  SCP -. guardrails .-> Accounts
  GHAPI -->|"webhooks"| WH --> DDB
  REG -. "sync allowed values" .-> SCP
```

### 2.2 End-to-end sequence

```mermaid
sequenceDiagram
  autonumber
  actor U as User
  participant UI as Web UI
  participant API as Project API
  participant REG as Org registry
  participant SF as Orchestrator
  participant GH as GitHub
  participant ENV as Env accounts (SBX/DEV/TEST/STAGE/PROD)
  participant GA as GitHub Actions

  UI->>API: GET /v1/org-registry (filtered by user's entitlements)
  API->>REG: portfolios → products the user may use
  U->>UI: Pick Portfolio and Product/Platform, name project, select Lambda + S3, connect S3 → Lambda
  UI->>API: POST /v1/projects:preview
  API->>REG: check selection + resolve account per environment
  API-->>UI: files + resolved tags + target accounts per environment
  U->>UI: "Create Repository & Deploy"
  UI->>API: POST /v1/projects (Idempotency-Key)
  API-->>UI: 202 {jobId}
  API->>SF: StartExecution
  SF->>GH: 1. create repo (custom properties = ownership tags)
  par for each environment account
    SF->>ENV: 2. project bootstrap: tagged deploy role + exec role (trust: this repo + this env only)
  end
  SF->>GH: 3. create one GitHub environment per enabled env (protection rules) + repo/env variables
  SF->>GH: 4. one atomic commit
  GH->>GA: push to main
  GA->>ENV: build once → DEV → TEST → (approval) STAGE → (approval) PROD
  GH-->>SF: deployment / workflow_run webhooks → status per environment
  SF-->>UI: repo URL, run URL, status for each environment
```

### 2.2a Implementation decision: control plane on ECS + Aurora PostgreSQL

**Decided at implementation start:** the platform's own control plane runs on **ECS Fargate** (api, worker and ui services) with **Aurora PostgreSQL Serverless v2** as its database, deployed by `infra/platform/platform.yaml`. This replaces DynamoDB and Step Functions for the control plane:
- the job queue and saga state live in PostgreSQL (`FOR UPDATE SKIP LOCKED`);
- the worker service runs provisioning steps with undo-on-failure;
- registry, cost centers, jobs and audit are relational tables, migrated with Alembic.

The same containers run locally with Docker Desktop (PostgreSQL 16) for development and testing. Generated customer infrastructure is unaffected: it still uses any AWS service via CloudFormation.

### 2.3 Component responsibilities

| Component | Responsibility | Scaling |
|---|---|---|
| **Web UI** | Cascading ownership dropdowns, service catalog, connection editor, preview (files, tags, target accounts), job status per environment. | Static on CDN |
| **Project API** | Authentication, entitlement checks, validation, preview, job creation, idempotency. Keeps no state between requests. | Horizontal containers |
| **Org registry** | Source of the Portfolio → Product/Platform tree, projects, cost centers, entitlements, allowed tag values. | DynamoDB + cache; master data, CSV/REST import |
| **Environment config** | Admin-managed list of environments (name, order, tier, protection and guardrail profiles) and **account bindings** (environment + portfolio/product + region → AWS account ID). Validates and onboards accounts before they can be used (§5.5). | DynamoDB, versioned, audited |
| **Synthesis engine** | Payload → template, starter code, workflow, per-environment parameter files. Pure function with no I/O. | Runs in-process |
| **Validation gate** | Schema, connection rules, cfn-lint, cfn-guard (rules differ per environment), IAM least-privilege + tag linter. | Runs in-process |
| **Orchestrator** | Provisioning steps across GitHub and up to five accounts, with retries and undo steps. | Worker ECS service + PostgreSQL job queue (§2.2a) |
| **Org guardrails** | SCPs and Tag Policies attached to OUs, enforcing the tag rules no matter which tool makes the call. | AWS Organizations |
| **StackSets** | Deploy the *account bootstrap* (OIDC provider, shared tag-based policies, provisioner role) to every workload account automatically, including new ones. | Service-managed StackSets |
| **Artifact bucket** | One per region in Shared Services. Workload accounts can read only their project's prefix. | S3 |

### 2.4 API surface (contract only)

| Method & path | Purpose |
|---|---|
| `GET /v1/org-registry` | Portfolio → Product/Platform tree, **filtered to what the caller is entitled to**. Drives the dropdowns. |
| `GET /v1/catalog` | Services that can be selected, their settings and valid connections. |
| `GET /v1/environments` | Active environments in promotion order (read-only for normal users). |
| `GET/POST/PUT /v1/admin/environments` | **Admin:** create, rename (display name), reorder, set profiles, deactivate environments. |
| `GET/POST/PUT/DELETE /v1/admin/account-bindings` | **Admin:** map an AWS account ID to an environment for a portfolio/product/region. |
| `POST /v1/admin/account-bindings/{id}:validate` | **Admin:** run the onboarding checks (§5.5.3) and report the result. |
| `POST /v1/projects:preview` | Validate + synthesize, no side effects. Returns files, resolved tags and target accounts per environment. |
| `POST /v1/projects` | Start provisioning (`Idempotency-Key` required) → 202 `{jobId}`. |
| `GET /v1/jobs/{jobId}` / `…/events` | Job + per-environment status (JSON / SSE). |
| `GET /v1/projects/{id}/releases` | Release console: pipeline view and history per environment (§8.5). |
| `GET /v1/approvals?mine=true` | Reviewer's approval inbox. |
| `POST /v1/approvals/{id}:approve` / `:reject` | Approve/reject in the UI; the platform submits it to GitHub as the reviewer. |
| `POST /v1/projects/{id}/environments/{env}:promote` | Start promotion when the environment is in `on-request` mode. |
| `POST /v1/overrides` / `POST /v1/overrides/{id}:decide` | Request / decide a high-risk change override. |
| `GET /v1/shareable-resources` | Catalog of resources other projects have marked shareable (§4.11). |
| `POST /v1/sharing-requests` | Create a sharing request: share offer, access request, agreement, renewal or revocation (§4.11.6). |
| `GET /v1/sharing-requests?mine=true` / `POST /v1/sharing-requests/{id}:approve` / `:reject` | Sharing approval inbox and decisions. |
| `POST /v1/github/webhooks` | GitHub App webhooks. |

---

## 3. Request payload and data model

### 3.1 Design choices
- **Ownership by ID, not by name:** the UI sends registry IDs (`pf-…`, `pr-…`). The server checks them against the registry *and* the user's entitlements. **The UI is never trusted for ownership.**
- **No account IDs in the payload.** The server works out the target account for each environment from the admin-configured account bindings (§5.5). Users cannot point a deploy at an account they don't own.
- **Graph-shaped:** `resources` (nodes) and `connections` (edges). Permissions and event wiring come from the edges, so the user never writes IAM.
- **Stable IDs supplied by the user** become logical IDs and part of physical names; stable IDs are what make updates safe.

### 3.2 Example — Python Lambda + S3, owned by Payments → Invoicing → AP Automation

```json
{
  "schemaVersion": "2.0",
  "requestId": "6f1c2a9e-4b7d-4a52-9d55-0d1f2b3c4e5f",
  "catalogVersion": "2026.10.0",
  "project": {
    "name": "invoice-ingest",
    "description": "Process invoices dropped into S3",
    "github": { "owner": "acme-platform", "visibility": "private" }
  },
  "ownership": {
    "portfolioId": "pf-payments",
    "productId": "pr-invoicing",
    "dataClassification": "confidential"
  },
  "environments": {
    "enabled": ["sandbox", "dev", "test", "stage", "prod"],
    "region": "us-east-1"
  },
  "resilience": {
    "mode": "dr",
    "primaryRegion": "us-east-1",
    "secondaryRegion": "us-east-2",
    "drStrategy": "pilot-light",
    "targets": { "rtoMinutes": 60, "rpoMinutes": 5 }
  },
  "resources": [
    { "id": "uploads", "type": "s3.bucket",
      "config": { "versioning": true, "expireNoncurrentDays": 30 } },
    { "id": "processor", "type": "lambda.python",
      "config": { "runtime": "python3.13", "architecture": "arm64", "starterCode": "s3-event-logger" } }
  ],
  "connections": [
    { "kind": "s3.notify", "source": "uploads", "target": "processor",
      "config": { "events": ["s3:ObjectCreated:*"], "prefix": "incoming/" } }
  ],
  "environmentOverrides": {
    "prod":    { "processor": { "memoryMb": 512, "reservedConcurrency": 50 } },
    "sandbox": { "*": { "retainOnDelete": false } }
  },
  "deploy": { "auth": "oidc" }
}
```

What the server adds before synthesis (shown in the preview, read-only):

```json
{
  "resolvedTags": {
    "org:portfolio": "pf-payments",
    "org:product": "pr-invoicing",
    "org:project": "invoice-ingest",
    "org:cost-center": "CC-4410",
    "org:data-classification": "confidential",
    "org:managed-by": "cloudinfra"
  },
  "targets": {
    "sandbox": { "accountId": "111111111111", "region": "us-east-1" },
    "dev":     { "accountId": "222222222222", "region": "us-east-1" },
    "test":    { "accountId": "333333333333", "region": "us-east-1" },
    "stage":   { "accountId": "444444444444", "region": "us-east-1" },
    "prod":    { "accountId": "555555555555", "region": "us-east-1" }
  }
}
```

`org:environment` is added per account at deploy time (§4.3).

### 3.3 Schema rules (enforced by the validation gate)

| Field | Rule | Reason |
|---|---|---|
| `ownership.*Id` | Must exist in the registry; product must belong to the portfolio; user must be entitled to the product | Stops users from claiming someone else's product. |
| `ownership.dataClassification` | ≤ the product's classification ceiling; `restricted` data not allowed in `sandbox` | Classification gates are enforced in SCPs too (§4.7). |
| `environments.enabled` | Subset of the **active configured** environments that have an onboarded account binding for this product; must include every environment the configuration marks as a required gate before a later one (e.g. `prod` requires `stage`); order comes from the configuration, not the payload | Promotion integrity. |
| `project.name` | `^[a-z][a-z0-9]*(-[a-z0-9]+)*$`, 3–30 chars, no `--`, **unique within the GitHub org and across the registry** | `org:project` must identify exactly one project. `--` is reserved as the name separator. |
| `resources[].id` | `^[a-z][a-z0-9-]{0,19}$`, unique | Logical ID + physical name. |
| `len(project.name) + len(id)` for S3 | ≤ 31 | Bucket name `{project}--{id}-{account}-{region}` must stay ≤ 63 chars. |
| `resilience` | `mode` ∈ single/dr/ha, allowed by the environment's policy; `primaryRegion` / `secondaryRegion`: **any two different regions** from the platform's region list, chosen in the UI (pre-filled with us-east-1 / us-east-2); every selected service must be available in both regions; in HA every data store must support active/active (§10.3, §10.9) | DR-capable from the start; impossible combinations are rejected early. |
| `environmentOverrides` | Only settings the catalog marks as overridable, within per-environment ranges (e.g. prod log retention ≥ 90 days) | Environments differ in size, not in shape. |
| Connections | Source/target must exist; the pair of types must be allowed; no overlapping S3 notifications; no write access to a bucket that also triggers the same function on an overlapping prefix | Correctness + stops S3 ↔ Lambda infinite loops. |

**Catalog:**
- **Resource types:** any project-scoped AWS resource type. Tier 1 curated (including all major database engines) and Tier 2 schema-driven; see §6.8.
- **Connection kinds:** generic kinds (`iam.access`, `network.access`, `event.source`, `event.notify`, `event.rule`, `api.route`, `workflow.task`, `secret.binding`, `cdn.origin`) that work across services (§6.8.4). The example payload's `s3.notify` is the S3-specific form of `event.notify`.

### 3.4 Persistent model (DynamoDB, single table)

| Entity | PK | SK | Key attributes |
|---|---|---|---|
| Organization settings | `CFG#ORG` | `META` | **default cost center**, cost center format rule, version |
| Portfolio | `REG#PORTFOLIO` | `PF#{id}` | displayName, status, owner group, **costCenter** (optional; inherits the org default) |
| Product/Platform | `REG#PF#{portfolioId}` | `PR#{id}` | displayName, kind (`product`\|`platform`), costCenter (optional; inherits the portfolio's), classification ceiling, allowed envs, entitled IdP groups, GitHub access team (repo maintain role), GitHub reviewer teams per env |
| Environment | `CFG#ENV` | `ENV#{envId}` | displayName, order, tier, OU, required-gate flag, protection profile, guardrail profile, status, version |
| Account binding | `CFG#BIND#{envId}` | `{scope}#{scopeId}#{region}` | accountId, status (`pending`/`onboarded`/`failed`/`retired`), last validation result, version |
| Account index (uniqueness) | `CFG#ACCT#{accountId}` | `META` | envId. Written in the same transaction as the binding, so **one account ID can belong to only one environment** |
| Project | `PROJECT#{name}` | `META` | ownership IDs, repo ID, enabled envs, bootstrap stack IDs per env, catalog version |
| Job | `JOB#{jobId}` | `META` / `STEP#{n}#{name}#{env}` | state, per-step / per-env status, errors, undo state |
| Idempotency | `IDEMP#{requestId}` | `META` | jobId, payloadHash |

Job states: `ACCEPTED → REPO_CREATED → AWS_BOOTSTRAPPED(per env) → ACTIONS_CONFIGURED → COMMITTED → PROMOTING → SUCCEEDED | DEPLOY_FAILED(env) | FAILED_ROLLED_BACK | FAILED_NEEDS_ATTENTION`.

---

## 4. Org registry, tagging strategy and tag-based permissions

### 4.1 Hierarchy and how each level is used

Three levels: **Portfolio → Product/Platform → Project**. Who may act for a product (repo access, approvers, human AWS access) comes from IdP/GitHub groups attached to the product in the registry; it is not a level in the hierarchy and not a tag.

```mermaid
flowchart TD
  PF["Portfolio<br/>pf-payments"] --> PR1["Product<br/>pr-invoicing"]
  PF --> PR2["Platform<br/>pl-payments-core"]
  PR1 --> P1["Project / repo<br/>invoice-ingest"]
  PR1 --> P2["Project / repo<br/>invoice-ocr"]
  PR2 --> P3["Project / repo<br/>ledger-api"]
```

| Level | Used for | Used in IAM permissions? |
|---|---|---|
| **Portfolio** | Cost roll-up, portfolio-level guardrails, account routing (§5.2) | Guardrail SCPs only (e.g. "this account only accepts portfolio X") |
| **Product / Platform** | Cost, entitlements (who may create projects), optional sharing between projects in the same product | Yes, for opt-in sharing within a product (§4.6) |
| **Project** | **The main isolation boundary.** One repo = one project = one set of roles per environment | **Yes, always** |
| **Environment** | Which account / stage | Yes: must equal the account's environment |

**Default isolation:** a project can create, change and delete only resources tagged with its own `org:project`. Sharing within the same product is opt-in and read-only by default. Sharing across products is never automatic.

### 4.2 Org registry → UI dropdowns
- **Source of truth:** the **platform registry is the master**, maintained in the platform admin screen. Bulk changes can be imported via CSV or the REST API (so any existing inventory can feed it), but no external product is required. The UI never hardcodes the lists.
- **Cascading dropdowns:**
  - **Portfolio:** only portfolios where the user has at least one entitled product.
  - **Product/Platform:** filtered by the chosen portfolio *and* the user's IdP groups. Shows a badge for kind (Product or Platform).
  - **Project:** a new name typed by the user (validated for format and uniqueness, §3.3), not a dropdown.
  - **Resilience:** single region / DR / HA pair; then **Primary region** and **Secondary region** dropdowns listing every region the platform has enabled, pre-filled with us-east-1 / us-east-2 (§10.9).
- **Read-only fields shown after selection:** cost center (resolved, with where it comes from, §4.2.1), classification ceiling, and target account per environment (from the account bindings). The user sees exactly where the project will deploy.
- **Server-side re-check** on preview and on create (registry + entitlement). This guards against a stale UI and against crafted requests.
- **IDs are immutable; display names can change.** Tag values are IDs (`pr-invoicing`), so renaming "Invoicing" to "AP Invoicing" changes nothing in AWS.
- **Lifecycle:** retiring a product blocks new projects, flags existing ones and does not delete anything.

#### 4.2.1 Cost centers (admin-configurable for the whole organization)

Platform admins maintain cost centers in the admin screen (**Admin → Cost centers**). Nothing is hardcoded and nothing comes from an external finance system unless imported.

| Level | Set by | Rule |
|---|---|---|
| **Organization default** | Platform admin | Required. Used when nothing more specific is set |
| **Portfolio** | Platform admin | Optional. Overrides the org default for everything in the portfolio |
| **Product / Platform** | Platform admin | Optional. Overrides the portfolio value for that product |
| **Project override** | Requested in the project; approved by a platform admin (finance) | Optional, for exceptions (e.g. a project funded by another budget) |

- **Resolution:** the effective cost center is project override → product → portfolio → org default. The UI always shows the resolved value and **where it comes from** (e.g. "CC-4400 · inherited from Payments").
- **Validation:** a format rule set in organization settings (default `^CC-[0-9]{4}$`). Values can also be bulk-imported by CSV/REST, with the same validation.
- **Propagation:** changing a cost center opens **tag-update PRs** on every affected infrastructure repo. Normal deploys update the stack tags, and CloudFormation re-tags the resources. Nothing is re-tagged by hand. The admin screen shows how many projects a change affects before saving.
- **Governance:** every change is versioned and audited (who, when, old → new). Tag Policies (§4.7) get the list of valid cost centers automatically. `org:cost-center` is activated as a cost allocation tag, so Cost Explorer and the CUR report spend per cost center.
- **Permissions:** cost centers are billing metadata, not a security boundary. They are never used in IAM conditions (§4.5), so changing one never affects access.


### 4.3 Tag schema

The key prefix `org:` is a placeholder; choose your company prefix (D3). All values are registry IDs or validated slugs.

| Key | Example | Set by | Required | Used for |
|---|---|---|---|---|
| `org:portfolio` | `pf-payments` | Platform (from registry) | Yes | Cost, guardrails |
| `org:product` | `pr-invoicing` | Platform | Yes | Cost, sharing within a product |
| `org:project` | `invoice-ingest` | Platform | Yes | **Primary permission key** |
| `org:environment` | `dev` | Platform (per account) | Yes | Must match the account's environment |
| `org:cost-center` | `CC-4410` | Platform (resolved from the cost center hierarchy, §4.2.1) | Yes | Billing (activated as a cost allocation tag) |
| `org:data-classification` | `confidential` | User (≤ product ceiling) | Yes | SCP gates (e.g. not in sandbox) |
| `org:managed-by` | `cloudinfra` | Platform | Yes | Marks resources only the platform pipeline may change |
| `org:share-scope` | `none` / `product` / `portfolio` / `organization` | Provider (UI, via infra PR) | No (default `none`) | **Sharing by tags**: who outside the project may use the resource, across accounts (§4.11.1) |
| `org:share-access` | `read` / `readwrite` / `invoke` / `publish` / `consume` | Provider (UI, via infra PR) | No (default `read`) | What shared consumers may do (§4.11.1) |
| `org:share-approval` | `required` (default) / `auto` | Provider (UI, approved offer) | No | Whether each consumer access request needs the provider's approval or is auto-approved within the tag rule (§4.11.6) |
| `org:resilience` | `dr` | Platform (project setting) | Yes | Reporting, cost, DR drill scheduling (§10) |
| `org:region-role` | `primary` / `secondary` | Platform (per region) | Yes | Operations and failover tooling (§10) |
| `org:expires-on` | `2026-11-01` | Platform (sandbox only) | Sandbox only | Automatic cleanup in sandbox |

**Where the tags are recorded:**

| Location | Tags | Purpose |
|---|---|---|
| IAM roles the platform creates per project per env (deploy role, CFN execution role) | All `org:*` keys | **These role tags are the source of truth.** Inside IAM policies they are read as `aws:PrincipalTag/...`. |
| CloudFormation stack tags | Same values, passed by the pipeline | Propagated by CloudFormation to every resource that supports tags. AWS only accepts them if they **match the role's own tags** (§4.5). |
| GitHub repo custom properties | portfolio, product, project | Discovery, rulesets, audit. Informational, not a security control. |
| `infra.json` in the repo | Ownership IDs | Regeneration. **Not trusted** for permissions. |

### 4.4 Why a repo cannot forge tags

```mermaid
flowchart LR
  A["Repo edits stack tags to<br/>org:project = ledger-api"] --> B["Deploy role tags (set by platform):<br/>org:project = invoice-ingest"]
  B --> C{"IAM: aws:RequestTag/org:project<br/>equals<br/>aws:PrincipalTag/org:project?"}
  C -->|"no"| D["AccessDenied on CreateChangeSet"]
  C -->|"yes"| E["Change set accepted"]
```

The role's tags can be changed only by the platform's provisioner role, and an SCP blocks changes to role tags by anyone else (§4.7). So a project can only ever act as itself.

### 4.5 Tag-based permissions (ABAC) design

**One shared policy per role type per account, instead of one policy per project.** The policies use `${aws:PrincipalTag/org:project}`, so the same policy behaves differently for each project's role. They are deployed once per account by StackSets. Project bootstrap only creates **tagged roles** that attach them. This is the main scalability gain: adding project number 500 adds no new policy documents.

| Role (per project, per env account) | Trusted by | Attached shared policy | Tag rules |
|---|---|---|---|
| `GitHubDeployRole` | GitHub OIDC, `sub = repo:{owner}/{repo}:environment:{env}` | `cloudinfra-deploy-abac` | CloudFormation create/update/change-set actions only when `aws:RequestTag/org:*` = `${aws:PrincipalTag/org:*}` for all required keys; describe/execute/delete only when `aws:ResourceTag/org:project` = own project. `iam:PassRole` only on roles where `aws:ResourceTag/org:project` = own project, passed to CloudFormation. Upload only to `artifact-bucket/${aws:PrincipalTag/org:project}/*`. |
| `CfnExecutionRole` | `cloudformation.amazonaws.com` (with `aws:SourceAccount`) | `cloudinfra-exec-abac` | **Create:** allowed only if request tags = own tags (and `aws:TagKeys` only from the allowed list). **Change/delete:** only if `aws:ResourceTag/org:project` = own project. **IAM:** `CreateRole`/`PutRolePolicy` only with the shared boundary attached and own tags. `PassRole` only on own-project roles, to Lambda. |
| App roles (e.g. the Lambda execution role, created by the stack) | `lambda.amazonaws.com` | Exact-ARN inline policy (from binders) **+ shared boundary** `cloudinfra-app-boundary` | The boundary allows data access only to resources tagged with the same `org:project` (or same `org:product` with `org:share-scope=product`, read-only). The inline policy narrows it to exact ARNs. |

**Illustrative pattern** (a design sketch, not final policy). The core rule of `cloudinfra-exec-abac` for Lambda:

```json
[
  {
    "Sid": "CreateOnlyWithOwnTags",
    "Effect": "Allow",
    "Action": ["lambda:CreateFunction", "lambda:TagResource"],
    "Resource": "arn:aws:lambda:*:${aws:PrincipalAccount}:function:${aws:PrincipalTag/org:project}--*",
    "Condition": {
      "StringEquals": {
        "aws:RequestTag/org:project":     "${aws:PrincipalTag/org:project}",
        "aws:RequestTag/org:product":     "${aws:PrincipalTag/org:product}",
        "aws:RequestTag/org:environment": "${aws:PrincipalTag/org:environment}"
      },
      "ForAllValues:StringEquals": { "aws:TagKeys": ["org:portfolio","org:product","org:project","org:environment","org:cost-center","org:data-classification","org:managed-by","org:share-scope","org:resilience","org:region-role"] }
    }
  },
  {
    "Sid": "ManageOnlyOwnProject",
    "Effect": "Allow",
    "Action": ["lambda:UpdateFunctionCode","lambda:UpdateFunctionConfiguration","lambda:DeleteFunction","lambda:AddPermission","lambda:RemovePermission","lambda:GetFunction"],
    "Resource": "arn:aws:lambda:*:${aws:PrincipalAccount}:function:${aws:PrincipalTag/org:project}--*",
    "Condition": { "StringEquals": { "aws:ResourceTag/org:project": "${aws:PrincipalTag/org:project}" } }
  }
]
```

Each rule checks **both** the tag condition and a name pattern built from the principal's own tag. Each one alone would be enough; together they are defense in depth.

### 4.6 Tags + names: covering what tag conditions can't

AWS support for `aws:ResourceTag` / `aws:RequestTag` **varies by service and by action**. The platform keeps a **support matrix** per catalog service, checked against the AWS Service Authorization Reference and tested in CI against a real sandbox account:

| Situation | Control used |
|---|---|
| Action supports `aws:RequestTag` (create) and `aws:ResourceTag` (change) | Tag condition **and** name pattern |
| Action lacks tag-condition support (some describe/list calls, some bucket-configuration actions) | Name pattern `${aws:PrincipalTag/org:project}--*` (still built from the role's tag, so still tag-driven) |
| Action supports no resource scoping at all (e.g. some `Describe*` calls) | Allowed read-only, at account+region scope, only in platform-owned roles, **never** in generated app roles |

**Sharing with other projects** is done by share tags or by agreement (§4.11). For example, an `iam.access` connection to a resource in *another* project of the *same* product is allowed when:
1. The target resource carries `org:share-scope=product` (or wider).
2. The access is within its `org:share-access` level (read by default).
3. The boundary condition `aws:ResourceTag/org:product = ${aws:PrincipalTag/org:product}` holds.

Access across products is not offered by the platform; it goes through a separate exception process.

### 4.7 Organization guardrails (SCPs + Tag Policies)

SCPs apply to every principal in the account, including humans and other tools. So the tag rules hold even outside this platform.

| Guardrail | Attached to | Rule |
|---|---|---|
| **Protect ownership tags** | All workload OUs | Deny `TagResource`/`UntagResource` (and service-specific equivalents) that add, change or remove `org:*` keys on a resource, unless the caller's `org:project` matches the resource's, or the caller is the platform provisioner / break-glass role. |
| **Protect platform roles** | All workload OUs | Deny changes (policy, trust, tags, boundary) to roles tagged `org:managed-by=cloudinfra`, except by the provisioner role. Deny `iam:DeleteRolePermissionsBoundary` everywhere. |
| **Require tags on create** | All workload OUs | For callers tagged `org:managed-by=cloudinfra`: deny create actions on catalog services if `aws:RequestTag/org:project` or `org:environment` is missing. Scoped to platform principals so other tooling isn't broken. |
| **Environment lock** | Each environment OU | Deny create if `aws:RequestTag/org:environment` ≠ that OU's environment (e.g. only `prod` in the Prod OU). |
| **Classification gate** | Sandbox OU | Deny create if `aws:RequestTag/org:data-classification` is `confidential` or `restricted`. |
| **Region allow-list** | All workload OUs | Only regions enabled in the platform's region list (§10.9). **Generated from that list**, so enabling a region in the admin screen updates the SCP (after approval). |
| **Tag Policies** | Root | Allowed keys + **allowed values** for `org:portfolio`/`org:product`, **generated from the registry and synced automatically**; enforce letter case; enforce on resource types that support it. |

Note: Tag Policies standardize values and report non-compliance; they enforce only for supported resource types. **SCP + IAM conditions are the actual enforcement**; Tag Policies are the consistency and reporting layer.

### 4.8 Human access uses the same tags
In IAM Identity Center, **attributes for access control** map an IdP attribute (product) to a session tag. Permission sets in shared environment accounts then use the same `aws:ResourceTag/org:product = ${aws:PrincipalTag/org:product}` pattern. Engineers can view and debug their product's resources in DEV/TEST and get read-only access in PROD, with no per-product policies.

### 4.9 Compliance and drift
- AWS Config rules (`required-tags` + a custom rule) flag `org:*` tag values that don't match the registry, per account, collected in the audit account.
- Resource Explorer / Tag Editor views per product.
- Cost Explorer + CUR grouped by `org:portfolio` / `org:product` / `org:cost-center` (activated as cost allocation tags in the management account).

---

### 4.10 Runtime isolation: components talk only to resources with the same tags

**Rule:** every component the platform creates (Lambda, ECS task, EKS pod, Step Functions state machine, Glue job, …) can read, write or invoke **only resources carrying the same `org:project` and `org:environment` tag values**. A Lambda in `invoice-ingest` / `dev` can use the `invoice-ingest` / `dev` S3 bucket because both are part of the same solution, and **nothing else**, even if someone pastes another bucket's ARN into the code or the template.

This is generated into the CloudFormation template at creation time. Nobody writes it by hand, and it applies to every resource type in the catalog (§6.8).

#### 4.10.1 How it is enforced (four layers)

```mermaid
flowchart LR
  L["Lambda runtime role<br/>org:project=invoice-ingest<br/>org:environment=dev"] --> C1["① Identity policy<br/>exact ARN + aws:ResourceTag = my tags"]
  C1 --> C2["② Permissions boundary<br/>same-project resources only"]
  C2 --> C3["③ Bucket policy<br/>deny if aws:PrincipalTag ≠ bucket tags"]
  C3 --> B["S3 bucket<br/>org:project=invoice-ingest<br/>org:environment=dev"]
  X["Lambda of another project<br/>org:project=ledger-api"] -. "denied at ①, ② and ③" .-> C3
```

| Layer | Where | What it checks | Covers |
|---|---|---|---|
| **1. Identity policy of the runtime role** | Generated per component by the connection binders (§6.8.4) | Exact resource ARNs from the connections **plus** `aws:ResourceTag/org:project = ${aws:PrincipalTag/org:project}` and `aws:ResourceTag/org:environment = ${aws:PrincipalTag/org:environment}` on every action where AWS supports resource-tag conditions | Caller side |
| **2. Shared permissions boundary** (`cloudinfra-app-boundary`, §4.5) | Attached to every runtime role (required by the CFN execution role) | Same tag conditions for supported actions; for actions without tag support, only names built from the principal's tag (`${aws:PrincipalTag/org:project}--*`) | Caller side, even if layer 1 had a bug |
| **3. Resource policy on the target** | Generated on **every resource type that supports a resource policy**: S3 buckets, SQS queues, SNS topics, KMS keys, Secrets Manager secrets, DynamoDB tables, ECR repositories, EventBridge buses, OpenSearch domains, API Gateway (private), Lambda (invocation), and so on | **Deny** any principal whose `aws:PrincipalTag/org:project` or `aws:PrincipalTag/org:environment` is not exactly this resource's value. Works for **all actions** on the resource, including those that don't support resource-tag conditions (e.g. S3 object operations). | Target side, independent of the caller's policies |
| **4. Organization guardrail (SCP)** | Workload OUs (§4.7) | For principals tagged `org:managed-by=cloudinfra`: deny supported actions when `aws:ResourceTag/org:project ≠ ${aws:PrincipalTag/org:project}` | Whole account, including roles created outside the platform pattern |

Because the **runtime roles carry the same stack tags** as the resources (propagated by CloudFormation, and required on `iam:CreateRole` by the CFN execution role, §4.5), "same tags and values" is something AWS checks on every request. It does not depend on naming conventions.

#### 4.10.2 Example: the generated S3 bucket policy (illustrative)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DenyOtherProjects",
      "Effect": "Deny",
      "Principal": "*",
      "Action": "s3:*",
      "Resource": ["arn:aws:s3:::invoice-ingest--uploads-222222222222-us-east-1",
                   "arn:aws:s3:::invoice-ingest--uploads-222222222222-us-east-1/*"],
      "Condition": {
        "StringNotEquals": { "aws:PrincipalTag/org:project": "invoice-ingest" },
        "BoolIfExists":    { "aws:PrincipalIsAWSService": "false" },
        "ArnNotLike":      { "aws:PrincipalArn": ["arn:aws:iam::222222222222:role/aws-service-role/*",
                                                  "arn:aws:iam::222222222222:role/cloudinfra/break-glass-*"] }
      }
    },
    {
      "Sid": "DenyOtherEnvironments",
      "Effect": "Deny",
      "Principal": "*",
      "Action": "s3:*",
      "Resource": ["arn:aws:s3:::invoice-ingest--uploads-222222222222-us-east-1",
                   "arn:aws:s3:::invoice-ingest--uploads-222222222222-us-east-1/*"],
      "Condition": {
        "StringNotEquals": { "aws:PrincipalTag/org:environment": "dev" },
        "BoolIfExists":    { "aws:PrincipalIsAWSService": "false" },
        "ArnNotLike":      { "aws:PrincipalArn": ["arn:aws:iam::222222222222:role/aws-service-role/*",
                                                  "arn:aws:iam::222222222222:role/cloudinfra/break-glass-*"] }
      }
    },
    { "Sid": "DenyInsecureTransport", "Effect": "Deny", "Principal": "*", "Action": "s3:*",
      "Resource": ["arn:aws:s3:::invoice-ingest--uploads-222222222222-us-east-1",
                   "arn:aws:s3:::invoice-ingest--uploads-222222222222-us-east-1/*"],
      "Condition": { "Bool": { "aws:SecureTransport": "false" } } }
  ]
}
```

Design notes:
- **Project and environment are separate Deny statements.** Several keys inside one `StringNotEquals` are combined with AND, which would deny only when *both* differ. Separate statements deny when *either* differs.
- **A principal with no tag is denied:** a negated condition on a missing key evaluates to true.
- **Exceptions are explicit and minimal:**
  - AWS service-linked roles, e.g. AWS Config reading the bucket configuration;
  - the audited break-glass role.

  The CloudFormation execution role and the S3 replication role (§10) carry the project tags, so they pass without exceptions.
- **AWS service principals** (e.g. S3 invoking Lambda, CloudFront reading S3) are not IAM roles and have no tags. They are allowed only through statements pinned to the **specific same-project source** with `aws:SourceArn` + `aws:SourceAccount` (the §6.3 pattern). The binder generates these only for connections drawn in the UI, so the source is always a resource with the same tags.

#### 4.10.3 What this covers, and the honest edges

| Situation | Behavior |
|---|---|
| Lambda → S3 / DynamoDB / SQS / SNS / Secrets / KMS of the same project + environment | Allowed (exact actions from the connection) |
| Lambda → same resource type of **another project** (ARN pasted in code) | **Denied** by layers 1, 2 and 3 |
| DEV component → STAGE resource of the same project | **Denied** (environment tag differs; also a different account) |
| Sharing with other projects / accounts | **By tags** (§4.11.1): the resource policy allows principals whose `org:product` / `org:portfolio` tags match the resource's `org:share-scope`, same environment, inside the organization, limited to `org:share-access` actions. **By agreement** (§4.11.2) for anything else |
| Humans (Identity Center) | Data access follows the environment policy: e.g. read for the product's engineers in DEV/TEST via an explicit, read-only exception on `org:product`; no human data access in PROD except break-glass |
| Network paths (DB, cache, OpenSearch in a VPC) | Security groups only allow ingress from the security groups of same-project components (`network.access`, §6.8.4). Databases also use IAM auth / per-project secrets, which are themselves tag-protected |
| Service without resource policies **and** without tag-condition support | Layer 1 uses exact ARNs, layer 2 uses the principal-tag-derived name pattern, and the catalog marks the service "name-scoped"; such services need platform review before enablement (§6.8.2) |

#### 4.10.4 Verification

- **Synthesis-time linter:**
  - every resource in a project carries identical `org:project` / `org:environment` values;
  - every runtime role has the boundary and tag conditions;
  - every resource that supports a resource policy has the project/environment deny statements.

  A template missing any of these is rejected.
- **CI cross-project tests (P1):** two projects are deployed in the platform test account. Tests assert that project A's Lambda **cannot** read, write or invoke project B's bucket, queue, table, secret or function, even with the exact ARN, and **can** use its own.
- **IAM Access Analyzer** (external and internal access findings) runs in every account. Any access path to a project resource from a principal outside that project raises a finding to the platform.

### 4.11 Sharing across projects and accounts: by tags or by agreement

Infrastructure created by the platform often needs assets owned by **other projects**, in the same or in **other AWS accounts**: a central data-lake bucket, a shared SQS queue, another product's KMS-encrypted dataset. Sharing is supported in two ways, and both **keep the tag-based isolation of §4.10**:

| Way | How it is decided | Approval per consumer | Use for |
|---|---|---|---|
| **1. Sharing by tags** (default) | The provider puts **share tags** on its resource. They define which consumers *can* be granted access (matching tags, any account of the organization). | **Yes, through the sharing approval workflow (§4.11.6).** The offer (share tags) is approved once; each consumer's access request is approved by the provider, or auto-approved if the provider chose `org:share-approval=auto` | Common, predictable sharing: within a product, within a portfolio, organization-wide reference data |
| **2. Sharing by agreement** | An explicit record naming one provider resource and one consumer | **Yes, through the same workflow** (provider owner, plus security / platform admin where required) | Anything the tag rules cannot express: one specific consumer, write access across products, outside the organization, exceptions |

In both cases the platform **generates** the permissions on both sides. Nobody hand-edits a policy.

#### 4.11.1 Sharing by tags

**Share tags on the provider resource** (set in the platform UI, deployed through the provider's normal infrastructure PR, gates and approvals):

| Tag | Values | Meaning |
|---|---|---|
| `org:share-scope` | `none` (default) \| `product` \| `portfolio` \| `organization` | **Who** may use the resource: principals whose `org:product` (or `org:portfolio`) equals the resource's value, or any platform principal in the organization |
| `org:share-access` | `read` (default) \| `readwrite` \| `invoke` \| `publish` \| `consume` | **What** they may do; mapped to exact actions per service (§6.8.1) |
| `org:environment` (existing) | — | Sharing by tags is **always same-environment**: the consumer's `org:environment` must equal the resource's. Never configurable by tag. |

**The rule AWS evaluates** for a consumer principal *P* and a provider resource *R*:

> allow the `org:share-access` actions **if** P's `org:environment` = R's `org:environment` **and** P is in the organization (`aws:PrincipalOrgID`) **and** (`org:share-scope = product` and P's `org:product` = R's `org:product`) **or** (`org:share-scope = portfolio` and P's `org:portfolio` = R's `org:portfolio`) **or** (`org:share-scope = organization`)

The rule needs no consumer ARNs or account IDs. It works **across accounts**, because AWS evaluates the caller's principal tags (`aws:PrincipalTag/...`) in the resource account's policy. A new project or account in the same product gets access automatically, and a project that moves to another product loses it automatically.

**What the platform generates:**

| Side | Generated from the tags |
|---|---|
| **Provider resource policy** (S3, SQS, SNS, KMS, Secrets Manager, DynamoDB, EventBridge, Lambda, ECR, Kinesis, OpenSearch, …) | An Allow for the share rule above, with the resource's **own tag values written in** at synthesis time (e.g. `aws:PrincipalTag/org:product = "pr-invoicing"`). The §4.10 deny statements are widened only to the same scope. For `read` sharing, an extra deny blocks every write action for anyone but the owning project. |
| **Provider KMS key** (if the data is encrypted) | Key policy grant for the same share rule, limited with `kms:ViaService` to the service in use |
| **Cross-account role** (pattern B, for services without resource policies) | Trust policy: any principal in the organization **with matching `org:product` / `org:portfolio` and `org:environment` tags**, instead of named consumer roles |
| **Consumer side** | When a consumer draws a connection to a shared resource (picked from the **shareable-resource catalog**, which is built from share tags), the platform checks the tags match, then raises an **access request** in the sharing approval workflow (§4.11.6). Only after approval does it generate the exact-ARN statements and the contract binding (auto-approved, with a notification to the provider, if the resource is tagged `org:share-approval=auto`). Because only the platform creates runtime roles and their policies, **no consumer can use a shared resource without an approved request**, even when the tags would match. The consumer's boundary allows cross-project access only to resources whose `aws:ResourceTag/org:share-scope` and product/portfolio match the consumer's tags (where the service supports resource-tag conditions), and only inside the organization. |

**Example: generated statements for a bucket tagged `org:product=pr-invoicing`, `org:share-scope=product`, `org:share-access=read`, `org:environment=prod` (illustrative):**

```json
[
  { "Sid": "ShareByTagRead", "Effect": "Allow", "Principal": "*",
    "Action": ["s3:GetObject", "s3:ListBucket"],
    "Resource": ["arn:aws:s3:::invoice-ingest--uploads-555555555555-us-east-1",
                 "arn:aws:s3:::invoice-ingest--uploads-555555555555-us-east-1/*"],
    "Condition": { "StringEquals": { "aws:PrincipalOrgID": "o-exampleorg",
                                     "aws:PrincipalTag/org:product": "pr-invoicing",
                                     "aws:PrincipalTag/org:environment": "prod" } } },
  { "Sid": "DenyOutsideShareScope", "Effect": "Deny", "Principal": "*", "Action": "s3:*",
    "Resource": ["arn:aws:s3:::invoice-ingest--uploads-555555555555-us-east-1",
                 "arn:aws:s3:::invoice-ingest--uploads-555555555555-us-east-1/*"],
    "Condition": { "StringNotEquals": { "aws:PrincipalTag/org:product": "pr-invoicing" },
                   "BoolIfExists": { "aws:PrincipalIsAWSService": "false" } } },
  { "Sid": "DenyWritesExceptOwner", "Effect": "Deny", "Principal": "*",
    "Action": ["s3:PutObject", "s3:DeleteObject", "s3:PutObjectAcl"],
    "Resource": "arn:aws:s3:::invoice-ingest--uploads-555555555555-us-east-1/*",
    "Condition": { "StringNotEquals": { "aws:PrincipalTag/org:project": "invoice-ingest" },
                   "BoolIfExists": { "aws:PrincipalIsAWSService": "false" } } }
]
```

The environment deny statement from §4.10.2 stays unchanged, and the service-linked-role and break-glass exceptions apply as before.

**Guardrails on share tags:**
- Share tags are `org:*` tags, so **only the platform pipeline can set or change them** (SCP §4.7). Changing a share tag is an infrastructure change with the normal gates and approvals.
- **Classification limits** (defaults, configurable, D37):
  - `public`/`internal` data: any scope.
  - `confidential`: up to `product`.
  - `restricted`: `none`, so agreements only.
- **Every change to share tags is a share-offer request** in the approval workflow (§4.11.6). It needs a security reviewer when widening scope beyond `product` or granting anything other than `read`.
- **Tag Policies** enforce the allowed values. The **shareable-resource catalog** in the UI lists every resource with a share scope, its owner, access level and classification.
- **IAM Access Analyzer:** archive rules are generated from the share tags, so expected access (e.g. "principals in o-exampleorg with product pr-invoicing, read") is archived automatically, and anything else alerts.
- **Revoking** = setting `org:share-scope=none`. The next deploy regenerates the policies and access stops for everyone at once. The consumers' connections are flagged in their projects.

#### 4.11.2 Sharing by agreement (explicit, for everything tags don't cover)

A sharing agreement is a record in the platform registry, created and approved in the UI:

| Field | Example |
|---|---|
| Provider | Project `datalake-core` / environment `prod` / account `666666666666` / resource `arn:aws:s3:::datalake-core--curated-666666666666-us-east-1` (or "non-platform resource" + ARN) |
| Consumer | Project `invoice-ingest` / environment `prod` / account `555555555555` / component (slot) `processor` |
| Access | `read` \| `write` \| `readwrite` \| `invoke` \| `publish` \| `consume` (mapped to exact actions per service from the Service Authorization Reference, §6.8.1) |
| Scope | Optional prefix / key condition (e.g. `s3:prefix = invoices/`) |
| Data classification | Must be ≤ the consumer project's classification ceiling |
| Expiry / review date | Required, e.g. 12 months; recertified quarterly |
| Approvals | Consumer owner (request) + **provider owner** + security reviewer for PROD or `confidential`+ data |

**Rules enforced on every agreement:**
- **Same environment tier only:** DEV↔DEV, PROD↔PROD. PROD resources are never shared with non-PROD. Any other combination needs a security exception.
- **Inside the AWS Organization by default** (`aws:PrincipalOrgID` / `aws:ResourceOrgID`). Accounts outside the organization (partners, vendors) are off by default and need an explicit exception, with an ExternalId for role assumption.
- **Least privilege:** exact actions for the access level, exact resource ARNs, optional prefix.
- **Both sides consent:** nothing is generated until the provider owner approves.

#### 4.11.3 How access is granted (per service)

| Pattern | When | Provider side (generated) | Consumer side (generated) |
|---|---|---|---|
| **A. Resource policy grant** (preferred) | Services with resource-based policies: S3, SQS, SNS, KMS, Secrets Manager, EventBridge buses, Lambda (invoke), DynamoDB (resource policies), ECR, OpenSearch, Kinesis (resource policies) | Allow statement for the consumer: `aws:PrincipalAccount = consumer account` **and** `aws:PrincipalTag/org:project = consumer project` **and** `aws:PrincipalTag/org:environment = env` **and** `aws:PrincipalOrgID = our org`. The §4.10 deny statements gain the approved consumer as their only additional exception. | Runtime role statement for the exact ARN + actions, with `aws:ResourceAccount = provider account` and, where supported, `aws:ResourceTag/org:project = provider project` |
| **B. Cross-account role** | Services without resource policies, or when the provider wants one auditable entry point | A role `xacct/{provider-project}/{consumer-project}` tagged with the provider's tags **plus** `org:share-consumer = {consumer project}`. Trust: the consumer component's role ARN, with `aws:PrincipalTag/org:project` and `org:environment` conditions and `aws:PrincipalOrgID`. Permissions: only the agreed actions on the agreed resources | `sts:AssumeRole` on **that one role ARN** only. The boundary allows `sts:AssumeRole` only when `aws:ResourceTag/org:share-consumer = ${aws:PrincipalTag/org:project}` |
| **C. AWS RAM share** | Resources shared by AWS RAM (e.g. subnets, Transit Gateway attachments, Glue Data Catalog, Route 53 Resolver rules) | RAM resource share to the consumer account, tagged with the agreement ID | Consumer stack references the shared resource ARN from the contract |
| **D. Encrypted data** | Any of the above where the data is KMS-encrypted | Key policy grant (pattern A) for the consumer role, with `kms:ViaService` limited to the service in use (e.g. `s3.us-east-1.amazonaws.com`) | `kms:Decrypt` / `kms:GenerateDataKey` on that key ARN only |
| **E. Private network path** | Cross-account network access (databases, internal APIs) | **PrivateLink endpoint service** (preferred) with allowed principals = consumer account; owned by the provider project or the network team | Interface endpoint + security group in the consumer project (`network.access`) |
| **F. Events** | EventBridge / SNS → SQS across accounts | Bus policy / topic policy allowing the consumer's rule or subscription (pattern A) | Rule target or subscription, plus the queue policy on the consumer's own queue |

**Non-platform resources** (in accounts the platform does not manage): the platform generates the consumer side. It gives the provider owner a **ready-to-apply policy snippet**. A readiness check (a harmless read such as `HeadBucket` / `GetQueueAttributes` from the consumer role) confirms the grant before the agreement is marked active.

#### 4.11.4 How sharing fits the four isolation layers (§4.10)

| Layer | Change for an approved agreement |
|---|---|
| 1. Consumer runtime role | Gets statements for the provider's exact ARNs and actions (pattern A) or for `sts:AssumeRole` on one role (pattern B). **Generated only from an active agreement**; the linter rejects any other cross-account statement. |
| 2. Permissions boundary | Allows cross-account access only to resources **inside the organization** (`aws:ResourceOrgID`), and role assumption only to roles tagged `org:share-consumer = ${aws:PrincipalTag/org:project}`. Everything else stays same-project only. |
| 3. Provider resource policy | **By tags:** one Allow for the share rule, with the deny statements widened to the share scope only. **By agreement:** the deny statements list only the owning project plus approved consumers (account + project + environment), and a precise Allow is added per agreement. |
| 4. SCP data perimeter | Platform principals cannot access resources outside the organization, and resource policies cannot grant to principals outside the organization, unless an exception is registered (§4.7). |

A consumer can therefore reach exactly the agreed resource, with exactly the agreed actions, from exactly the agreed component and environment. No other project in either account gains anything.

#### 4.11.5 Agreement workflow in the UI

```mermaid
sequenceDiagram
  autonumber
  actor C as Consumer owner
  participant UI as Platform UI
  actor P as Provider owner
  actor S as Security reviewer
  participant GH as GitHub (both infra repos)
  C->>UI: "Connect to resource in another account" (pick a shareable resource or paste an ARN)
  UI->>UI: validate: same tier, classification, org, access level → exact actions
  UI->>P: approval request (release console inbox)
  P-->>UI: approve (scope, expiry)
  UI->>S: approval request (PROD or confidential+ only)
  S-->>UI: approve
  UI->>GH: PR on provider infra repo (resource policy / xacct role / RAM share)
  UI->>GH: PR on consumer infra repo (role statements + contract binding)
  GH-->>UI: both deployed through normal gates and approvals
  UI->>UI: readiness check passes → agreement ACTIVE
```

- **Shareable resources:** the catalog shows resources with share tags (self-service connect, §4.11.1) and resources marked as available by agreement (request and approve).
- **Contract:** the consumer's contract (§9.4) gets an `external` section with the provider ARN, region, KMS key ARN and access level. Application code reads it like any other binding.
- **Revocation and expiry:** revoking (by either owner or security) or expiry opens PRs that remove both sides. Expiry warnings go out 30 and 7 days before.
- **DR/HA (§10):** agreements cover both regions of each side. Resource policies are generated in every region where the provider resource or replica exists, and the contract lists per-region ARNs.
- **Audit:** every agreement, approval, change and revocation is in the release records. **IAM Access Analyzer** findings that match an active agreement are archived automatically; any other cross-account access raises an alert.

#### 4.11.6 Sharing approval workflow

**All sharing is granted through one approval workflow in the platform UI.** Tags (and agreements) define what *can* be shared. The workflow decides what *is* shared, by whom, and records why.

**Request types:**

| Request | Raised by | Effect when approved |
|---|---|---|
| **Share offer** | Provider owner | Sets or changes `org:share-scope` / `org:share-access` / `org:share-approval` on a resource. Opens the provider infra PR |
| **Access request** | Consumer owner (by drawing a connection to a shared resource) | Grants one consumer component access within the tag rule. Opens the consumer infra PR (and the provider PR where a per-consumer grant is needed, e.g. a KMS grant) |
| **Agreement request** | Consumer owner | Creates a sharing agreement (§4.11.2). Opens both PRs |
| **Renewal** | Platform (before expiry / at recertification) | Extends the access or agreement; if not approved in time, access is removed |
| **Revocation** | Provider, consumer, security | Removes access on both sides. Emergency revocation needs only security and takes effect at once |

**Approval routing** (defaults; configurable by platform admins, D38):

| Situation | Approvers |
|---|---|
| Share offer, scope `product`, access `read`, data ≤ `internal` | Provider product owner |
| Share offer, scope `portfolio`/`organization`, **or** any access beyond `read`, **or** data `confidential` | Provider product owner **+ security reviewer** |
| Access request within an approved offer, resource tagged `org:share-approval=auto` | **Auto-approved** (provider notified; request still recorded) |
| Access request within an approved offer, `org:share-approval=required` (default) | Provider product owner |
| Access request or agreement for **PROD** with `confidential` data | Provider product owner **+ security reviewer** |
| Agreement **outside the AWS Organization**, or a cross-environment exception | Provider product owner + security reviewer **+ platform admin** |
| Renewal | Same approvers as the original request |
| Emergency revocation | Security reviewer (single approver) |

**Workflow rules:**
- **Separation of duties:** the requester cannot approve their own request; two-approver steps need two different people. Approvers come from the registry groups of the provider product (owners) and from the security group.
- **Evidence on one page:**
  - what is shared and with whom (project, product, account, environment);
  - access level → exact actions;
  - data classification;
  - the **generated policy diff** for both sides;
  - the Access Analyzer preview of the resulting access.
- **Timeouts and escalation:** reminders after 2 business days; escalation to the product's secondary owner after 5; pending requests expire after 30 days.
- **Approval leads to deployment, never manual edits:** an approved request opens the infra PRs, which go through the normal gates. For STAGE/PROD they also need the usual release approval (§8.3). The release reviewer sees the sharing approval as evidence, so the decision is not asked twice: release approval checks the change, sharing approval checks the access.
- **Recertification:** every active access and agreement is re-approved periodically (default quarterly, by the provider owner). Anything not recertified is removed automatically.
- **Audit:** every request, decision, comment, generated policy and deployment is in the release records. Exportable per resource ("who can access this and who approved it") and per consumer ("what does this project use and who approved it").

**Engine:** AWS Step Functions (human approval steps with task tokens), state in DynamoDB, notifications through the in-app inbox and Amazon SES. These are the same AWS services as the rest of the control plane (§1).

```mermaid
stateDiagram-v2
  [*] --> Submitted
  Submitted --> AutoApproved: access request, org:share-approval=auto
  Submitted --> PendingApproval: routing matrix
  PendingApproval --> Approved: all required approvers
  PendingApproval --> Rejected: any approver rejects
  PendingApproval --> Expired: 30 days
  AutoApproved --> Deploying
  Approved --> Deploying: infra PRs + normal gates
  Deploying --> Active: readiness check passed
  Active --> PendingRenewal: expiry / recertification due
  PendingRenewal --> Active: re-approved
  PendingRenewal --> Revoked: not re-approved
  Active --> Revoked: revocation request
  Rejected --> [*]
  Expired --> [*]
  Revoked --> [*]
```

---

## 5. Multi-account environment strategy

### 5.1 Organization structure

```mermaid
flowchart TD
  ROOT["Root (management account)"] --> SEC["Security OU<br/>Log Archive · Audit / Security tooling"]
  ROOT --> INF["Infrastructure OU<br/>Network · Shared Services (artifacts) · Platform (control plane)"]
  ROOT --> SBXOU["Sandbox OU"]
  ROOT --> WL["Workloads OU"]
  WL --> NP["NonProd OU"]
  NP --> DEVOU["DEV OU"]
  NP --> TESTOU["TEST OU"]
  NP --> STGOU["QA/STAGE OU"]
  WL --> PRDOU["Prod OU"]
  ROOT --> SUS["Suspended OU"]
```

The full landing-zone OU structure (questionnaire-driven; Sandbox, DEV, TEST, STAGE, PROD always separate isolated OUs; one Security OU), its Control Tower controls and the isolated hub-and-spoke network are designed in §20. This diagram shows only the environment OUs. Separate OUs per environment let each environment have its own SCPs (environment lock, classification, sandbox budget/cleanup, prod deletion protection).

### 5.2 Account granularity: options

| Option | Accounts | Isolation between products | Main risk | When |
|---|---|---|---|---|
| **A. One account per environment** | 5 | Tags/ABAC only | Large blast radius; **shared service quotas** (e.g. Lambda's default 1,000 concurrent executions per account per region shared by everyone) | Small orgs |
| **B. One account per portfolio per environment** (recommended) | 5 × portfolios | Account boundary between portfolios; ABAC between products/projects inside | Moderate number of accounts | Default |
| **C. One account per product per environment** | 5 × products | Account boundary per product | Account sprawl | Regulated or very large products |

**Recommendation: B, with C available per product.** Account bindings (§5.5) decide per portfolio or product, so a product can move to dedicated accounts later without changing the generator, pipeline or policies. Only its binding changes. **Tag-based isolation is required in all three options**, because more than one project always shares an account.

### 5.3 Environment profiles

These are the **default profiles** for the five seeded environments. All of them can be changed per environment in the application (§5.5).

| | Sandbox | DEV | TEST | QA/STAGE | PROD |
|---|---|---|---|---|---|
| Purpose | Experiments, feature branches | Integration on `main` | Automated test suites | Production-like, UAT | Live |
| Deploy trigger | Manual dispatch from **any branch** | Auto on push to `main` | Auto after DEV succeeds | After TEST + **approval** | After STAGE + **approval** |
| GitHub env protection | None | Branch: `main` | Branch: `main` | `main`, **required reviewer approval** (QA; release console, GitHub identities), no self-approval | `main`/release tags, **required reviewer approval** (product owner + change mgmt; release console, GitHub identities), no self-approval, optional wait timer |
| Data classification allowed | ≤ internal | ≤ confidential (synthetic data) | ≤ confidential | as product ceiling | as product ceiling |
| `retainOnDelete` default | false | false | false | true | true (+ stack policy blocks replace/delete) |
| Log retention | 7 d | 14 d | 14 d | 90 d | ≥ 365 d |
| Cleanup | `org:expires-on` TTL (e.g. 14 days) + nightly cleanup job | — | — | — | Deletion denied by SCP except break-glass |
| Budget | Per-project budget alarm + hard SCP limits on expensive services | Budget alarm | Budget alarm | Budget alarm | Alarms + anomaly detection |
| Alarms | — | basic | basic | full | full + paging |

### 5.4 Bootstrap at scale

| Layer | What | Deployed by | When |
|---|---|---|---|
| **Account bootstrap** | GitHub OIDC provider; shared policies `cloudinfra-deploy-abac`, `cloudinfra-exec-abac`, `cloudinfra-app-boundary`; `CloudInfraProvisioner` role (trusted only by the Platform account, with `aws:PrincipalOrgID`); in gated accounts, the `PlatformReleaseExecutor` role (§8.3.1: execute reviewed change sets / release reviewed artifacts only; session tag `org:project` required) | **Service-managed StackSet** targeting the workload OUs, auto-deploying to new accounts | Once; updates roll out across the org |
| **Shared Services** | Artifact bucket per **enabled** region (created when an admin enables a region, §10.9); its bucket policy lets org accounts' execution roles read `${aws:PrincipalTag/org:project}/*` only (`aws:PrincipalOrgID` + principal-tag condition) | Platform IaC | Once per region |
| **Project bootstrap** | Per enabled environment: `GitHubDeployRole` + `CfnExecutionRole`, **tagged with the project's tags** and attaching the shared policies. Small, because the policies already exist. | Orchestrator via `CloudInfraProvisioner` in each target account (in parallel, throttled per account) | Once per project per environment |

Lambda requires the code bucket to be in the **same region** as the function; it can be in another account. Hence one artifact bucket per region in Shared Services.

### 5.5 Configurable environments and account numbers

Environments and their AWS account numbers are **data in the application, not code**. The five environments above are the default seed. Admins can rename, reorder, add (e.g. `perf`) or retire environments, and bind account numbers to them, without a code change or redeploy.

#### 5.5.1 Environment definition (admin screen)

| Field | Example | Notes |
|---|---|---|
| `envId` | `stage` | Immutable slug (`^[a-z][a-z0-9]{1,15}$`). Used as the GitHub environment name, the `org:environment` tag value and the OIDC `sub` suffix, so it **cannot be renamed** once a project uses it. |
| `displayName` | `QA/STAGE` | Free text, can change at any time. |
| `order` | `4` | Promotion order. Must be unique among active environments. |
| `tier` | `sandbox` \| `nonprod` \| `prod` | Selects default guardrails and which OU an account must be in. |
| `requiredGate` | `true` | If true, any later environment requires this one to be enabled (e.g. no prod without stage). |
| `deployTrigger` | `manual-any-branch` \| `auto-on-main` \| `after-previous` \| `after-previous-with-approval` | Becomes the job wiring in the generated `deploy.yml`. |
| `requiresApproval` | `true` | GitHub required-reviewer approval before deployment. **Locked to `true` for STAGE and all `prod`-tier environments** (§8.3). |
| `protectionProfile` | branch rules, reviewer source, prevent self-review, wait timer | Applied to the GitHub environment (§7.2). |
| `guardrailProfile` | classification ceiling, retention minimums, retain defaults, TTL, stack policy | Feeds validation, cfn-guard rules and `config/{env}.json` defaults (§5.3 table = the default profiles). |
| `status` | `active` \| `retired` | Retired environments are hidden for new projects; existing projects keep working until migrated. |

#### 5.5.2 Account bindings

An account binding says *"for this environment, this portfolio (or product), in this region, deploy to this AWS account"*.

| Field | Example | Rule |
|---|---|---|
| `envId` | `prod` | Must be an active environment |
| `scope` | `portfolio` / `product` | A product binding overrides its portfolio's binding (matches option B with C per product, §5.2) |
| `scopeId` | `pf-payments` | Must exist in the org registry |
| `region` | `us-east-1` | Must be in the region allow-list |
| `accountId` | `555555555555` | 12 digits. **Unique across environments:** an account can belong to only one environment (enforced by a transactional uniqueness record). It may serve several portfolios only if the admin explicitly allows sharing (option A). |
| `status` | `pending` → `onboarded` / `failed` → `retired` | Only `onboarded` bindings can be selected for deploys |

Resolution at preview time is: product binding → portfolio binding → error "no account configured for {env}". The preview shows the resolved account for every environment before the user clicks Create.

#### 5.5.3 Onboarding checks (run when a binding is saved or re-validated)

| Check | How |
|---|---|
| Account belongs to the organization and is active | `organizations:DescribeAccount` from the Platform account (delegated admin) |
| Account is in the OU that matches the environment's tier | `organizations:ListParents` |
| Account bootstrap is in place | StackSet instance status `CURRENT` for that account + region |
| Platform can reach it | Assume `CloudInfraProvisioner` and call `sts:GetCallerIdentity`; returned account must equal `accountId` |
| GitHub OIDC provider and shared tag-based policies exist | Read-only IAM checks through the provisioner role |
| Account not bound to a different environment | Uniqueness record |

A binding that fails any check stays `failed`, with the reason shown in the admin screen.

#### 5.5.4 Who can change it, and how changes propagate

- **Permissions:** only `platform-admin` can edit environments and bindings. Changes to `prod`-tier environments need a **second admin's approval** (four-eyes) before they take effect. Every change is versioned and audited (who, when, before/after).
- **New projects** always use the current configuration.
- **Existing projects are never silently re-pointed.** When an environment is added or a binding changes, the platform lists the affected projects and, per project:
  1. Bootstraps the new account (§5.4).
  2. Updates the repo's GitHub variables (§5.5.5).
  3. Opens a "sync pipeline" PR if the environment list or order changed.

  Moving an existing stack to a different account is a **migration** (deploy in the new account, move data, retire the old stack). It is done on purpose and per project, never automatically.
- A **reconciler** compares each repo's GitHub variables with the application configuration nightly. It reports drift and, if configured, repairs it.

#### 5.5.5 GitHub variables (all pipeline configuration lives here)

Every value the pipeline needs is a **GitHub Actions variable** (`vars.*`), written by the platform. The workflow files contain no account numbers, ARNs, names or tags; they only reference variables. There are **no GitHub secrets** in OIDC mode, because no credentials are stored. A role ARN is an identifier, not a credential, so it is a variable too.

| Variable | Level | Example | Source in the application |
|---|---|---|---|
| `PROJECT_NAME` | Repository | `invoice-ingest` | Project |
| `ORG_PORTFOLIO` | Repository | `pf-payments` | Ownership (registry ID) |
| `ORG_PRODUCT` | Repository | `pr-invoicing` | Ownership |
| `ORG_COST_CENTER` | Repository | `CC-4410` | Registry (product) |
| `ORG_DATA_CLASSIFICATION` | Repository | `confidential` | Ownership |
| `ENVIRONMENT_ORDER` | Repository | `sandbox,dev,test,stage,prod` | Environment config (informational; the generated `deploy.yml` holds the actual job chain) |
| `ENVIRONMENT_NAME` | **Environment** | `prod` | `envId` |
| `AWS_ACCOUNT_ID` | **Environment** | `555555555555` | Resolved account binding |
| `AWS_REGION` | **Environment** | `us-east-1` | Binding region (multi-region projects use `AWS_PRIMARY_REGION` / `AWS_SECONDARY_REGION` instead, §10.5) |
| `AWS_ROLE_ARN` | **Environment** | `arn:aws:iam::555555555555:role/cloudinfra/invoice-ingest-deploy` | Project bootstrap output |
| `CFN_EXEC_ROLE_ARN` | **Environment** | `arn:aws:iam::555555555555:role/cloudinfra/invoice-ingest-cfn-exec` | Project bootstrap output |
| `ARTIFACT_BUCKET` | **Environment** | `cloudinfra-artifacts-999999999999-us-east-1` | Shared Services bucket for the binding's region |

- **Plan environments** (`stage-plan`, `prod-plan`) have their own copy of these environment variables, where `AWS_ROLE_ARN` points to the **plan role** (§8.3). The workflow uses the same variable name everywhere; GitHub supplies the right value per environment.
- **Environment-level variables** are visible only to jobs that run in that GitHub environment. So the DEV job never sees the PROD account number or role.
- GitHub's precedence is environment → repository → organization. The platform writes each variable at exactly one level, so precedence never decides a value by accident.
- **Who can edit them:** the product's GitHub access team (from the registry) gets the `maintain` role on the repo, not `admin`, so it cannot change variables or environment protection. Only the platform (GitHub App) and org admins can. This is a convenience control, not the security boundary.
- **The security boundary is still AWS.** If someone did change `AWS_ACCOUNT_ID` or a tag variable:
  - OIDC trust in each account only accepts this repo + this environment.
  - IAM only accepts stack tags equal to the deploy role's own tags (§4.4).
  - The pipeline also checks that `aws sts get-caller-identity` returns `vars.AWS_ACCOUNT_ID` and that `vars.ENVIRONMENT_NAME` equals the job's GitHub environment, and stops if not.

  A tampered variable can make a deploy fail; it cannot make it touch another project's or another environment's resources.
- **Long-lived credentials mode (§8.7)** is the only exception: access keys are credentials and are stored as GitHub **environment secrets**, never as variables.

---

## 6. CloudFormation generation engine

### 6.1 Approach: building blocks + connection binders

```mermaid
flowchart LR
  P["Validated payload<br/>+ resolved tags"] --> I["Create one block per resource"]
  I --> B["Apply binders<br/>(events, permissions, IAM statements,<br/>env vars, DependsOn)"]
  B --> E["Blocks emit CFN resources"]
  E --> L["Least-privilege + tag linter<br/>cfn-lint · cfn-guard"]
  L --> Y["template.yaml (one for all envs)"]
  P --> PF["config/{env}.json<br/>(parameters per environment)"]
  B --> C["single-repo starter mode only:<br/>src/{id}/lambda_function.py<br/>(otherwise code lives in app repos, §9)"]
  Y & PF & C --> F["File bundle + deploy.yml + infra.json + README"]
```

- **One template for all environments.** Differences between environments are only parameter values in `config/{env}.json` (memory, retention, concurrency, retain flags), checked against per-environment ranges.
- **Tags are not hardcoded per resource in the template.** They are applied as **stack tags** by the pipeline and propagated by CloudFormation. The template itself stays environment-neutral and ownership-neutral. (A resource type that doesn't receive propagated tags gets explicit `Tags` from parameters; the linter checks every taggable resource ends up tagged.)
- Output is **deterministic** (stable logical IDs, sorted keys, no timestamps), so regenerating gives an empty changeset.

### 6.2 Naming

| Item | Pattern | Example |
|---|---|---|
| Stack | `{project}` (one per environment account) | `invoice-ingest` |
| Logical IDs | `PascalCase(id)` + type suffix | `UploadsBucket`, `ProcessorFunction`, `ProcessorRole` |
| S3 bucket | `{project}--{id}-${AWS::AccountId}-${AWS::Region}` | `invoice-ingest--uploads-222222222222-us-east-1` |
| Lambda / DynamoDB | `{project}--{id}` | `invoice-ingest--processor` |
| Log group | `/aws/lambda/{project}--{id}` | — |
| IAM roles | CloudFormation-generated name, Path `/app/{project}/`, tagged | — |
| Boundary | Shared `cloudinfra-app-boundary` per account | — |

The account ID in bucket names keeps them unique across environments.

### 6.3 S3 → Lambda wiring (and the circular dependency trap)

The obvious template has a dependency loop:
- The bucket's notification needs the function ARN.
- The `Lambda::Permission` needs the bucket ARN.
- The bucket must wait for the permission, because S3 checks that it may invoke the function when the notification is saved.

**Fix:**
1. The bucket name is predictable (built with `Fn::Sub`).
2. `Lambda::Permission.SourceArn` and the function role's `s3:GetObject` resource use a **constructed ARN string**, not `Ref`/`GetAtt`.
3. The bucket gets `DependsOn` on the permission.
4. The permission sets `SourceAccount: ${AWS::AccountId}`, so another account that owns a bucket with that name cannot invoke the function.

```mermaid
flowchart LR
  LG["LogGroup"] --> R["Role (boundary attached)<br/>s3:GetObject on built ARN/incoming/*"]
  R --> F["Function"]
  F --> P["Lambda::Permission<br/>s3.amazonaws.com · built SourceArn · SourceAccount"]
  P --> B["Bucket<br/>ObjectCreated:* prefix incoming/ → Function"]
  B --> BP["BucketPolicy (deny non-TLS)"]
```

### 6.4 Defaults built into each block
- **S3:**
  - Public access blocked; ACLs off; encryption (SSE-S3, or SSE-KMS for `confidential`+).
  - Bucket policy: deny other projects and other environments by principal tag (§4.10.2), and deny non-TLS requests.
  - Versioning + lifecycle.
  - `DeletionPolicy: RetainExceptOnCreate` / `UpdateReplacePolicy: Retain` when retained (stage/prod by default).
- **Lambda:**
  - One execution role per function, with the shared boundary attached; exact-ARN inline policy (logs to its own log group + binder statements).
  - An explicit log group with retention per environment; JSON logging.
  - `arm64`.
  - Code: in the recommended split model (§9) the function is created with a platform bootstrap package and the **application repo** deploys the real code. In single-repo starter mode only, code comes from the regional artifact bucket at `{project}/{tree-hash}/{id}.zip`.
  - DLQ / on-failure destination recommended for S3 triggers.
- **DynamoDB:** on-demand billing, point-in-time recovery, encryption, deletion protection in stage/prod.

#### 6.4.1 Service settings (declared by each block, validated, shown in the UI)

Each curated block declares the `config` keys it accepts as **setting** objects (one class per kind: choice, integer, text; Open/Closed). The declaration drives three things, so they cannot drift apart:

1. **Validation.** `BlockRegistry.problems_for` rejects unknown keys and invalid values with a 422 that names the allowed keys (for example, *"lambda.function 'processor' does not accept 'memory'; allowed: runtime, handler, memory_mb, timeout_sec"*). Before this, unknown keys were silently ignored and the block used its defaults.
2. **Defaults.** Blocks read values through `Block.setting(name)`, which falls back to the declared default.
3. **UI.** `GET /v1/catalog` returns each service's `settings` (`kind`, `name`, `label`, `default`, plus `choices`, `minimum`/`maximum`/`unit` or `optional`). The Services step renders one field per setting for every curated resource. Only values the user changes are sent, so `infra.json` keeps "default" distinct from "chosen".

| Service | Setting | Kind | Default | Allowed |
|---|---|---|---|---|
| Lambda | `runtime` | choice | `python3.13` | `python3.13`, `python3.12`, `nodejs22.x`, `nodejs20.x`, `java21`, `provided.al2023` (Go, Rust and other compiled languages) |
| Lambda | `handler` | text | `lambda_function.lambda_handler` | 1–128 characters of `A-Za-z0-9_.:/$-` |
| Lambda | `memory_mb` | integer | 256 | 128–10240 MB |
| Lambda | `timeout_sec` | integer | 30 | 1–900 seconds |
| DynamoDB | `partition_key` | text | `pk` | 1–255 characters of `A-Za-z0-9_.-` |
| DynamoDB | `sort_key` | text, optional | none | 1–255 characters of `A-Za-z0-9_.-` |
| S3, SQS | none | | | Any `config` key is rejected |

Schema-driven (Tier 2) resources accept only `config.properties`, which must be a JSON object.

### 6.5 Template parameters

| Parameter | Source |
|---|---|
| `ProjectName` | GitHub environment variable |
| `EnvironmentName` | GitHub environment variable (must equal the deploy role's `org:environment` tag) |
| `CodeS3Bucket`, `CodeS3Prefix` | Bootstrap package location (split model, §9) or `{project}/{tree-hash-of-src}` (single-repo starter mode) |
| Per-resource settings (memory, retention, concurrency, retain) | `config/{env}.json` |

### 6.6 Validation gate
1. Schema + graph + registry/entitlement checks (§3.3).
2. **Least-privilege linter:**
   - No `Allow` with `*` / `service:*` actions or `*` resources in generated roles.
   - No `iam:*` or `iam:PassRole` in app roles. No `sts:AssumeRole`, except on the single cross-account role named in an **active sharing agreement** (§4.11). No cross-account resource statements unless generated from an active agreement.
   - Every generated role has the boundary.
3. **Tag linter:** every taggable resource will carry the required `org:*` keys (via propagation or explicit tags) with **identical** project/environment values. Every runtime role has the boundary and tag conditions, and every resource that supports a resource policy has the same-tag deny statements (§4.10).
4. cfn-lint; **cfn-guard rules per environment** (e.g. prod: retain + alarms + retention ≥ 365 days).
5. Golden-file tests for every catalog combination.

### 6.7 Idempotency of the template
- Stable logical IDs and predictable physical names.
- Retain policies on stateful resources; stack policy in prod.
- Code keys based on content (tree hash). A docs-only push gives an empty changeset (`--no-fail-on-empty-changeset`).
- No timestamps or request IDs in the template; deploys go through changesets.

---

### 6.8 Full AWS service coverage: every service and every combination, including databases

**Goal:** users can build any combination of AWS services that CloudFormation supports, including all database engines, with the same security, tagging, environment and approval guarantees as the Lambda + S3 example.

**Why the hand-written approach must change:** AWS has well over a thousand CloudFormation resource types and adds more every month. Hand-writing a block and binder for each one, and testing every combination by hand, does not scale. The engine therefore **generates** most of the catalog from AWS's own machine-readable specifications and adds **curated, opinionated blocks** on top for the services people use most.

#### 6.8.1 Two inputs published by AWS

| Source | What it gives the platform | How it is used |
|---|---|---|
| **CloudFormation resource provider schemas** (JSON Schema for every resource type; `aws cloudformation describe-type` / published schema bundle per region) | Every property, its type, required/read-only/create-only fields, which properties force **replacement**, available `GetAtt` attributes, tagging support | Generates the UI form, payload validation, the replacement-risk classifier (§8.4.2) and correct `Ref`/`GetAtt` wiring for any resource type |
| **AWS Service Authorization Reference** (machine-readable JSON per service: actions, resource ARN formats, condition keys, access levels) | For every action: read/write/list/tagging level, ARN pattern, whether `aws:ResourceTag` / `aws:RequestTag` are supported | Generates least-privilege `iam.access` statements for **any** service, the tag-condition support matrix (§4.6) and the per-service parts of the shared tag-based policies (§4.5) |

A nightly **catalog sync job** downloads both, diffs them against the current catalog version, and opens a PR on the platform repo with new and changed types. A platform engineer reviews it, the golden tests run, and it ships as a new `catalogVersion`. Nothing reaches users without review.

```mermaid
flowchart LR
  A["CloudFormation resource schemas"] --> S["Catalog sync job (nightly)"]
  B["Service Authorization Reference"] --> S
  S --> G["Generated layer<br/>forms · validation · IAM action sets ·<br/>tag-support matrix · replacement rules"]
  C["Curated overlays (hand-written)<br/>secure defaults · binders · env profiles"] --> M["Catalog version N"]
  G --> M
  M --> R["Review PR + golden tests +<br/>sandbox deploy tests"]
  R --> E["Enablement by platform admins<br/>(per environment / portfolio)"]
  E --> UI["Service catalog in the UI"]
```

#### 6.8.2 Catalog tiers

| Tier | What | Defaults and wiring | Who can use it |
|---|---|---|---|
| **Tier 1: Curated** | The most-used services (list below) | Hand-written secure defaults per environment profile, binders for connections, tested combinations, reference patterns | All users |
| **Tier 2: Schema-driven** | **Any other project-scoped CloudFormation resource type** | Generated form + validation; mandatory guardrails applied to every type (naming, tags, encryption where the schema has it, deletion policies for stateful types); generic `iam.access` binder from the Service Authorization Reference | Enabled per service by platform admins after a short review (ABAC support, guard rules, cost); can be limited to sandbox/dev first |
| **Excluded** | Account-wide or organization-wide types (Organizations, Control Tower, IAM Identity Center, account settings, IAM users/groups, VPC creation where the landing zone owns the network, billing) and anything that can't be scoped to one project | — | Not offered; managed by the landing zone / platform team |

Promoting a Tier 2 service to Tier 1 is a normal catalog change: add a curated overlay and binders.

**Tier 1 at launch (proposal, D27):**

| Category | Services |
|---|---|
| Compute | Lambda, ECS (Fargate), EKS workloads (shared clusters), App Runner, Batch |
| Integration | Step Functions, EventBridge (buses, rules, Scheduler, Pipes), SQS, SNS, Kinesis Data Streams, Amazon Data Firehose, Amazon MQ, MSK |
| API & edge | API Gateway (REST, HTTP, WebSocket), Application/Network Load Balancer (listener rules on shared or project ALB), CloudFront, AWS WAF (web ACL association) |
| Storage | S3, EFS |
| **Databases** | **Aurora PostgreSQL / MySQL (incl. Serverless v2), RDS PostgreSQL / MySQL / MariaDB, DynamoDB, DocumentDB, Neptune, ElastiCache (Valkey / Redis OSS / Memcached), MemoryDB, Keyspaces, Timestream, Redshift Serverless, OpenSearch Service (incl. Serverless)** |
| Analytics | Glue (jobs, crawlers, Data Catalog), Athena workgroups, Lake Formation permissions (project-scoped) |
| Security & config | KMS keys (project keys), Secrets Manager, SSM parameters, AppConfig, Cognito user pools |
| Observability | CloudWatch alarms, dashboards, log groups, X-Ray groups |
| Machine learning | SageMaker endpoints/models (project-scoped), Amazon Bedrock access (model invocation permissions) |

**Commercial database engines:** RDS for Oracle and RDS for SQL Server include third-party vendor licenses. Because of the open-source/no-commercial-products policy (§1), they are **excluded by default** and can be enabled only by an explicit decision (D28).

#### 6.8.3 Databases: what the platform adds

Databases need more than a resource: network placement, credentials, backups and engine-specific settings. The curated database blocks provide these automatically.

| Concern | Built-in behavior |
|---|---|
| **Network** | Placed in the landing zone's private database subnets (published to SSM by the network team, D23). A **security group per database**. Ingress is opened only by a connection (`network.access`, below) from a specific compute slot's security group, on the engine port. **Never public.** |
| **Credentials** | **No passwords in templates or repos.** RDS/Aurora/DocumentDB/Redshift use **AWS-managed master credentials in Secrets Manager** (`ManageMasterUserPassword`) with rotation. App runtime roles get `secretsmanager:GetSecretValue` on that one secret only. **IAM database authentication** (`rds-db:connect` for a specific DB user) is offered where the engine supports it. |
| **Connections from Lambda** | **RDS Proxy** added automatically when a Lambda slot connects to RDS/Aurora (connection pooling + IAM auth) |
| **Encryption** | At rest with the project KMS key (stage/prod) or AWS-managed key (sandbox/dev); TLS required (parameter group `require_secure_transport` / `rds.force_ssl`) |
| **Resilience per environment profile** | Sandbox/dev: single-AZ, small instance or serverless minimum, 1-day backups. Stage/prod: Multi-AZ / Aurora replicas, longer backup retention, Performance Insights, enhanced monitoring |
| **Data protection** | `DeletionProtection` on stage/prod; `DeletionPolicy: Snapshot` (or `RetainExceptOnCreate` where snapshots don't apply) and `UpdateReplacePolicy: Snapshot`. Any change that would **replace** a database is classified **high risk** and blocked without an override (§8.4.2). |
| **Parameter groups** | Generated per database from the engine family, with secure defaults; overridable settings limited to an allow-list |
| **Contract exposes** | Endpoint(s) (writer/reader), port, engine/version, database name, secret ARN, proxy endpoint, IAM auth user, security group ID |
| **Schema migrations** | Owned by the **application repo** (solution code), using open-source tools such as Flyway, Liquibase or Alembic. Run by the golden-path pipeline as a one-off ECS task or Lambda **inside the VPC**, before the new code version is released. Same approvals as the app deploy (§9.9 independence preserved). |

#### 6.8.4 Connection kinds that cover any combination

Combinations are built from a **small set of generic connection kinds** that work across services, not from a binder per pair of services:

| Connection kind | Examples | What the binder generates |
|---|---|---|
| `iam.access` (read / write / readwrite / admin-data) | Lambda → DynamoDB, ECS → S3, Step Functions → Lambda, Glue → S3 | Least-privilege statements from the Service Authorization Reference for the target's ARN; tag conditions where supported |
| `network.access` | ECS → Aurora (5432), Lambda → ElastiCache (6379), EKS workload → OpenSearch (443) | Security group ingress rule (source SG → target SG, engine port only); VPC config on the source if missing |
| `event.source` (poll-based) | SQS / Kinesis / DynamoDB Streams / MSK / Amazon MQ → Lambda | Event source mapping + the poller permissions on the source |
| `event.notify` (push-based) | S3 → Lambda/SQS/SNS/EventBridge, SNS → SQS/Lambda | Notification config + resource policy on the target with `SourceArn`/`SourceAccount` (the §6.3 pattern, generalized) |
| `event.rule` | EventBridge rule/schedule/pipe → any supported target | Rule/schedule/pipe + target role or resource policy |
| `api.route` | API Gateway / ALB → Lambda / ECS / Step Functions | Integration, route, permission/target group |
| `workflow.task` | Step Functions → Lambda / ECS / DynamoDB / SQS / SNS / Glue / Batch / Bedrock … | Task state substitution values + state machine role statements for that integration |
| `secret.binding` | Any compute → database secret / Secrets Manager secret / SSM parameter | `GetSecretValue`/`GetParameter` on that one ARN + KMS decrypt on its key; value name injected as env var |
| `cdn.origin` | CloudFront → S3 / ALB / API Gateway | Origin + origin access control and the matching bucket/resource policy |
| `xacct.access` | Any component → a resource in **another AWS account** (S3, SQS, SNS, KMS, DynamoDB, secrets, events, private APIs) | Created only from an approved **sharing agreement** (§4.11): provider resource policy / cross-account role / RAM share / PrivateLink, plus consumer role statements and contract binding |

Each connection kind declares **which source and target types it accepts**, using capabilities from the generated layer (e.g. "can be a Lambda event source", "has a security group", "has an ARN"). So a new service is usable in combinations as soon as its schema and authorization data are in the catalog. The **compatibility matrix** shown in the UI is computed, not hand-maintained.

#### 6.8.5 Scaling templates: layered stacks

Large combinations can exceed CloudFormation limits (500 resources per stack, 1 MB template) and mix very different change rates. The engine splits a project into **layer stacks** automatically when needed:

| Stack | Contains | Change rate | Protection |
|---|---|---|---|
| `{project}-data` | Databases, buckets, tables, streams, KMS keys, secrets | Rare | Strongest: stack policy denies replace/delete; retain/snapshot policies |
| `{project}-integration` | Queues, topics, event buses, rules, APIs | Medium | Standard |
| `{project}-compute` | Lambda shells, ECS services, EKS namespace resources, state machine roles | Frequent | Standard |
| `{project}-edge` | CloudFront, WAF associations, DNS records | Rare | Standard |

- Layers reference each other through **SSM parameters**, not CloudFormation exports (same reason as §9.4).
- They deploy in dependency order in the same pipeline run, each through its own change set, and STAGE/PROD reviewers approve **all layer change sets together** as one release.
- Small projects stay a single stack.

#### 6.8.6 How "all combinations" are validated and tested

Exhaustive testing of every combination is impossible, so correctness rests on **construction rules** plus **systematic sampling**:

1. **By construction:** every resource is validated against its AWS schema; every connection against the computed compatibility matrix; every IAM statement is generated from the authorization data and passes the least-privilege linter; every template passes cfn-lint and cfn-guard. A combination that passes these is valid by design.
2. **Golden tests:** every Tier 1 block and every connection kind has reference templates in CI.
3. **Pairwise combination tests:** CI generates **pairwise (all-pairs) combinations** of Tier 1 types × connection kinds × environment profiles. This covers every interaction between any two choices with a manageable number of cases. Each case is synthesized and linted on every change.
4. **Real deploy tests:** a nightly job deploys a rotating sample of combinations (including every database engine at least weekly) into a dedicated **platform test account**, runs connectivity checks (e.g. Lambda → RDS Proxy → Aurora with IAM auth), then deletes them.
5. **Reference patterns:** popular combinations are offered as one-click **patterns** in the UI, each fully deploy-tested. Examples:
   - REST API + Lambda + Aurora Serverless;
   - containerized service on ECS + ALB + RDS PostgreSQL + ElastiCache;
   - event pipeline (S3 → EventBridge → Step Functions → Lambda → DynamoDB);
   - streaming (Kinesis → Lambda → OpenSearch);
   - data lake (S3 + Glue + Athena + Lake Formation).

#### 6.8.7 Governance for a large catalog

- **Enablement:** admins enable services per environment tier and per portfolio (e.g. Neptune allowed in sandbox only until reviewed). Disabled services are hidden in the UI and also denied by SCP, so the rule holds outside the platform too.
- **Cost visibility:** the preview shows an indicative monthly cost per environment for each resource. It is computed in-house from the **AWS Price List API** (AWS service, no third-party tool).
- **Quotas:** the preview warns when a combination would approach an account quota (e.g. VPC security groups, Lambda concurrency), using the Service Quotas API.
- **Deprecations:** when AWS deprecates a resource type, property or engine version, the catalog sync flags the affected projects and the platform opens upgrade PRs on their infrastructure repos.

---

## 7. GitHub repository provisioning

### 7.1 Identity: GitHub App (recommended)
1-hour installation tokens, per-installation rate limits, and an audit trail as a bot. Permissions:

| Permission | Level | Used for |
|---|---|---|
| Administration | write | Create/delete repos, custom properties |
| Contents | write | Commit |
| **Workflows** | write | Required to commit anything under `.github/workflows/` |
| Secrets | write | Only for long-lived credentials mode (§8.7); not needed with OIDC |
| Variables | write | Actions variables |
| Environments | write | Create one GitHub environment per configured environment |
| Actions | read | Run status |
| Deployments | write | Run status; **submit reviewer approvals from the release console** (as the reviewer, via user-to-server token, §8.5) |
| Members | read | Resolve reviewer teams |

Webhooks: `workflow_run`, `deployment`, `deployment_status`, `deployment_review`, `deployment_protection_rule`. GitHub Apps can create repos in **organizations**; personal-account repos are out of scope for v1.

### 7.2 Provisioning steps (each step is safe to retry)

| # | Step | How | Retry / idempotency approach | Undo (before the commit) |
|---|---|---|---|---|
| 1 | Create repo | `POST /orgs/{org}/repos` (`auto_init: true`). Set **custom properties** `portfolio`, `product`, `project`; grant the product's GitHub access team (from the registry) the `maintain` role. | Name exists → check the ownership marker (custom property `provision-request`); resume if ours, otherwise fail with a name conflict | Delete the repo (only if this job created it) |
| 2 | Bootstrap AWS **per enabled environment** (in parallel) | AssumeRole `CloudInfraProvisioner` in each target account → create/update `cloudinfra-bootstrap-{project}` (tagged roles, OIDC trust for `repo:{owner}/{repo}:environment:{env}`) | CloudFormation `ClientRequestToken`; create-or-update | Delete the bootstrap stack in each account where it was created |
| 3 | GitHub environments | `PUT /repos/{o}/{r}/environments/{env}` for each enabled environment, with protection rules from that environment's protection profile (§5.5) (branch policies; for STAGE and PROD: required reviewers from the registry, prevent self-review, plus a separate `{env}-plan` environment without reviewers, §8.3) | `PUT` can safely be repeated | Removed when the repo is deleted |
| 4 | GitHub variables | Repository variables (project + ownership tags) and **environment variables per enabled environment** (`ENVIRONMENT_NAME`, `AWS_ACCOUNT_ID`, `AWS_REGION`, `AWS_ROLE_ARN`, `CFN_EXEC_ROLE_ARN`, `ARTIFACT_BUCKET`). Full list in §5.5.5. No secrets in OIDC mode. | Create-or-update (`POST`, then `PATCH` on 409) | Removed when the repo is deleted |
| 5 | **Atomic commit** | Git Data API: create tree (all files) → create commit → fast-forward `refs/heads/main` (`force: false`) | Skip if `main` already has the job's commit trailer | **None.** The repo is kept from here on |
| 6 | Track promotion | `deployment_status` / `workflow_run` webhooks per environment; reconciler as a backup | Matched by `head_sha` + environment | — |

**Why variables are set before the commit:** pushing `deploy.yml` starts the workflow at once.

**Why the Git Data API:** one commit appears all at once. The per-file contents endpoint would create N commits and N workflow runs.

**Why environment-scoped values:** each environment's job sees only its own account's role. A DEV job cannot even read the PROD role ARN.

### 7.3 Rate limits and API etiquette
- Honor `x-ratelimit-remaining` / `reset` and `retry-after`. Otherwise use exponential backoff with full jitter (1 s base, 60 s cap, 6 attempts).
- Content-creating calls are serialized per installation, at least 1 s apart (token bucket, §12.3).
- Webhooks instead of polling; conditional requests (`304`s are not counted against the limit).
- A project with 5 environments needs roughly 25–30 write calls. At 1 write/s per installation, that is about 30 s of GitHub time per project, which is why provisioning is async and queued.

---

## 8. Deployment pipeline (GitHub Actions + OIDC, configurable environments)

### 8.1 Trust model per environment

```mermaid
flowchart LR
  subgraph GHJ["GitHub job: environment = dev"]
    J["deploy-dev"] -->|"JWT sub = repo:acme-platform/invoice-ingest:environment:dev"| X[" "]
  end
  X -->|"AssumeRoleWithWebIdentity"| STS["STS in DEV account"]
  STS -->|"trust: aud + sub exact match"| DR["GitHubDeployRole (DEV)<br/>tags: org:project=invoice-ingest,<br/>org:environment=dev, …"]
  DR -->|"CreateChangeSet with stack tags<br/>(must equal role tags)"| CFN["CloudFormation"]
  CFN -->|"assumes"| ER["CfnExecutionRole (DEV)<br/>same tags · cloudinfra-exec-abac"]
  ER -->|"create/update only own-tagged resources"| APP["invoice-ingest stack"]
```

- A token for `environment:dev` matches **only** the DEV account's role trust. Separate accounts + exact `sub` matching mean no environment can reach another environment's account.
- Hardening: customize the OIDC `sub` to include `repository_id`, so a deleted-and-recreated repo with the same name doesn't inherit trust.

### 8.2 Promotion flow

```mermaid
flowchart LR
  PR["Pull request"] --> V["validate<br/>lint · guard · unit tests<br/>(no AWS access)"]
  FB["Any branch<br/>(manual dispatch)"] --> SBX["deploy: sandbox"]
  M["push to main"] --> V2["validate"] --> BLD["build once<br/>(starter mode: zip src/*;<br/>split model: no code build)"]
  BLD --> DEV["deploy: dev<br/>+ smoke tests"]
  DEV --> TEST["deploy: test<br/>+ integration tests"]
  TEST --> CSS["plan: stage<br/>(create change set only)"] --> AS{"Reviewer approval<br/>(required, release console)"} --> STG["deploy: stage<br/>release executor applies<br/>reviewed change set + UAT checks"]
  STG --> CSP["plan: prod<br/>(create change set only)"] --> AP{"Reviewer approval<br/>(required, release console)"} --> PRD["deploy: prod<br/>release executor applies<br/>reviewed change set + checks"]
```

- **Build once:** one zip per function per commit, uploaded to the regional artifact bucket at a key based on content. Every environment deploys that exact key. No rebuilds between environments.
- **Change set before approval:** for STAGE and PROD, a plan job creates the change set and writes its summary (replacements and deletions highlighted) to the job summary. Reviewers approve with the exact change in front of them, and only that change set is executed (§8.3).
- **Sandbox** deploys can come from any branch via manual dispatch. Stacks get `org:expires-on` and are removed by the sandbox cleanup job.

### 8.3 Approval gates: STAGE and PROD require GitHub reviewer approval before deployment

**Rule:** nothing is deployed to STAGE or PROD until a GitHub reviewer approves. The approval happens **before** the deploy job starts. Until then the job has no OIDC token and no AWS access, so nothing in the account can change.

**How it works: plan, approve, then apply the reviewed change set.** The diagram and table below show the flow with GitHub environment reviewers (**Mode B**). In the default **Mode A** (§8.3.1) the steps are the same, except that approval happens in the release console and the **platform release executor**, not a GitHub job, executes the change set.

```mermaid
sequenceDiagram
  autonumber
  participant P as plan-stage job<br/>(GitHub env: stage-plan, no reviewers)
  participant AWS as STAGE account
  actor R as Reviewer (from registry)
  participant D as deploy-stage job<br/>(GitHub env: stage, required reviewers)
  P->>AWS: OIDC → StagePlanRole: CreateChangeSet (name = cs-{sha}-{run})
  AWS-->>P: change set summary (adds / modifies / replacements / deletes)
  P->>P: write summary to job summary, pass change set name as job output
  Note over D: job waits: "Review deployments" in GitHub
  R->>D: Approve (or Reject), with the change set summary in front of them
  D->>AWS: OIDC → GitHubDeployRole: ExecuteChangeSet(cs-{sha}-{run}) only
  AWS-->>D: UPDATE_COMPLETE / rollback + events
```

| Item | Design |
|---|---|
| GitHub environments | Two per gated stage: `stage-plan` / `stage` and `prod-plan` / `prod`. Only `stage` and `prod` have **required reviewers**. The plan environments have a branch rule (`main`) but no reviewers. |
| Plan role (`{project}-plan`, per gated account) | Trusted only for `sub = repo:{owner}/{repo}:environment:{env}-plan`. Can create, describe and delete change sets on its own stack (same tag rules as §4.5) and read the artifact. **Cannot execute change sets** or touch resources. |
| Deploy role in gated accounts | **Mode A:** there is no GitHub-assumable deploy role in STAGE/PROD; only the platform release executor can execute. **Mode B:** for STAGE and PROD it may **only execute an existing change set** (plus describe). It cannot create a new change set, so what runs is exactly what was reviewed. If the stack changed after the plan, execution fails and the pipeline re-plans; reviewers then approve the new plan. |
| Reviewers | Set on each environment from the registry: the product's reviewer GitHub team(s) per environment (default: QA reviewers for STAGE; product owner group + change management for PROD). Up to 6 users/teams per environment; one approval releases the job. |
| Prevent self-review | Enabled on `stage` and `prod`: the person who triggered the run cannot approve it. |
| Branch rule | `stage` and `prod` deploy only from `main` (PROD optionally also from release tags). |
| Wait timer | Optional on `prod` (e.g. 15 min after approval), for a final cancel window. |
| Timeouts | A pending approval expires after 30 days (GitHub limit). The job is marked "Awaiting approval" in the platform UI until then; no AWS change happens. Rejection stops the promotion and leaves the environment untouched. |
| Audit | GitHub records who approved/rejected, when, and the comment. The platform stores it with the job (via `deployment_status` / `deployment_review` webhooks) next to the change set ID and the CloudTrail `ExecuteChangeSet` event. |

**The gate cannot be turned off**
- In the environment configuration (§5.5.1), `requiresApproval` is **locked to `true` for STAGE and for every `prod`-tier environment**. Admins can change *who* reviews, but cannot remove the gate. Any new environment of tier `prod` gets the gate automatically.
- Approval is checked by the platform before the release executor runs (Mode A), so no repo setting can bypass it. In Mode B, the product's GitHub team also has only the `maintain` role, so it cannot edit environment protection rules.
- The reconciler checks every repo's `stage` and `prod` environments nightly. Missing reviewers, disabled prevent-self-review or a changed branch rule is **restored automatically and alerted**.
- AWS backs it up: in gated accounts, only the release executor (Mode A) or an execute-only deploy role (Mode B) can apply changes, and only to existing, reviewed change sets. Even a workflow edited to skip the plan job cannot deploy new changes to STAGE or PROD.

#### 8.3.1 Approval enforcement modes (no paid GitHub features required)

GitHub's environment required reviewers and custom deployment protection rules need **GitHub Enterprise Cloud** for private and internal repos. So the design does **not depend on them**. The default mode gives the same guarantee on any GitHub plan.

| | **Mode A: platform-executed release (default, any GitHub plan)** | **Mode B: add GitHub environment protection (optional, Enterprise)** |
|---|---|---|
| Plan | GitHub job creates the change set with the plan role (as above) | Same |
| Approval | Reviewers approve in the **release console** (§8.5). They sign in with their **GitHub identity** (OAuth); the platform checks live, via the GitHub API, that they are in the product's reviewer GitHub team for that environment and not the person who triggered the run. | Mode A approval **plus** GitHub required reviewers on the `stage`/`prod` environments (submitted from the console as the reviewer) |
| Who executes | The platform's **release executor** executes the exact reviewed change set (or, for application deploys, releases the exact reviewed artifact, §9.7). GitHub Actions **holds no execute permission** in STAGE/PROD accounts. | Same, or the GitHub deploy job executes it after GitHub approval |
| AWS-side guarantee | Only the executor role can execute change sets/releases in gated accounts. It is assumable only from the Platform account (`aws:PrincipalOrgID` + ExternalId), and **only with a session tag `org:project`**, so even the executor is limited by tags to one project per session. | Same |
| Record of approval | Release record (who, when, comment, evidence); also written back to GitHub as a **deployment status and commit status** on the SHA, so the approval is visible in GitHub | GitHub audit log as well |

**Mode A sequence (STAGE shown; PROD is identical):**
1. `plan-stage` job (GitHub): creates change set `cs-{sha}-{run}`, posts the summary and evidence to the platform.
2. Gate service: evaluates G4 (§8.4). If it fails, stop.
3. Release console: reviewer approves.
4. Release executor: assumes `PlatformReleaseExecutor` in the STAGE account with session tag `org:project=invoice-ingest`, executes `cs-{sha}-{run}`, and waits for completion.
5. Status flows back to the GitHub run (the waiting `release-stage` job polls the platform API, or a `repository_dispatch` updates it) and to the release console.

Why this is at least as strong as GitHub reviewers alone:
- The only identity that can change STAGE/PROD is the platform executor, and it acts only on approved, gate-passed change sets.
- An edited workflow, a leaked GitHub token or a compromised runner cannot deploy to STAGE/PROD in either mode.
- The gate rules live in the platform, not in repo YAML.


### 8.4 Quality gates for STAGE and PROD (recommended strategy)

**Recommendation:** build the quality gate as **layered, evidence-based gates**, with the final decision made by a **central gate service in the platform** that is plugged into GitHub as a **custom deployment protection rule** on the `stage` and `prod` environments. Human reviewer approval (§8.3) is the last layer, not the only one.

Why this approach:
- **The gate's rules live in the platform, not in each repo's YAML.** A team cannot weaken them by editing the workflow, and changing a rule for all repos is one change in one place.
- **Decisions are based on evidence tied to the exact commit and artifact.** "TEST passed" means TEST passed for *this* SHA and *this* artifact digest, not just the latest run.
- **Reviewers get the full evidence in one summary**, so approval is an informed decision rather than a click.
- **AWS still has the final say.** The gated deploy role can only execute a reviewed change set (§8.3).

#### 8.4.1 The gate layers

```mermaid
flowchart LR
  G1["G1 · Pull request<br/>required checks + code review"] --> G2["G2 · Build<br/>SBOM · vuln scan · signed provenance"]
  G2 --> G3["G3 · DEV / TEST<br/>smoke + integration tests"]
  G3 --> G4["G4 · Pre-STAGE automated gate<br/>change set risk · drift · policy checks"]
  G4 --> H1{"Reviewer approval<br/>STAGE"}
  H1 --> S["STAGE deploy<br/>+ UAT · alarms"]
  S --> G5["G5 · Pre-PROD automated gate<br/>bake time · STAGE health · same artifact ·<br/>change window · change record"]
  G5 --> H2{"Reviewer approval<br/>PROD"}
  H2 --> P["PROD deploy<br/>alarm-based rollback"]
  P --> G6["G6 · Post-deploy verification"]
```

| Gate | When | Checks | Blocks on | Enforced by |
|---|---|---|---|---|
| **G1 · Pull request** | Before merge to `main` | cfn-lint; cfn-guard (all environment rule sets, so a PROD violation is caught early); IaC security scan (Checkov); unit tests + coverage threshold; SAST (bandit / SpotBugs+FindSecBugs / gosec / cargo-audit / eslint-plugin-security); dependency scan (OSV-Scanner); secret scanning (gitleaks); 1 code review from the product's team (CODEOWNERS) | Any failure | GitHub **ruleset** on `main` (required status checks + required review), set by the platform at repo creation and checked by the reconciler |
| **G2 · Build** | Once per commit on `main` | SBOM (Syft); vulnerability scan of the bundle (Trivy / OSV-Scanner); **signed provenance**: cosign signature with an AWS KMS key plus a SLSA provenance statement binding the artifact digest to the commit and workflow run | Critical/high vulnerabilities without an approved exception; missing attestation | Build job; digest + results recorded as evidence |
| **G3 · DEV / TEST** | After each deploy | DEV: smoke tests. TEST: integration/contract tests against the deployed stack; results published as check runs | Any failed suite | `needs:` in the workflow + evidence record |
| **G4 · Pre-STAGE** | In `plan-stage`, before approval | Evidence check: G1–G3 passed **for this SHA and digest**. Attestation verified. **Change set risk analysis** (below). **Drift detection** on the STAGE stack. **IAM Access Analyzer custom policy checks**: no new access compared with the currently deployed template (`CheckNoNewAccess`) and no forbidden actions (`CheckAccessNotGranted`) | Any failed check; high-risk change without an explicit override | Gate service (Mode A: before the release executor; Mode B: also as a deployment protection rule) |
| **Reviewer (STAGE)** | After G4 passes | Human approval with the evidence summary | Rejection / no approval | GitHub required reviewers (§8.3) |
| **G5 · Pre-PROD** | In `plan-prod`, before approval | Everything in G4 for the PROD stack, plus: **same artifact digest that ran in STAGE**; STAGE **bake time** met (e.g. ≥ 24 h, set per environment); STAGE CloudWatch alarms **green** during the bake; UAT sign-off recorded; **change window** open / no freeze; optional **change record** approved (built-in; external ITSM only via webhook if an organization wants it); for DR/HA projects, a **successful STAGE DR drill** within the last 30 days and a healthy secondary region (§10.7) | Any failed check | Gate service (Mode A: before the release executor; Mode B: also as a deployment protection rule) |
| **Reviewer (PROD)** | After G5 passes | Human approval with the evidence summary | Rejection / no approval | GitHub required reviewers (§8.3) |
| **G6 · Post-deploy** | During and after the PROD deploy | CloudFormation **rollback triggers** (`RollbackConfiguration` with CloudWatch alarms and a monitoring window) roll the stack back automatically if alarms fire; post-deploy health checks | Alarm during the monitoring window → automatic rollback | CloudFormation + pipeline |

#### 8.4.2 Change set risk analysis (G4/G5)

The plan job sends the change set to the gate service, which classifies every change:

| Risk | Examples | Default outcome |
|---|---|---|
| **High** | Replacement or deletion of a stateful resource (S3 bucket, DynamoDB table); deletion of a log group in PROD; removing `DeletionPolicy: Retain`; disabling encryption or versioning | **Blocked**, unless the change carries an explicit, separately approved override (e.g. a `allow-destructive-change` label approved by a platform admin). The override is recorded. |
| **Medium** | Any IAM policy or role change; new S3 notification or Lambda permission; runtime change | Allowed, but **highlighted** at the top of the reviewer summary |
| **Low** | Code-only update; memory/timeout change; tag change | Allowed |

#### 8.4.3 Where the evidence lives

- The gate service keeps a **release record** per commit SHA: artifact digest and attestation, test and scan results per environment, change set IDs and risk classification, drift result, approvals (who, when, comment), and deploy outcome.
- Workflows post results to the platform with the job's OIDC token, so the platform can verify which repo, environment and run sent them.
- The same record feeds the reviewer summary, the platform UI and audit (§14).

#### 8.4.4 How the gate plugs into GitHub

In **Mode A** (default) the gate is checked by the platform before the release executor runs, with no GitHub feature needed. In **Mode B** it is also connected to GitHub as follows:

- The platform's GitHub App is registered as a **custom deployment protection rule** on every `stage` and `prod` environment, set at repo creation and checked by the reconciler.
- When a `deploy-stage` / `deploy-prod` job is about to start, GitHub sends a `deployment_protection_rule` event. The gate service evaluates G4/G5 and answers approve or reject, with a link to the evidence.
- The job starts only when **both** the gate service and a human reviewer approve. If the gate rejects, reviewers are never asked.
- **Mode A (default, any plan):** the gate service is evaluated by the platform itself before the release executor runs (§8.3.1). The deployment protection rule integration above applies only in **Mode B** (GitHub Enterprise).

#### 8.4.5 Gate settings are configurable per environment

These thresholds are part of the environment's `guardrailProfile` (§5.5.1) and are edited by platform admins:
- coverage minimum;
- allowed vulnerability severity;
- bake time;
- change windows / freeze calendar;
- whether a change record is required;
- which risk levels need an override.

The **gates themselves cannot be disabled for STAGE or prod-tier environments**; only their thresholds can be tuned.

#### 8.4.6 Later improvement (not v1)
For PROD Lambda deployments, add **gradual traffic shifting** (Lambda alias + CodeDeploy canary, e.g. 10% for 10 minutes, then 100%) with alarm-based automatic rollback. This limits the impact of a bad release to a small share of traffic.

### 8.5 Release console: the approval workflow in the platform UI

**Recommendation:** the platform UI provides the whole promotion and approval workflow, and **GitHub remains the record of approvals**. When a reviewer clicks *Approve* in the platform, the platform calls GitHub's *review pending deployments* API **as that reviewer**, using their own GitHub identity. So:
- it is a real GitHub reviewer approval: the required-reviewer rule, prevent-self-review and GitHub's audit log all still apply;
- reviewers never need to leave the platform;
- approving directly in GitHub still works, and the platform reflects it within seconds via webhooks.

#### 8.5.1 Screens

| Screen | Who | What it shows / does |
|---|---|---|
| **Project pipeline view** | Everyone entitled to the product | One column per environment in configured order. Each column shows: state, commit SHA, artifact digest, who triggered, when, gate results (G1–G6) as green/red chips, and links to the GitHub run and the CloudFormation stack. |
| **My approvals (inbox)** | Reviewers | All pending STAGE/PROD approvals across the products where the user is a reviewer, oldest first, with waiting time. |
| **Approval detail** | Reviewers | The evidence summary from the release record (§8.4.3), on one page: <br/>• change set diff grouped by risk, with high-risk items on top<br/>• test and scan results<br/>• drift result<br/>• for PROD: STAGE bake time and alarm health, and confirmation that the artifact is the same one that ran in STAGE<br/>• change ticket link<br/>Plus a comment box and **Approve** / **Reject** buttons. *Approve* stays disabled until the automated gate (G4/G5) has passed. |
| **Override requests** | Requester → platform admin | Request an override for a high-risk change (§8.4.2) with a reason; a platform admin approves or rejects it in the UI. The override applies only to that change set. |
| **Release history** | Everyone entitled; auditors | Every promotion per environment: who requested, which gates passed, who approved/rejected and why, outcome, rollback events. Exportable. |

#### 8.5.2 Promotion state machine (per commit, per gated environment)

```mermaid
stateDiagram-v2
  [*] --> Waiting: previous environment succeeded
  Waiting --> Planning: plan job started
  Planning --> GateChecking: change set created
  GateChecking --> GateFailed: G4/G5 failed
  GateChecking --> OverrideRequested: high-risk change
  OverrideRequested --> GateChecking: admin approved override
  OverrideRequested --> Rejected: admin rejected override
  GateChecking --> AwaitingApproval: automated gate passed
  AwaitingApproval --> Approved: reviewer approved (UI or GitHub)
  AwaitingApproval --> Rejected: reviewer rejected
  AwaitingApproval --> Expired: 30 days, no decision
  AwaitingApproval --> Superseded: newer commit planned for this environment
  Approved --> Deploying: deploy job executes reviewed change set
  Deploying --> Deployed
  Deploying --> RolledBack: deploy failed / alarm rollback
  GateFailed --> [*]
  Rejected --> [*]
  Expired --> [*]
  Superseded --> [*]
  Deployed --> [*]
  RolledBack --> [*]
```

- **Superseded:** if a newer commit reaches the same gate, the older pending approval is closed automatically, so reviewers only see the latest candidate.
- The state is driven by GitHub webhooks (`workflow_run`, `deployment`, `deployment_status`, `deployment_review`, `deployment_protection_rule`) and the gate service, stored in the job/release tables (§3.4).

#### 8.5.3 How an approval in the UI reaches GitHub (Mode B only)

In **Mode A** (default), an approval in the console goes straight to the release executor (§8.3.1), and the platform writes a deployment status and commit status back to GitHub. The sequence below applies only when GitHub environment reviewers are also enabled (Mode B).

```mermaid
sequenceDiagram
  autonumber
  actor R as Reviewer
  participant UI as Release console
  participant API as Platform API
  participant GS as Gate service
  participant GH as GitHub
  GH->>GS: deployment_protection_rule (deploy-prod waiting)
  GS->>GS: evaluate G5 → pass
  GS->>GH: approve protection rule (automated part)
  GS-->>UI: inbox item "invoice-ingest → PROD awaiting approval"
  R->>UI: open evidence, comment, Approve
  UI->>API: POST /v1/approvals/{id}:approve
  API->>API: check: reviewer group for product+env, not the requester, gate passed, still latest
  API->>GH: POST /repos/{o}/{r}/actions/runs/{run}/pending_deployments<br/>(state=approved, environment=prod, comment) using the reviewer's GitHub user token
  GH-->>API: 200, deploy-prod job starts
  GH-->>API: deployment_review webhook → release record updated
```

- **Reviewer identity:** each reviewer links their GitHub account once (GitHub App user authorization, OAuth). The platform stores the refresh token encrypted. It uses the token only to submit approvals, and only for runs in that reviewer's own products.
- **Double check on our side:** before calling GitHub, the platform checks that the user is in the product's reviewer group for that environment, is not the person who triggered the run, and that the automated gate passed. GitHub then enforces its own rules again.
- **Notifications:** new pending approvals, gate failures, rejections and rollbacks go to the **in-app inbox** and **email via Amazon SES**, with a deep link to the approval detail page. Generic **signed outgoing webhooks** let an organization forward events to any chat tool it uses, without the platform depending on that tool. Reminders go out after a configurable wait (e.g. 4 h).
- **Promotion mode** (configurable per environment, §5.5.1):
  - `auto`: STAGE plan starts automatically after TEST succeeds.
  - `on-request`: a user clicks **Promote to STAGE/PROD** in the UI, which starts the plan job via `workflow_dispatch`.

  Either way, the approval is still required.

#### 8.5.4 Separation of duties
- Requester ≠ approver (platform check + GitHub prevent self-review).
- PROD can require **two approvals from different groups** (e.g. product owner and change management). The platform collects both in the UI and submits the GitHub approval only when both are in. This requires that only the platform's approver identities be listed as GitHub reviewers; the alternative is GitHub's own single-approval model.
- Platform admins can approve overrides but cannot approve their own requests.

### 8.6 `deploy.yml` — design (not code yet)

| Aspect | Design |
|---|---|
| Triggers | `push` to `main`; `pull_request` (validate only); `workflow_dispatch` with an environment input (sandbox, or re-run any stage) |
| Permissions | `id-token: write`, `contents: read` |
| Structure | A reusable workflow `deploy-env.yml` (inputs: environment) holds all deploy steps and is identical in every repo. The caller `deploy.yml` is **generated from the environment configuration**: one job per enabled environment, chained in the configured order; gated environments (STAGE, PROD) get a `plan-{env}` job followed by a `deploy-{env}` job, with the quality gate (§8.4) and reviewer approval (§8.3) between them. If admins change the environment list later, the platform opens a "sync pipeline" PR in affected repos instead of changing them silently. |
| Concurrency | One group per environment (`deploy-{env}`), `cancel-in-progress: false` |
| Supply chain | Actions pinned to commit SHAs (only GitHub-owned `actions/*`, `aws-actions/*` and the platform's own actions are allowed); Dependabot |
| Per-environment job steps | 1. OIDC credentials (`role-to-assume: vars.AWS_ROLE_ARN`, `aws-region: vars.AWS_REGION`, scoped to that GitHub environment)<br/>2. **Guard:** caller account must equal `vars.AWS_ACCOUNT_ID` and `vars.ENVIRONMENT_NAME` must equal the job's environment<br/>3. **Pre-flight stack-state check** (table below)<br/>4. `aws cloudformation deploy` with `--role-arn $CFN_EXEC_ROLE_ARN`, `--parameter-overrides` from `config/{env}.json` + code prefix, `--tags` = the full `org:*` set built from GitHub variables (`vars.ORG_*`, `vars.PROJECT_NAME`, `vars.ENVIRONMENT_NAME`), `--no-fail-on-empty-changeset` (**DEV/TEST/sandbox only**; STAGE/PROD use the plan → approve → execute flow in §8.3)<br/>5. Post-deploy checks; outputs to job summary<br/>6. On failure: failed stack events (resource, type, reason) to job summary, exit non-zero |

Tags passed with `--tags` come from GitHub variables set by the platform (§5.5.5). **Even if someone changes them, IAM denies any value that doesn't match the deploy role's tags (§4.4).**

| Stack status before deploy | Action |
|---|---|
| does not exist | create via changeset |
| `CREATE_COMPLETE` / `UPDATE_COMPLETE` / `UPDATE_ROLLBACK_COMPLETE` | update via changeset |
| `ROLLBACK_COMPLETE` (first create failed) | delete the empty stack, then create again (safe: `RetainExceptOnCreate`) |
| `*_IN_PROGRESS` | wait with timeout |
| `UPDATE_ROLLBACK_FAILED` / `DELETE_FAILED` | stop with a runbook link. Never automated. |

### 8.7 Long-lived credentials mode (supported, not recommended)
Only where an account cannot have an OIDC provider:
- A per-project, per-environment IAM user with the same shared policy, **tagged identically**.
- Keys stored as **environment secrets** (the only secrets in the design; everything else stays a variable); ≤ 90-day rotation enforced by a platform job; warning shown in the UI.

---

## 9. Developer consumption: application repositories

### 9.1 The problem and the recommended model

The repos the platform generates (§7) are **infrastructure repos**: they define the AWS resources, the IAM roles and the event wiring for one project. Developers write their actual code (Python, Java, Go, Rust, Node.js, …) in **application repos**, and deploy it to ECS, Lambda, EKS or Step Functions *on top of* that infrastructure. Two things are needed:
1. a reliable way for application repos to **find** the infrastructure (names, ARNs, roles, endpoints) in every environment;
2. a safe way for them to **deploy onto** it, without being able to create IAM, change network or data resources, or touch other projects.

**Recommendation: "infrastructure contract + golden-path pipelines".**
- Each infrastructure repo **publishes a versioned, machine-readable contract** per environment: what it provides and how to reach it.
- Application repos **declare which project and which compute slots** they deploy to, in one small file.
- Application repos deploy through **reusable, platform-owned GitHub workflows** (one per language and compute type). These read the contract at deploy time, so no ARNs or account details are copied into application repos.
- Application deploy roles use the **same tag-based permission model** (§4), but can only update the runnable artifacts of their bound slots. They can never create IAM roles or change data, network or trigger resources.

```mermaid
flowchart LR
  subgraph Infra["Infrastructure repo (platform-generated)<br/>invoice-ingest-infra"]
    T["template.yaml · infra.json"]
  end
  subgraph Acct["Each environment account"]
    STK["Infra stack<br/>buckets · tables · queues · roles ·<br/>Lambda shell · ECS service · namespace · SFN role"]
    SSM[("SSM Parameter Store<br/>/platform/projects/invoice-ingest/contract")]
    APPSTK["App resources<br/>code versions · task definitions ·<br/>pods · state machine definitions"]
  end
  subgraph Apps["Application repos (developer-owned)"]
    A1["invoice-processor (Python)<br/>→ Lambda slot 'processor'"]
    A2["invoice-api (Java)<br/>→ ECS slot 'api'"]
    A3["invoice-worker (Go)<br/>→ EKS slot 'worker'"]
    A4["invoice-flow (ASL + Rust tasks)<br/>→ Step Functions slot 'flow'"]
  end
  PW["platform-workflows repo<br/>reusable build + deploy workflows (versioned)"]
  PORTAL["Platform UI / developer portal<br/>contract viewer · linked repos · how-tos"]

  T -->|"deploy (infra pipeline)"| STK --> SSM
  A1 & A2 & A3 & A4 -->|"uses: platform-workflows@v1"| PW
  PW -->|"read contract"| SSM
  PW -->|"deploy artifact (app deploy role)"| APPSTK
  SSM -. "published copy" .-> PORTAL
```

### 9.2 Who owns what: infrastructure vs application

The rule: **the infrastructure repo owns anything with identity, network, data or triggers. The application repo owns the runnable artifact and its runtime settings.**

| Compute type | Infrastructure repo owns (via the platform UI) | Application repo owns | How the app deploys |
|---|---|---|---|
| **Lambda** | Function "shell" (name, execution role, triggers such as S3 notifications, permissions, log group, concurrency, VPC config, binding env vars), a `live` alias, code-signing config in gated environments | Code, build, versions, which version `live` points to; app-level settings in AppConfig/SSM under the app path | Upload artifact → `UpdateFunctionCode` → `PublishVersion` → move `live` alias (later: CodeDeploy canary) |
| **ECS (Fargate)** | Cluster (per project, as clusters cost nothing), ECR repository, task role and task execution role, security groups, ALB target group/listener rule, log group, the ECS service (created with a platform placeholder image) | Dockerfile, image, task definition revisions (image digest, CPU/memory, env vars, health check) | Build image → push to ECR → register task definition (roles taken from the contract) → update service; ECS deployment circuit breaker with rollback |
| **EKS** | *Shared* cluster per portfolio per environment, run by the platform team (a cluster per project is too costly). Per project: namespace, ResourceQuota/LimitRange, NetworkPolicy, ServiceAccount + **EKS Pod Identity** association to a project role, ECR repository | Container image, Helm chart / Kustomize manifests **limited to its namespace** | Recommended: **GitOps with Argo CD**. The pipeline pushes the image and updates the image digest in the environment overlay; Argo CD syncs the namespace. Alternative: `helm upgrade --atomic` with a namespace-scoped role. |
| **Step Functions** | State machine execution role (allowed to call only the project's Lambdas/ECS tasks/resources), log group, X-Ray settings | The state machine definition (ASL) and any task code (which deploys to its own Lambda/ECS slots) | Small **app stack** (CloudFormation) containing the state machine, with `DefinitionSubstitutions` filled from the contract; the definition is validated before deploy |

**Why this split:**
- Developers can ship code many times a day without touching security-sensitive resources.
- Every new permission, trigger or data store still goes through the platform UI → infrastructure repo PR → quality gates (§8.4) → approvals.
- Drift checks on the infrastructure stack **ignore the fields owned by the application** (Lambda code and alias version, ECS service task definition) so these updates are not flagged as drift.

**Infrastructure repo changes (supersedes the single-repo starter code):** in the recommended model, the infrastructure repo no longer contains application code. Lambda functions are created with a small **platform bootstrap package** for their runtime, and the infrastructure pipeline does not build code. A **"single-repo starter" mode** (code in `src/` inside the infrastructure repo, as in §6) is kept for sandbox prototypes only.

### 9.3 Catalog additions for compute slots

A **compute slot** is a catalog resource that application code is deployed into. Each slot is bound to exactly one application repo; one application repo may serve several slots (a monorepo).

| Type | Key settings | Contract exposes |
|---|---|---|
| `lambda.function` | runtime family (`python`, `java`, `nodejs`, `go`, `rust`, `container`), arch, memory, timeout, triggers via connections | function name/ARN, `live` alias ARN, runtime, handler convention, artifact location, signing profile |
| `ecs.service` | CPU/memory limits, desired count range, port, public/internal, health check path | cluster, service, task role ARN, execution role ARN, ECR URI, container name, log group, subnets/SGs (from the landing zone network via SSM), target group |
| `eks.workload` | target shared cluster, quota, service account | cluster name, namespace, service account, ECR URI, Argo CD application name |
| `stepfunctions.workflow` | type (standard/express), logging level | role ARN, log group ARN, substitution values for the project's resources |
| `ecr.repository` | (created automatically for container slots) | repository URI; immutable tags + scan on push |

Existing connection kinds still apply (e.g. `s3.notify` → `lambda.function`, `iam.access` from any slot's runtime role to a bucket/table). The existing `lambda.python` becomes `lambda.function` with `runtime: python`.

### 9.4 The infrastructure contract

**Published three ways after every successful infrastructure deploy, per environment:**

| Where | For | Notes |
|---|---|---|
| **SSM Parameter Store** in the environment account: `/platform/projects/{project}/contract` (JSON, advanced tier) plus one parameter per value under `/platform/projects/{project}/...` | Deploy pipelines and running code | Written as `AWS::SSM::Parameter` resources by the infrastructure stack itself, so it is always in sync with what is deployed. Readable only by roles tagged with the same project (ABAC on the path). |
| **Platform API / developer portal**: `GET /v1/projects/{id}/contract?env=dev` | Humans, tooling, local development | Copy recorded in the release record with the infra commit SHA |
| **Infrastructure repo release** (GitHub Release asset `contract.{env}.json`, tagged with the infra version) | Review and diffing | Lets reviewers see contract changes between versions |

**Why SSM, not CloudFormation exports:** exports lock the exporting stack. A value that is imported elsewhere cannot be changed or removed, which would block infrastructure changes. SSM parameters keep stacks loosely coupled.

**Example contract (DEV):**

```json
{
  "contractVersion": "1",
  "project": "invoice-ingest",
  "environment": "dev",
  "accountId": "222222222222",
  "region": "us-east-1",
  "infraVersion": "1.4.0",
  "infraCommit": "4f78c64",
  "compute": {
    "processor": {
      "type": "lambda.function", "runtime": "python3.13", "architecture": "arm64",
      "functionName": "invoice-ingest--processor",
      "aliasArn": "arn:aws:lambda:us-east-1:222222222222:function:invoice-ingest--processor:live",
      "artifactBucket": "cloudinfra-artifacts-999999999999-us-east-1",
      "artifactPrefix": "apps/invoice-ingest/processor/",
      "boundRepo": "acme-platform/invoice-processor"
    },
    "api": {
      "type": "ecs.service",
      "cluster": "invoice-ingest--cluster", "service": "invoice-ingest--api",
      "containerName": "app",
      "ecrRepositoryUri": "222222222222.dkr.ecr.us-east-1.amazonaws.com/invoice-ingest/api",
      "taskRoleArn": "arn:aws:iam::222222222222:role/app/invoice-ingest/workload/…",
      "executionRoleArn": "arn:aws:iam::222222222222:role/app/invoice-ingest/workload/…",
      "logGroup": "/ecs/invoice-ingest--api",
      "boundRepo": "acme-platform/invoice-api"
    }
  },
  "resources": {
    "uploads": { "type": "s3.bucket", "name": "invoice-ingest--uploads-222222222222-us-east-1" }
  },
  "runtimeEnv": {
    "processor": { "UPLOADS_BUCKET_NAME": "invoice-ingest--uploads-222222222222-us-east-1" },
    "api":       { "UPLOADS_BUCKET_NAME": "invoice-ingest--uploads-222222222222-us-east-1" }
  }
}
```

**Contract versioning and compatibility:**
- `contractVersion` changes only for schema changes.
- Each infra change is classified by the gate service as **additive** (new slot/resource/value) or **breaking** (removed or renamed slot/resource, changed runtime family, changed container name).
- **Additive changes always flow freely.** Breaking changes follow the **expand → migrate → contract** rule (§9.9.4), so the platform team never has to wait for a product team to sign off, and nothing a deployed application uses disappears from under it.
- Application deploys check the contract in the target environment:
  - A **required** value that is missing stops that deploy with a clear message (*"DEV infrastructure does not yet provide `uploads`"*). Only the deploy stops; development carries on.
  - **Optional** values (§9.5) never block a deploy.
  - Infrastructure and applications are **promoted independently**.

### 9.5 Linking an application repo: `.platform/app.yaml`

Every application repo has one small, language-neutral file that says what it deploys and where:

```yaml
apiVersion: platform/v1
project: invoice-ingest            # the infrastructure project
components:
  - slot: processor                # compute slot in the infra contract
    type: lambda.function
    language: python               # python | java | go | rust | nodejs | container
    path: services/processor
    requires: [uploads]            # must exist in the target env, or this deploy waits
    optional: [archive]            # used if present; code handles absence (feature flag)
  - slot: api
    type: ecs.service
    language: java
    path: services/api
    build: { tool: gradle }
```

- **Binding is recorded in the platform, not trusted from this file.** The platform links slot → repo when the app repo is created (or linked) in the UI. The app deploy role's OIDC trust is limited to that repo, so a file in another repo claiming `project: invoice-ingest` gets AccessDenied.
- The file decides **how to build** and **which slots to deploy**. The contract decides **where**.

### 9.6 Golden-path pipelines (`platform-workflows` repo)

A central, versioned repo of **reusable GitHub workflows**. Application repos call them by tag; Dependabot pins and updates the commit SHAs. Builds are separate from deploys, so one artifact is built once and promoted through every environment, just like infrastructure (§8.2).

**Build workflows (per language):**

| Language | Lambda artifact | Container artifact (ECS/EKS) |
|---|---|---|
| Python | zip with dependencies (`pip install --target`, arm64 wheels) → `python3.x` runtime | Docker image |
| Java | jar/zip via Maven/Gradle → `java21` runtime (SnapStart optional) | Docker image (e.g. Jib or Dockerfile) |
| Go | `bootstrap` binary (`GOOS=linux GOARCH=arm64`) → `provided.al2023` | Distroless image |
| Rust | `bootstrap` via `cargo lambda build --arm64` → `provided.al2023` | Distroless image |
| Node.js | bundled zip (esbuild) → `nodejs22.x` | Docker image |

Every build: unit tests → SAST/dependency scan → SBOM → vulnerability scan → **signed provenance (cosign + AWS KMS)** → (Lambda) **AWS Signer code signing** → publish to the artifact bucket (zip) or ECR (image, by digest). This is the application version of gates G1–G2.

**Deploy workflows (per compute type):** `deploy-lambda.yml`, `deploy-ecs.yml`, `deploy-eks.yml` (GitOps update), `deploy-sfn.yml`. Each one:
1. Assumes the **app deploy role** for the environment via OIDC.
2. Reads the contract from SSM and checks `requires`.
3. Checks that the artifact's runtime family matches the slot (a Go binary cannot go to a Python slot).
4. Deploys and waits until healthy.
5. Rolls back on failure: Lambda alias back to the previous version, ECS circuit breaker, Argo CD rollback, SFN previous definition.
6. Reports to the release record.

Application repos get the **same environments, approvals and quality gates** as infrastructure repos:
- GitHub environments sandbox → PROD;
- required reviewers and the gate service for STAGE/PROD;
- the release console (§8.5) shows application promotions next to infrastructure promotions.

For application deploys, the "change set" the reviewer approves is a **deploy diff**: current vs new artifact digest, code/version hash, task definition diff and Kubernetes manifest diff.

### 9.7 Security for application deploys

**App deploy role** (per application repo, per environment, created by the platform):
- **Trust:** OIDC `sub = repo:{owner}/{app-repo}:environment:{env}`.
- **Tags:** same `org:*` tags as the project, so the same tag-based model applies (§4).
- **Shared policy:** `cloudinfra-appdeploy-abac`, which allows only:

| Allowed | Scope |
|---|---|
| `lambda:UpdateFunctionCode`, `PublishVersion`, `UpdateAlias`, `GetFunction` | Functions tagged with the same project **and** named after a slot bound to this repo |
| `ecs:RegisterTaskDefinition` (with own tags), `ecs:UpdateService`, `ecs:Describe*` | Services/task families of bound slots |
| `iam:PassRole` | Only roles under `/app/{project}/workload/`, only to `ecs-tasks.amazonaws.com` / `states.amazonaws.com`, as listed in the contract |
| `ecr:*Image*` push/pull actions | Repositories tagged with the same project |
| `ssm:GetParameter*` | `/platform/projects/${aws:PrincipalTag/org:project}/*` |
| `cloudformation:*ChangeSet*` on app stacks `{project}-app-*` | **With the `cloudformation:ResourceTypes` condition** limited to an allow-list (e.g. `AWS::StepFunctions::StateMachine`, `AWS::Lambda::Version`, `AWS::CloudWatch::Dashboard`) |
| `s3:PutObject` | `artifact-bucket/apps/{project}/*` |
| `eks:DescribeCluster` | Shared cluster (for GitOps, nothing else; Kubernetes access goes through Argo CD) |

**Gated environments (STAGE/PROD), Mode A:** the app deploy role only **prepares** a release: it uploads the artifact, publishes a Lambda version, registers a task definition revision, or proposes a GitOps commit. The **platform release executor** performs the traffic-affecting step after approval: moving the `live` alias, updating the ECS service, merging/syncing the GitOps change, or executing the app stack change set.

**Never allowed:** `iam:Create*`/`Put*`/`Attach*`, any change to buckets/tables/queues/VPC/security groups/triggers, any resource of another project.

**Extra safeguards:**
- A **CloudFormation Guard Hook** in every account rejects IAM, network and data resource types in stacks named `*-app-*`.
- **Artifact provenance in gated environments** (an AWS-side check in addition to GitHub approvals):
  - Lambda functions in STAGE/PROD have a **code signing config** that accepts only code signed by the platform build.
  - ECR repositories use immutable tags and deploys pin images by digest.
  - EKS admission policy (e.g. Kyverno) admits only images with a valid signature/attestation.
- **Runtime access:** running code uses the slot's runtime role (Lambda execution role, ECS task role, Pod Identity role, SFN role). Like every component, it can reach only resources with the same project and environment tags (§4.10). These are created by the infrastructure stack with exact-ARN policies and the shared boundary (§4.5), so application code has exactly the access drawn as connections in the platform UI.

### 9.8 How developers use it day to day

| Need | How |
|---|---|
| Start a new service | Platform UI → project → **"Create application repo"**: choose slot(s), language and compute type. The platform creates the repo with a language template, `.platform/app.yaml`, a workflow that calls the golden path, environments, protection rules and variables, using the same provisioning steps as §7. Or link an existing repo. |
| Find resource names/ARNs | Platform UI **contract viewer** per environment (copy buttons, diff between environments); `platform` CLI: `platform contract get invoice-ingest --env dev` |
| Use resources in code | Read the environment variables the deploy injects (`UPLOADS_BUCKET_NAME`, …). This works the same way in every language, with no platform SDK. The language templates include small examples (boto3, AWS SDK for Java v2, AWS SDK for Go v2, AWS SDK for Rust). |
| Get a new bucket/table/permission | Platform UI → **"Change infrastructure"** → the platform regenerates the template and opens a **PR on the infrastructure repo** → gates and approvals → infra promotes → the contract updates → the app can use it |
| Run or test locally | IAM Identity Center access to sandbox/DEV, with tag-based access to the product's resources (§4.8); `platform env export --env dev` writes the contract values as local env vars |
| Discover what exists | Platform UI project page (infra repo, bound app repos per slot, environments, versions). Each repo also gets a `catalog-info.yaml` so an open-source **Backstage** portal can show the same view, if you choose to run one (optional). |

**GitHub variables in application repos** (§5.5.5 rules apply). These are the only variables an application repo needs; everything else comes from the contract at deploy time:

| Variable | Level |
|---|---|
| `PROJECT_NAME` | Repository |
| `ENVIRONMENT_NAME` | Environment |
| `AWS_ACCOUNT_ID` | Environment |
| `AWS_REGION` | Environment |
| `AWS_ROLE_ARN` (the app deploy role) | Environment |
| `CONTRACT_PARAMETER` (`/platform/projects/{project}/contract`) | Repository |

**Repo visibility:** infrastructure repos are **internal** (readable by everyone in the GitHub org, writable only through the platform), so developers can read the template and the contract. Application repos follow the product's normal policy.

### 9.9 Working in parallel: how platform and product teams stay independent

Every solution has **two parts**:
1. **Infrastructure:** owned by the platform team. It is generated and changed through the platform and lives in the infrastructure repo.
2. **Solution code:** owned by the product team. It is written by developers in application repos and deployed onto the infrastructure.

The goal is that **neither team ever waits for the other**. The design achieves this with six mechanisms.

#### 9.9.1 Separate everything except the contract

| | Infrastructure | Solution code |
|---|---|---|
| Repo | `{project}-infra` (platform-generated) | one or more application repos |
| Owner | Platform team (product team can request changes via the UI) | Product team |
| Pipeline | Infra pipeline (§8) | Golden-path app pipelines (§9.6) |
| Version | `infraVersion` (semver, tagged in the infra repo) | each app's own version |
| Release schedule | Independent | Independent |
| Approvals/gates | Own GitHub environments + gates | Own GitHub environments + gates |
| AWS role | Infra deploy role + CFN execution role | App deploy role (only bound slots' artifacts) |
| **Shared** | **The contract only** (§9.4) | **The contract only** |

- **Neither pipeline ever triggers the other.** An infra deploy never redeploys code; an app deploy never changes infrastructure.
- **Each side owns its own fields, enforced by IAM, not by convention.** Infra deploys never touch app-owned fields (Lambda code/alias version, ECS task definition, Kubernetes manifests, ASL definitions). App deploy roles cannot touch infra-owned fields (§9.7). Drift checks ignore the other side's fields.

#### 9.9.2 Contract first: product teams can start before infrastructure exists

The contract exists in two forms:

| Form | When it exists | Used for |
|---|---|---|
| **Declared contract** | As soon as the project (or a change) is designed in the platform UI. It is generated from `infra.json` **before anything is deployed**. | Developers code against slot names, env var names and value types on day one |
| **Deployed contract** | Per environment, after each infra deploy (SSM, §9.4) | Actual values used by deploys and running code |

The platform UI shows both, side by side per environment ("declared, not yet deployed in TEST"). A product team can build, unit-test and even merge code that uses a resource the platform team has not deployed yet.

#### 9.9.3 Placeholders: infrastructure can ship before any solution code

Every compute slot is created with a **platform placeholder artifact**:
- a bootstrap Lambda package for each runtime that returns a clear "no application deployed" response;
- a placeholder container image with a health endpoint.

So the platform team can deploy, test and promote infrastructure to every environment with no application code present, and alarms and health checks still pass. When the product team's first deploy lands, it simply replaces the placeholder.

#### 9.9.4 Changing the contract without blocking anyone (expand → migrate → contract)

| Change | What happens | Who waits |
|---|---|---|
| **Additive** (new resource, slot, value, permission) | Deploys and appears in the contract; apps start using it when they're ready | Nobody |
| **Rename / replace** | **Expand:** the new value is added next to the old one; the old one is marked `deprecated` (with a removal-not-before date) in the contract. **Migrate:** product teams switch on their own schedule; the platform UI and PR comments remind them. **Contract:** the old value is removed automatically once no deployed app version in that environment still requires it. | Nobody. Removal waits for usage to reach zero, not for a person. |
| **Remove** | Same as above: deprecate → removal when unused | Nobody |
| **Emergency removal** (e.g. security issue) | Platform admin override, recorded; affected app owners notified | Explicit exception |

The platform knows exactly which value each **deployed** app version requires, because every app deploy records its `requires` list in the release record per environment. "Unused" is therefore a fact the platform can check, not a guess.

#### 9.9.5 Developing and testing solution code without the real infrastructure

| Need | Mechanism |
|---|---|
| Unit tests | Language templates include fakes/mocks for the AWS SDK calls they use; tests read the same env vars the deploy injects |
| Local integration | `platform dev up` starts **open-source emulators** (moto server; AWS SAM CLI for Lambda; LocalStack Community optional) configured from the **declared contract**: same bucket/table/queue names and env vars |
| Real AWS without waiting | **Ephemeral sandbox environments**: the platform deploys the declared infrastructure into the sandbox account with a TTL (`org:expires-on`) for a feature branch, without touching shared environments |
| Contract tests | The golden-path build checks the app's `requires`/`optional` against the declared contract (catches typos and stale names before any deploy) |

#### 9.9.6 Requests between teams are asynchronous

- **Product team needs new infrastructure:** "Change infrastructure" in the platform UI creates a **change request**. It immediately produces an updated **declared contract** (so developers can carry on) and a PR on the infra repo for the platform team. The app uses the new value as `optional` (behind a feature flag) until it is deployed, then switches it to `requires`.
- **Platform team improves infrastructure** (new runtime version, encryption change, shared cluster upgrade): it ships when ready. Additive changes need no coordination. Anything that affects apps goes through §9.9.4.
- **Visibility for both sides:** a per-project **compatibility view** in the platform UI shows, for each environment, the deployed infra version, the deployed app versions, and whether each app's needs are met, waiting or deprecated.

#### 9.9.7 Responsibilities

| Activity | Platform team | Product team |
|---|---|---|
| Catalog, building blocks, golden-path workflows, language templates | **Owns** | Consulted |
| Infra repo for a project (template, roles, wiring) | **Owns / approves** | Requests changes via UI |
| Contract schema and deprecation policy | **Owns** | Informed |
| Solution code, build, tests, app releases | Informed | **Owns** |
| App deploy approvals (STAGE/PROD) | — | **Owns** (product reviewers) |
| Infra deploy approvals (STAGE/PROD) | **Owns** (with product reviewers optional) | Consulted |
| Incident: app bug | Supports | **Owns** |
| Incident: infra/platform fault | **Owns** | Supports |

---

## 10. Multi-region resilience: DR and HA

### 10.1 Resilience modes

Every project chooses a **resilience mode** in the project wizard. Every template the platform generates is **multi-region capable from the start**, so a project can move from single-region to DR or HA later without redesign.

| Mode | Regions deployed | Regions active | Typical RTO / RPO | When to use |
|---|---|---|---|---|
| **Single region** | Primary only | Primary | Hours (redeploy from code + backups) / backup age | Sandbox, DEV, non-critical tools |
| **DR (active / standby)** | **Primary + secondary** | **Primary only.** Secondary is deployed, data replicates continuously, compute and event sources are inactive | Minutes to < 1 h / seconds to minutes (replication lag) | Business-critical workloads that can tolerate a short failover |
| **HA pair (active / active)** | **Primary + secondary** | **Both** | Near zero / near zero (depends on data store) | Customer-facing, always-on workloads |

**Regions are chosen in the UI.** **Any pair of two different regions is allowed.** The user picks the primary and secondary region from dropdowns in the project wizard; the selection becomes the project's DR/HA pair. The dropdowns are **pre-filled with us-east-1 (primary) / us-east-2 (secondary)**. Admins manage the list of enabled regions and the default pair in the UI (§10.9).

**DR strategy (DR mode only):**

| Strategy | Secondary compute while standby | RTO | Cost |
|---|---|---|---|
| **Pilot light** (default) | Scaled to zero / disabled | Longer (scale-up time) | Lowest |
| **Warm standby** | Minimal capacity running, no traffic | Shorter | Moderate |

### 10.2 What "deployed but inactive" means

The same template is deployed to both regions. Three parameters, set by the pipeline per region, decide the behavior:

| Parameter | Values | Set from |
|---|---|---|
| `ResilienceMode` | `single` \| `dr` \| `ha` | Project setting |
| `RegionRole` | `primary` \| `secondary` | Which region the stack is in |
| `ActivationState` | `active` \| `standby` | **DR:** primary `active`, secondary `standby`. **HA:** both `active`. Flipped only by a failover (§10.6). |

The engine wraps every activation-sensitive setting in CloudFormation **conditions** (`IsActive`, `IsPrimary`, `IsHA`), so **standby is a configuration of the same resources, not different resources**. Activating a region changes parameters, not the template.

```mermaid
flowchart LR
  subgraph DR["DR mode (active / standby)"]
    direction TB
    R53A["Route 53 failover record<br/>+ ARC routing control"] -->|"100%"| P1["us-east-1 · ACTIVE<br/>compute running · event sources on"]
    R53A -. "0% until failover" .-> S1["us-east-2 · STANDBY<br/>deployed · data replicating ·<br/>compute 0 · event sources off"]
    P1 -->|"replication"| S1
  end
  subgraph HA["HA pair (active / active)"]
    direction TB
    R53B["Route 53 latency / weighted<br/>+ health checks"] -->|"traffic"| P2["us-east-1 · ACTIVE"]
    R53B -->|"traffic"| S2["us-east-2 · ACTIVE"]
    P2 <-->|"bidirectional replication"| S2
  end
```

### 10.3 Per-service behavior

Every catalog entry (§6.8) declares a **multi-region capability**: `native-global`, `replicated`, `regional` or `not-supported`. The engine uses it to wire replication and standby behavior automatically, and the validation gate uses it to reject combinations that cannot meet the chosen mode.

| Service | DR: secondary in standby | HA: both active | Replication / global mechanism |
|---|---|---|---|
| **Lambda** | Deployed; reserved concurrency 0 (pilot light) or minimal (warm); event source mappings `Enabled: false`; S3/EventBridge triggers not attached | Deployed and triggered in both regions | Code uploaded to both regional artifact buckets |
| **ECS / Fargate** | Service deployed with desired count 0 (pilot light) or minimum (warm) | Desired count per region | ECR **replication** (push once, available in both regions) |
| **EKS workloads** | Argo CD app synced with replicas 0 (or minimum) | Replicas per region | Shared cluster must exist in both regions; ECR replication |
| **API Gateway / ALB** | Deployed; receives no traffic (Route 53 failover secondary) | Both in Route 53 latency/weighted set with health checks | Route 53 records + health checks in the global stack |
| **SQS / SNS** | Deployed, idle | Each region processes its own messages | Producers send to the active region(s) |
| **EventBridge** | Rules and schedules `DISABLED` | Enabled in both; optional **global endpoints** for event ingestion | Rules in both regions |
| **Step Functions** | Deployed; schedules/triggers disabled | Enabled in both | — |
| **S3** | Replica bucket receives **cross-region replication** | **Two-way replication** with replica-modification sync | Bucket names already include the region (§6.2) |
| **DynamoDB** | **Global table** replica in the secondary (data current, unused) | Global table, writes in both regions (last-writer-wins: app must be idempotent) | `AWS::DynamoDB::GlobalTable` |
| **Aurora (PostgreSQL / MySQL)** | **Aurora Global Database**; secondary cluster (headless in pilot light, one reader in warm standby) | Global Database; single writer in primary, **write forwarding** from the secondary; reads local | `AWS::RDS::GlobalCluster` + regional clusters |
| **RDS (non-Aurora)** | Cross-region read replica, promoted on failover | **Not supported** (single writer, no forwarding): validation offers Aurora or DynamoDB instead | Cross-region replica |
| **ElastiCache (Valkey / Redis OSS)** | Global Datastore secondary | Global Datastore (writes to primary) or independent regional caches | Global Datastore |
| **DocumentDB / Neptune** | Global cluster secondary | Single writer: reads local, writes to primary | Global clusters |
| **OpenSearch** | Cross-cluster replication follower | Two domains, app writes to both or replicates | Cross-cluster replication |
| **Secrets Manager** | Secret **replicated** to secondary | Replicated | Multi-region secrets |
| **KMS** | **Multi-Region keys** for anything replicated, so replicas decrypt locally | Multi-Region keys | `MultiRegion: true` |
| **SSM contract** (§9.4) | Written in both regions, with `regionRole` and `activationState` | Both | Each regional stack writes its own |
| **CloudFront / WAF / Route 53** | Global services: deployed once, in the global stack. CloudFront certificates (ACM) and CloudFront-scope WAF web ACLs **must live in us-east-1**, whatever the selected pair (§10.9) | Same | Origin groups for origin failover |
| **Cognito user pools** | **Limited**: no native replication; flagged in the preview with a documented pattern (or excluded from DR/HA projects) | Same | — |

**Validation examples:**
- *HA with RDS PostgreSQL* → rejected: "RDS PostgreSQL can be active in only one region. Use Aurora PostgreSQL Global Database (write forwarding) or DynamoDB global tables."
- *DR with a service marked `not-supported`* → warning with the expected RTO, and the service is redeployed from code during recovery.

### 10.4 Stack layout across regions

| Stack | Deployed in | Contains |
|---|---|---|
| `{project}-global` | **Primary region only** | Global or once-only resources: Route 53 records and health checks, ARC routing controls, CloudFront, WAF, `AWS::DynamoDB::GlobalTable`, `AWS::RDS::GlobalCluster`, Multi-Region KMS primary keys |
| `{project}-data`, `{project}-integration`, `{project}-compute`, `{project}-edge` (§6.8.5) | **Both regions** (same template, `RegionRole`/`ActivationState` parameters) | Regional resources and replicas |

- **IAM is global.** The project's deploy, plan and CFN execution roles (§4.5) are created once per account and used for both regions; the app execution roles created by regional stacks get CloudFormation-generated names, so the two regions never collide.
- Both regions of one environment use the **same AWS account** by default. A separate DR account per environment is an option (D31); the account bindings (§5.5.2) already carry a region per binding.
- **During a primary-region outage, the global stack cannot be changed** (its CloudFormation control plane is in the primary region). That is why failover never depends on it: data-plane controls (ARC, Global Database failover) are used instead, and the global stack is reconciled after recovery.

### 10.5 Pipeline: deploying to both regions

```mermaid
flowchart LR
  B["build once<br/>artifacts → both regional buckets ·<br/>image → ECR (replicated)"] --> G["deploy {project}-global<br/>(primary region)"]
  G --> P["deploy regional stacks<br/>us-east-1 · ActivationState=active"]
  P --> S["deploy regional stacks<br/>us-east-2 · DR: standby / HA: active"]
  S --> V["verify<br/>replication healthy · readiness checks"]
```

- **Order per environment:** global stack → primary region → secondary region → readiness checks (replication lag, Route 53 ARC readiness, health checks).
- **STAGE / PROD:** the plan job creates change sets for **every stack in both regions**. Reviewers approve **one release** covering all of them (§8.3), and the release executor applies them in the order above.
- **Failure handling:** if the secondary region fails to deploy, the primary keeps running the new version. The release is marked "secondary out of sync" and **blocks the next promotion** until fixed, because a DR region on an old version is not a valid DR target.
- **Application repos (§9)** follow the same pattern: artifacts are published to both regions, and code is deployed to both. In DR standby, the code is updated but stays inactive, so the standby always runs the same version as the primary.
- **Per-environment policy** (environment configuration §5.5.1), defaults:

| Environment | Default resilience |
|---|---|
| Sandbox, DEV | Single region always (cost) |
| TEST | Single region (DR/HA optional) |
| QA/STAGE | **Mirrors PROD's mode**, so failover can be tested before PROD |
| PROD | As selected by the project |

**New GitHub variables (§5.5.5 rules apply):**

| Variable | Level | Example |
|---|---|---|
| `RESILIENCE_MODE` | Environment | `dr` |
| `AWS_PRIMARY_REGION` | Environment | `us-east-1` (replaces `AWS_REGION`) |
| `AWS_SECONDARY_REGION` | Environment | `us-east-2` (empty for single-region) |
| `ARTIFACT_BUCKET_PRIMARY` / `ARTIFACT_BUCKET_SECONDARY` | Environment | regional Shared Services buckets |
| `ACTIVATION_STATE_SECONDARY` | Environment | `standby` (DR) / `active` (HA); changed only by failover |

### 10.6 Failover and failback (DR mode)

Failover is a **platform operation** started from the release console, not a code change.

| Step | Action | Depends on primary region? |
|---|---|---|
| 1. Declare | Incident lead clicks **Fail over to us-east-2** in the release console; **two approvers** (break-glass fast path, separate from release approvals) | No |
| 2. Data | **Aurora Global Database**: managed failover (planned) or detach-and-promote (unplanned). **RDS** replica promoted. DynamoDB global tables, S3, secrets: already current | No |
| 3. Compute | Release executor sets `ActivationState=active` on the **secondary regional stacks only** (scale up, enable event sources and rules) | No |
| 4. Traffic | Flip **Route 53 Application Recovery Controller** routing control to us-east-2 (data plane, highly available) | No |
| 5. Verify | Health checks, smoke tests, contract in us-east-2 shows `activationState=active` | No |
| 6. Record | Release record + GitHub variable `ACTIVATION_STATE_*` updated, so the next pipeline run keeps the new state | No |

**Failback** reverses the steps once the primary is healthy: re-establish replication toward us-east-1, sync, a planned switchover, flip traffic back, and set us-east-2 to standby. It is scheduled, approved like a PROD release, and never automatic.

**HA mode:** no failover action is needed. Route 53 health checks remove an unhealthy region automatically. Single-writer data stores (Aurora) follow their managed failover; the platform shows the writer location in the release console.

### 10.7 Continuous DR assurance

- **Readiness checks:** Route 53 ARC readiness checks confirm the secondary matches the primary (capacity settings, versions, replication). Drift is shown in the release console and blocks promotion.
- **DR drills:** a scheduled failover and failback in **QA/STAGE** (default monthly) for every DR/HA project, run by the platform with the steps above.
- **Gate G5 addition (§8.4):** a PROD release of a DR/HA project requires a **successful STAGE DR drill within the last N days** (default 30) and a healthy secondary in PROD.
- **Measured, not assumed:** each drill records the achieved RTO/RPO against the targets set in the wizard, shown per project.

### 10.9 Region selection: any pair, chosen in the UI

**User experience (project wizard):**
1. Choose **Resilience**: single region / DR / HA pair.
2. Choose **Primary region** (dropdown) and, for DR/HA, **Secondary region** (dropdown). Both list every region the platform has enabled. They are pre-filled with **us-east-1 / us-east-2**, and any combination of two different regions can be selected.
3. The preview immediately shows, for the chosen pair:
   - the target account per environment and region;
   - service availability in both regions;
   - replication support for each data store;
   - indicative cost including **cross-region data transfer**;
   - expected RTO/RPO.

**What the platform validates for the selected pair:**

| Check | Source | If it fails |
|---|---|---|
| Primary ≠ secondary | Payload | Rejected |
| Both regions are **enabled in the platform** and **onboarded** in each target account (opt-in regions enabled, account bootstrap present, artifact bucket present) | Environment config + onboarding checks (§5.5.3) | Region not selectable for that environment until onboarding completes |
| Every selected service, engine version and instance class **exists in both regions** | AWS public SSM parameters (`/aws/service/global-infrastructure/regions/{region}/services`) + CloudFormation `describe-type` per region + RDS/ElastiCache orderable options APIs | Field-level error naming the missing service in the region |
| The data store's **cross-region feature supports this pair** (e.g. Aurora Global Database, DynamoDB global tables, ElastiCache Global Datastore, multi-Region KMS) | Catalog multi-region capability (§10.3), checked per region | Rejected with alternatives |
| Optional **data-residency rules** (e.g. a classification limited to certain regions) | Admin-defined region groups; none by default | Rejected only if an admin has defined such a rule |

**Global-service placement, independent of the pair:**
- **CloudFront** certificates (ACM) and **CloudFront-scope WAF** web ACLs must be created in **us-east-1** by AWS rule. The global stack therefore deploys those specific resources to us-east-1 even when the pair is, say, eu-west-1 / eu-central-1.
- Route 53 is global.
- All other global-stack resources (DynamoDB global table definition, Aurora global cluster, multi-Region KMS primary keys, ARC controls) are created in the **selected primary region**.

**Admin screen: Regions** (part of the environment configuration, §5.5):

| Setting | Purpose |
|---|---|
| **Enabled regions** | The list shown in the wizard dropdowns. Enabling a region triggers onboarding: account-bootstrap StackSet instances in that region for all workload accounts, a Shared Services artifact bucket in that region, ECR replication rules, and an SCP region allow-list update (with approval, §4.7). |
| **Default pair** | Pre-fill for the wizard (default us-east-1 / us-east-2), per environment if needed |
| **Region groups (optional)** | Data-residency rules by classification; empty by default, so all pairs are allowed |
| **Per-environment policy** | Which resilience modes each environment allows (defaults in §10.5) |

**Account bindings per region:** an account binding (§5.5.2) is per environment **and region**. By default, the same account serves every region of an environment, so a newly enabled region needs no new binding, only onboarding. A separate DR account can be bound per region if D31 chooses that.

**Changing regions later** (also from the UI, as an infrastructure change request with approvals):

| Change | How |
|---|---|
| Single region → DR/HA | Add the secondary region: deploy the regional stacks there in standby (DR) or active (HA), start replication, run readiness checks |
| Change the **secondary** region | Build the new secondary and wait for replication to catch up; switch the pair; then retire the old secondary |
| Change the **primary** region | A **planned switchover** (§10.6) to the secondary, then the old primary is rebuilt or retired. It is treated as a PROD release with approvals and a DR drill beforehand |

**GitHub variables** (§10.5) carry the selection per environment: `AWS_PRIMARY_REGION`, `AWS_SECONDARY_REGION`, and the regional artifact buckets. The platform updates them when a pair changes. Workflows contain no region names.

### 10.8 Platform control plane is multi-region too

Failover must work when us-east-1 is down, so the platform itself runs active/standby across the same region pair:
- DynamoDB **global tables** for registry, jobs and release records;
- Step Functions, API and release executor deployed in both regions;
- the UI and API behind Route 53 failover;
- `CloudInfraProvisioner` / `PlatformReleaseExecutor` roles are global IAM, assumable from either region.

## 11. Security model

| Threat | Mitigation |
|---|---|
| Unapproved cross-account access | Only via approved sharing agreements (§4.11); both sides generated from the agreement; SCP data perimeter keeps access inside the organization; Access Analyzer alerts on anything not matching an active agreement |
| A project changes another project's resources | Tag conditions on every create/change action (`aws:RequestTag` / `aws:ResourceTag` = principal tag) + name patterns built from the principal's tag + per-project roles + SCP protecting ownership tags |
| A repo forges tags to impersonate another product | Role tags are platform-owned and SCP-protected; request tags must equal principal tags (§4.4) |
| Generated IAM grants too much | Exact-ARN policies; least-privilege linter; shared tag-scoped boundary; exec role can only create roles with the boundary attached |
| A DEV/sandbox pipeline reaches PROD | Separate accounts; OIDC `sub` per environment; environment-scoped variables (a DEV job cannot see PROD's account or role); caller-account guard in the pipeline; environment-lock SCP |
| Unapproved change reaches STAGE or PROD | GitHub required reviewers before the deploy job starts (no AWS access until approved); prevent self-review; gated deploy role can only execute the reviewed change set; reconciler restores removed protection rules |
| Sensitive data in sandbox | Classification gate SCP + sandbox data rules |
| Removing the boundary or tags after creation | SCP denies `DeleteRolePermissionsBoundary` and `org:*` tag changes except by platform roles |
| Confused deputy | `SourceAccount` on the Lambda permission, `aws:SourceAccount` on the CFN trust, `aws:PrincipalOrgID` + ExternalId on the provisioner role |
| Platform GitHub credential leak | App private key in Secrets Manager (KMS); installation tokens per job, never stored |
| S3 ↔ Lambda infinite loop | Validation rule + Lambda's built-in recursive-loop detection |

**Platform authN/authZ:**
- SSO via the org IdP.
- Entitlements come from IdP group → product mapping in the registry.
- Roles: `viewer` (preview), `creator` (provision for entitled products), `approver` (mirrored into GitHub environment reviewers), `platform-admin`.

---

## 12. Scalability and multi-tenancy

### 10.1 Where the load is
Synthesis is cheap. The real limits are **GitHub API quotas per installation**, **CloudFormation / IAM API throttling per account**, and wall-clock time (a five-environment promotion takes tens of minutes plus approval time). So the effort goes into async orchestration, throttling that respects quotas, and keeping policy count flat.

### 10.2 Scaling each layer

| Layer | Strategy |
|---|---|
| UI | Static on CloudFront (includes the release console); registry responses cached per user with a short TTL |
| API | Stateless containers, autoscaled |
| Registry | DynamoDB; read-heavy, cached; admin edits and imports are event-driven |
| Orchestration | Step Functions Standard (durable, holding many jobs open costs no compute); per-environment bootstrap runs as a `Map` state with a concurrency cap |
| Workers | Lambda with reserved concurrency per worker type |
| Status | Webhooks → DynamoDB Streams → SSE/WebSocket; reconciler for missed events |
| **IAM footprint** | **Shared tag-based policies.** Per project, only small tagged roles are added. No per-project policy documents, so the account-level limits on managed policies are never approached. |
| Account onboarding | Service-managed StackSets auto-bootstrap new accounts in the workload OUs |

### 10.3 Throttling that respects quotas
- **Per GitHub installation:** a token bucket (DynamoDB conditional writes) for write calls; a job waits in a Step Functions `Wait` state rather than failing.
- **Per AWS account:** a cap on concurrent bootstrap stack operations (IAM and CloudFormation are the bottlenecks).
- **Per product/tenant:** fair-share limits; an SQS queue in front of `StartExecution` absorbs bursts.
- **Account quotas:** under option A/B, many projects share Lambda concurrency and other account quotas. Track per-account usage and alert. A product that outgrows its share moves to option C by changing its account binding only.

### 10.4 Catalog and registry growth
- **New service** = block + binders + tag-support matrix entry + additions to the shared policies (rolled out via StackSets) + golden tests. No UI-protocol or orchestrator changes.
- **New portfolio/product** = registry entry (admin screen or import). Tag Policy allowed values update automatically. No IAM changes.
- **New account** = joins an OU, is bootstrapped automatically, then an admin binds it to an environment in the application.
- **New environment** (e.g. adding `perf` between TEST and STAGE) = admin creates it in the application, binds accounts, and approves. New projects pick it up at once; existing projects get a sync-pipeline PR.

---

## 13. Error handling, idempotency and rollback

### 11.1 Failure matrix

| Failure | Handling | User sees |
|---|---|---|
| Invalid payload / not entitled to product | 422 / 403 before any side effect | Inline error on the exact field |
| GitHub rate limit | Backoff honoring headers; job waits | "Waiting for GitHub capacity…" |
| Repo name taken (not ours) | Fail fast, nothing to clean up | Name conflict + suggestion |
| Bootstrap fails in one environment account | Stack auto-rolls back; job undoes all environments + repo | Which account/environment failed and why (CFN events) |
| Provisioner role missing in an account (not bootstrapped) | Fail before any GitHub writes (checked during preview) | "Account {env} not onboarded" + admin link |
| Commit ref rejected (non-fast-forward) | Rebuild on the new parent, retry once | Nothing |
| **Deploy fails in an environment** | **Repo kept**; CloudFormation rolls back that environment only; later environments don't run; first-create failures are cleaned up by the next run's pre-flight | `DEPLOY_FAILED(env)` + run link + failed resources |
| AccessDenied from tag conditions | Treated as a policy violation, not retried; message names the tag key that didn't match | "Tag org:project mismatch on …" |
| `UPDATE_ROLLBACK_FAILED` | Never automated; runbook | `FAILED_NEEDS_ATTENTION` |
| Approval not given in time | Job stays in `PROMOTING` (the GitHub environment times out after 30 days); no AWS change | "Awaiting approval for stage/prod" |
| Missed webhook | Reconciler every 5 min queries runs/deployments by `head_sha` | Status resolves late, not never |

### 11.2 Idempotency layers
1. **API:** `Idempotency-Key` → same job; same key with a different payload → 409.
2. **Orchestrator:** execution name = `jobId`.
3. **Each step:** ownership marker on the repo, CloudFormation `ClientRequestToken`, `PUT` semantics, commit trailer check.
4. **Infrastructure:** deterministic template + content-keyed artifacts → empty changesets on re-run.

### 11.3 Undo policy

```mermaid
stateDiagram-v2
  [*] --> RepoCreated
  RepoCreated --> AwsBootstrapped: all envs ok
  AwsBootstrapped --> ActionsConfigured
  ActionsConfigured --> Committed
  Committed --> Promoting
  Promoting --> Succeeded: prod deployed
  Promoting --> DeployFailed: env failed (repo kept)
  RepoCreated --> Undo: failure
  AwsBootstrapped --> Undo: failure
  ActionsConfigured --> Undo: failure
  Undo --> FailedRolledBack: bootstrap stacks deleted (all envs) → repo deleted
  Undo --> FailedNeedsAttention: undo itself fails
```

- **Before the commit:** undo steps run in reverse order across all environment accounts. The repo is deleted only if this job created it.
- **After the commit:** nothing is deleted automatically. The user fixes and pushes, or uses "retry deploy" (`workflow_dispatch`).

---

## 14. Observability

| Signal | What |
|---|---|
| Logs | Structured, with `jobId`, `projectId`, `portfolio`, `product`, `env`, `step`, `attempt`, `x-github-request-id`, `stackId` |
| Traces | OpenTelemetry/X-Ray: API → Step Functions → workers |
| Metrics | Jobs by state; time from click to DEV and to PROD; deploy failure rate by environment and catalog combination; GitHub rate-limit headroom per installation; AccessDenied from tag conditions (could indicate misuse) |
| Cost | CUR / Cost Explorer by `org:portfolio` → `org:product` → `org:project` → `org:environment` |
| Compliance | AWS Config tag compliance per account → audit account; dashboard of non-compliant resources per product |
| Alerts | Spike in `FAILED_NEEDS_ATTENTION`; any attempt to change `org:*` tags (CloudTrail → EventBridge); bootstrap drift; rate-limit headroom below 10% |

---

## 15. Where an LLM fits (and where it must not)

| Use | Allowed? | Guardrails |
|---|---|---|
| Natural language → **draft payload** (services + connections) | Yes | Same validation; ownership still chosen from dropdowns, never inferred |
| Handler business logic in starter code | Optional | Limited to `src/`; linted; shown in preview |
| CloudFormation resources, IAM policies, tags | **No** | Deterministic blocks only |
| Explaining a failed deploy from stack events | Yes | Read-only summary next to the raw events |

---

## 16. Proposed repository layout

For your review. Nothing is created until you approve.

```
CloudInfraAutomation/
├── docs/
│   ├── ARCHITECTURE.md
│   ├── TAGGING-STANDARD.md            ← tag keys, values, ownership rules (from §4)
│   └── runbooks/
├── backend/
│   ├── api/                           ← FastAPI, auth, entitlements, idempotency
│   ├── registry/                      ← org registry model, CSV/REST import, tag-policy sync
│   ├── synth/                         ← models, blocks, binders, linters, starters, env profiles
│   ├── provisioning/                  ← github/, aws/ (multi-account), saga/
│   ├── webhooks/                      ← workflow_run / deployment_status + reconciler
│   └── tests/                         ← unit, golden, ABAC policy tests (IAM policy simulator)
├── org/
│   ├── scp/                           ← tag protection, env lock, classification, regions
│   ├── tag-policies/                  ← generated from registry
│   └── stacksets/account-bootstrap.yaml ← OIDC, shared ABAC policies, provisioner role
├── bootstrap/
│   └── project-bootstrap.yaml         ← tagged deploy role + exec role (per env)
├── platform-workflows/               ← reusable build (per language) + deploy (per compute) workflows; published as its own repo
├── app-templates/                   ← language templates for application repos (python, java, go, rust, nodejs)
├── generated-repo-skeleton/
│   └── .github/workflows/{deploy.yml, deploy-env.yml}
├── infra/                             ← platform control plane IaC
└── frontend/                          ← React UI with cascading ownership dropdowns
```

**Proposed stack:**
- Python 3.12+ (FastAPI, pydantic v2, PyGithub 2.x, boto3, PyNaCl).
- Step Functions + Lambda + DynamoDB.
- React + TypeScript.
- ABAC policies are tested with the **IAM policy simulator** and with real allow/deny tests in a sandbox account in CI.

---

## 17. Decisions needed from you

| # | Decision | Recommendation |
|---|---|---|
| D1 | Backend language | **Python** |
| D2 | GitHub identity | **GitHub App** (organizations only in v1) |
| D3 | Tag key prefix | Your company prefix, e.g. `acme:`. Placeholder in this document: `org:` |
| D4 | Main isolation level | **Project** (default) with opt-in read sharing within a product |
| D5 | Hierarchy | **Decided:** three levels, Portfolio → Product/Platform → Project. No team level or team tag. |
| D6 | Account granularity | **B: per portfolio per environment**, with C available per product |
| D7 | Registry source of truth | **Decided:** the platform registry is the master (CSV/REST import available) |
| D8 | Sandbox model | Shared sandbox account per portfolio with 14-day TTL, or per-product sandbox accounts? |
| D9 | Approvers | **Decided:** STAGE and PROD require GitHub reviewer approval before deployment. Open: which groups review each (default QA for STAGE; product owner + change management for PROD), and is a built-in change record required for PROD? |
| D10 | Regions | **Decided:** multi-region from the start: single region, DR or HA per project, any region pair chosen in the UI (§10) |
| D11 | Onboarded today? | Do Control Tower / OUs per environment already exist, or does `org/` need to create the OU structure too? |
| D12 | LLM | Exclude from v1, or NL → draft payload only? |
| D13 | Who can configure environments and accounts | **Platform admins only, with a second-person approval** for changes to production-tier environments. Normal users see environments read-only. (If you meant every user should configure them, note that whoever binds an account decides where code deploys.) |
| D14 | Binding scope | Bind accounts per **portfolio** by default, with a per-product override (matches D6), or per product only? |
| D15 | GitHub plan | Not a blocker: Mode A works on any plan. If you have GitHub Enterprise, should Mode B (GitHub environment reviewers in addition) be turned on? |
| D16 | Quality-gate thresholds | Coverage minimum (e.g. 80%), vulnerability policy (block critical/high), STAGE bake time before PROD (e.g. 24 h), change windows / freeze calendar, built-in change record required for PROD? |
| D17 | PROD approvals | One GitHub approval (simplest), or two approvals from different groups collected in the release console (§8.5.4)? |
| D18 | Notifications | **Decided:** in-app inbox + email via Amazon SES + optional signed webhooks |
| D19 | Application repo granularity | One repo per compute slot (simplest permissions), or allow monorepos serving several slots? |
| D20 | EKS deploy model | **Argo CD GitOps** (recommended) or pipeline-driven `helm upgrade`? Does a shared EKS cluster per portfolio per environment already exist, and who runs it? |
| D21 | Languages in v1 | Python, Java, Go, Rust, Node.js all at once, or start with two (e.g. Python + Java)? |
| D22 | Developer portal | Platform UI only (default), or also open-source Backstage (`catalog-info.yaml` generated either way)? |
| D23 | Networking for ECS/EKS | Shared VPC from the landing zone (subnets/SGs published to SSM by the network team)? |
| D24 | Deprecation window | Minimum time a deprecated contract value stays after it becomes unused in an environment (e.g. 0 days in DEV/TEST, 14 days in STAGE/PROD)? |
| D25 | Infra approvals | Should product reviewers also approve infra deploys to STAGE/PROD, or the platform team only? |
| D26 | Open-source license policy | Allow Apache-2.0, MIT, BSD, MPL-2.0 and LGPL (as libraries); exclude AGPL and source-available licenses unless approved? |
| D27 | Tier 1 services at launch | Confirm the proposed curated list (§6.8.2), or start smaller (e.g. compute + integration + Aurora/RDS PostgreSQL + DynamoDB) and grow? |
| D28 | Commercial DB engines | Exclude RDS for Oracle / SQL Server (default, per open-source policy), or allow them? |
| D29 | Network ownership | Does the landing zone provide shared VPCs with database/private subnets per environment account, or must the platform create project VPCs? |
| D30 | Region pairs | **Decided:** any two different regions, chosen in the UI per project; default pre-fill us-east-1 / us-east-2; admins manage the enabled-region list |
| D31 | DR account model | Same account for both regions of an environment (default), or a separate DR account per environment? |
| D32 | DR defaults | Pilot light (default) or warm standby for DR projects? QA/STAGE mirrors PROD's mode (default)? DR drill frequency (default monthly) and G5 recency (default 30 days)? |
| D33 | Cognito and other non-replicating services | Exclude from DR/HA projects, or allow with a documented recovery pattern? |
| D34 | Cross-account outside the AWS Organization | Keep off by default with a security exception per partner account (recommended), or allow certain partner accounts by default? |
| D35 | Sharing agreement policy | Default expiry (12 months?) and recertification (quarterly?); does PROD sharing always need a security reviewer, or only for `confidential`+ data? |
| D36 | Cross-environment sharing | Allow same-tier only (recommended), or permit specific exceptions such as PROD → non-PROD read of anonymized data? |
| D37 | Share-tag limits | Maximum `org:share-scope` per data classification (default: public/internal any, confidential ≤ product, restricted none) and whether `organization` scope is allowed at all? |
| D38 | Sharing approval routing | Accept the default routing matrix (§4.11.6)? Allow providers to choose `org:share-approval=auto`, or require approval for every access request? Recertification frequency (default quarterly)? |

---

## 18. Implementation phases (after approval)

| Phase | Deliverable | Exit criteria |
|---|---|---|
| **P0 — Standards** | `TAGGING-STANDARD.md`, registry schema, tag-support matrix for S3/Lambda/DynamoDB/Logs/IAM | Signed off by security / cloud governance |
| **P1 — Org guardrails** | SCPs, Tag Policies, account-bootstrap StackSet with shared ABAC policies, same-tag resource policy patterns (§4.10) | In a sandbox: project A's runtime roles cannot reach project B's S3/SQS/DynamoDB/secrets/functions even with exact ARNs (§4.10.4); project A's roles are **denied** on project B's resources and on forged tags; allowed on their own (automated allow/deny test suite) |
| **P2 — Engine** | Payload schema, synthesis (S3, Lambda, DynamoDB, binders), linters, per-environment parameter files, golden tests | Lambda + S3 template passes lint/guard for all 5 environments; regeneration gives identical output |
| **P3 — Pipeline** | `project-bootstrap.yaml`, `deploy.yml` + `deploy-env.yml`, G1–G3 gates, plan → approve → execute for STAGE/PROD | Manual repo promotes sandbox → prod with reviewer approvals; STAGE/PROD cannot deploy without approval; second push = empty changesets; failure in TEST stops promotion and the next push recovers |
| **P4 — Provisioning** | GitHub App client, multi-account bootstrapper, saga, CLI | One command creates a repo that bootstraps 5 accounts and deploys DEV; failures injected at each step undo cleanly |
| **P5 — API + UI** | Registry API, **environment & account admin screens**, **release console (pipeline view, approval inbox, approval detail)**, cascading dropdowns, preview, status per environment | Click-to-DEV in the browser; entitlement filtering verified; an admin can add/reorder an environment and bind an account, and onboarding checks block an invalid account |
| **P5b — Quality gate service** | Release record, deployment protection rule app, change set risk analysis, Access Analyzer checks, G4/G5 | A high-risk change set is blocked; PROD is refused if the artifact differs from STAGE or bake time is not met |
| **P5c — Application golden paths** | Compute slot catalog types, contract publishing (SSM + API), `platform-workflows` (build per language, deploy per compute type), app deploy roles, "Create application repo" flow, contract viewer | A Python Lambda app and a Java ECS app deploy from their own repos to DEV and promote to PROD with approvals; an app repo cannot create IAM or touch another project; an app deploy stops cleanly when the contract lacks a required value |
| **P5d — Full service catalog** | Catalog sync job (CFN schemas + Service Authorization Reference), Tier 2 generator, generic connection kinds, database blocks (Aurora/RDS/DynamoDB first), layered stacks, pairwise CI, nightly deploy tests, reference patterns | Any enabled resource type can be composed and passes all gates; pairwise suite green; every database engine deploy-tested weekly |
| **P5e — Multi-region DR/HA** | Resilience modes in wizard and payload, conditions in generated templates, global stack, per-service replication wiring, two-region pipeline, failover/failback operations, ARC readiness, DR drills, multi-region control plane | A DR project deploys to us-east-1 (active) and us-east-2 (standby); a STAGE drill fails over and back within target RTO/RPO; an HA project serves traffic from both regions |
| **P5f — Cross-account sharing** | Sharing approval workflow (share offers, access requests, agreements, renewals, revocations), sharing agreements, shareable-resource catalog, generators for patterns A–F, consumer contract `external` bindings, readiness checks, expiry/revocation, Access Analyzer integration | A consumer in account A reads an approved S3 prefix and consumes an approved SQS queue in account B; any other project or environment in A is denied; revoking the agreement removes access on both sides |
| **P6 — Production control plane** | Step Functions, webhooks, reconciler, quotas, observability, Config compliance | 100 concurrent jobs on one installation complete without failing on rate limits; tag compliance dashboard live |

**Next step:** review this document, answer §17, and approve a phase to start. No code will be written until then.

---

## 19. Appendix A: Approval and workflow diagrams

This appendix collects every approval flow in the design in one place. Each diagram links back to the section that defines the rules. The same diagrams are available as PNG and SVG files in `docs/diagrams/approvals/`.

**Approval summary:**

| What needs approval | Approvers | Enforced by | Defined in |
|---|---|---|---|
| STAGE / PROD release (infrastructure or application) | Product reviewers (QA for STAGE; product owner + change management for PROD) | Gate service first; release executor applies only the reviewed change | §8.3, §8.4, §8.5 |
| High-risk change override | Platform admin (not the requester) | Gate service blocks until the override is recorded | §8.4.2 |
| Sharing: offer, access request, agreement, renewal, revocation | Provider owner; + security / platform admin by risk; auto-approval only if the provider allows it | Sharing workflow, generated PRs, normal gates | §4.11.6 |
| Infrastructure change request (from a product team) | Platform team (code review), then release approvals per environment | Infra repo PR + gates | §9.9.6 |
| Environment, account binding or region change | Platform admin; + second platform admin for prod tier or the SCP region list | Configuration service (versioned, audited) | §5.5.4, §10.9 |
| DR failover / failback | Incident lead + second approver (break-glass) | Release executor runbook | §10.6 |

### A.1 Approval landscape

```mermaid
flowchart LR
  H1["REQUEST"]:::hdr --> H2["APPROVERS"]:::hdr --> H3["ENFORCEMENT"]:::hdr
  R1["STAGE / PROD release<br/>infrastructure or application"] --> A1["Product reviewers<br/>QA for STAGE · owner + change mgmt for PROD"] --> E1["Gate service passes first<br/>release executor applies the exact reviewed change"]
  R2["High-risk change override"] --> A2["Platform admin<br/>not the requester"] --> E2["Gate blocks until override recorded<br/>for this change set only"]
  R3["Sharing request<br/>offer · access · agreement · renewal · revocation"] --> A3["Provider owner<br/>+ security / platform admin by risk"] --> E3["Generated infra PRs on both sides<br/>normal gates · recertified quarterly"]
  R4["Infrastructure change request<br/>from a product team"] --> A4["Platform team code review<br/>then release approvals per environment"] --> E4["Infra repo PR · gates ·<br/>declared contract updated at once"]
  R5["Environment / account / region change"] --> A5["Platform admin<br/>+ second admin for prod tier or SCP"] --> E5["Versioned config · onboarding checks ·<br/>sync PRs to existing projects"]
  R6["DR failover / failback"] --> A6["Incident lead + second approver<br/>break-glass"] --> E6["Release executor runbook ·<br/>ARC traffic switch · RTO/RPO recorded"]
  classDef hdr fill:#1F3864,color:#ffffff,stroke:#1F3864,font-weight:bold
```

### A.2 STAGE / PROD release: default mode (any GitHub plan)

```mermaid
sequenceDiagram
  autonumber
  participant GA as GitHub Actions
  participant AWS as STAGE or PROD account
  participant GS as Gate service
  participant RC as Release console
  actor R as Reviewer
  participant EX as Release executor
  GA->>AWS: plan job: OIDC plan role creates change set cs-sha-run
  GA->>GS: evidence: change set summary, tests, scans, signed provenance
  GS->>GS: evaluate G4 or G5 policies (OPA)
  alt gate failed
    GS-->>RC: GateFailed with reasons, reviewers not asked
  else high-risk change
    GS-->>RC: OverrideRequested, see A.4
  else gate passed
    GS-->>RC: AwaitingApproval, inbox item for reviewers
    R->>RC: review evidence, approve with comment
    RC->>RC: check reviewer group, not the requester, still the latest candidate
    RC->>EX: release the approved change set
    EX->>AWS: assume executor role with session tag org:project, ExecuteChangeSet
    AWS-->>EX: UPDATE_COMPLETE or automatic rollback
    EX-->>GA: result to the waiting release job, GitHub deployment and commit status
  end
```

### A.3 Release decision flow

```mermaid
flowchart TD
  S["Change reaches the STAGE / PROD gate"] --> P{"Change set created<br/>by the plan job?"}
  P -->|no| F1["Stop: plan failed"]
  P -->|yes| G{"Automated gate<br/>G4 / G5 passed?"}
  G -->|no| F2["Stop: gate failed<br/>reasons shown"]
  G -->|yes| HR{"High-risk change?<br/>replace or delete data · IAM widening"}
  HR -->|yes| O{"Override approved<br/>by a platform admin?"}
  O -->|no| F3["Stop: rejected"]
  O -->|yes| Q
  HR -->|no| Q{"Reviewer decision<br/>not the requester"}
  Q -->|reject| F4["Stop: rejected"]
  Q -->|30 days, no decision| F5["Expired"]
  Q -->|newer commit arrived| F6["Superseded"]
  Q -->|approve| X["Release executor applies<br/>the exact reviewed change set"]
  X --> D{"Healthy during<br/>monitoring window?"}
  D -->|no| RB["Automatic rollback<br/>CloudFormation alarms"]
  D -->|yes| OK["Deployed and recorded"]
  classDef stop fill:#FBE5E1,stroke:#C0504D,color:#7F1D1D
  classDef ok fill:#E2F0D9,stroke:#548235,color:#1E4620
  class F1,F2,F3,F4,F5,F6,RB stop
  class OK ok
```

### A.4 High-risk change override

```mermaid
sequenceDiagram
  autonumber
  actor REQ as Requester
  participant RC as Release console
  actor PA as Platform admin
  participant GS as Gate service
  GS-->>RC: high-risk change detected, for example a database replacement
  REQ->>RC: request override with reason, data protection and rollback plan
  RC->>RC: validate: approver is not the requester, change set still current
  RC->>PA: approval request with change set diff and risk details
  alt approved
    PA->>RC: approve, scope limited to this change set
    RC->>GS: record override and re-evaluate
    GS-->>RC: AwaitingApproval, the normal reviewer step is still required
  else rejected
    PA->>RC: reject with comment
    RC-->>REQ: promotion stopped, environment unchanged
  end
```

### A.5 Sharing approval routing

```mermaid
flowchart TD
  S["Sharing request"] --> T{"Request type"}
  T -->|share offer| O1{"Scope wider than product, or<br/>access beyond read, or data confidential?"}
  O1 -->|no| AO["Provider product owner"]
  O1 -->|yes| AOS["Provider owner + security"]
  T -->|access request| AR{"Within an approved offer and<br/>org:share-approval = auto?"}
  AR -->|yes| AUTO["Auto-approved<br/>provider notified"]
  AR -->|no| PC{"PROD and data<br/>confidential?"}
  PC -->|no| AP["Provider product owner"]
  PC -->|yes| APS["Provider owner + security"]
  T -->|agreement| AG{"Outside the organization<br/>or across environments?"}
  AG -->|yes| AGX["Provider owner + security<br/>+ platform admin"]
  AG -->|no| PC
  T -->|renewal| RN["Same approvers as the original request"]
  T -->|revocation| RV{"Emergency?"}
  RV -->|yes| RVS["Security reviewer alone<br/>takes effect at once"]
  RV -->|no| RVO["Provider or consumer owner"]
  classDef stop fill:#FBE5E1,stroke:#C0504D,color:#7F1D1D
  classDef ok fill:#E2F0D9,stroke:#548235,color:#1E4620
  class AUTO ok
  class RVS stop
```

### A.6 Access request to a shared resource

```mermaid
sequenceDiagram
  autonumber
  actor C as Consumer owner
  participant UI as Platform UI
  participant WF as Sharing workflow
  actor P as Provider owner
  participant GH as Infra repos
  participant AWS as AWS accounts
  C->>UI: draw a connection to a shared resource from the catalog
  UI->>WF: access request, tag rule pre-checked: environment, organization, product or portfolio
  alt resource allows auto-approval
    WF-->>P: notification only
  else approval required
    WF->>P: inbox item with evidence and generated policy diff
    P->>WF: approve
  end
  WF->>GH: PR on consumer infra repo: role statements and contract binding
  WF->>GH: PR on provider infra repo when a per-consumer grant is needed, for example KMS
  GH->>AWS: deploy through normal gates, STAGE and PROD need release approval
  AWS-->>WF: readiness check passed, a harmless test read
  WF-->>C: access active, contract exposes the resource
```

### A.7 Infrastructure change request from a product team

```mermaid
sequenceDiagram
  autonumber
  actor D as Product developer
  participant UI as Platform UI
  participant PL as Synthesis and contract
  participant GH as Infra repo
  actor PT as Platform team
  participant ENV as Environments
  D->>UI: Change infrastructure, for example add a table and grant access
  UI->>PL: synthesize and validate
  PL-->>D: declared contract updated at once, development continues
  PL->>GH: PR with regenerated template and risk classification
  GH->>PT: code review by CODEOWNERS
  PT->>GH: approve and merge
  GH->>ENV: Sandbox, DEV and TEST deploy automatically
  GH->>ENV: STAGE and PROD via plan, reviewer approval and release executor
  ENV-->>D: deployed contract updated per environment
```

### A.8 Environment, account or region configuration change

```mermaid
flowchart TD
  A["Platform admin edits an environment,<br/>account binding or enabled region"] --> V{"Validation and onboarding checks pass?<br/>account in org · OU tier · bootstrap · unique account"}
  V -->|no| X["Rejected with reasons"]
  V -->|yes| T{"Affects a prod-tier environment<br/>or the SCP region list?"}
  T -->|no| AP["Applied: versioned and audited"]
  T -->|yes| S{"Second platform admin approves?<br/>not the editor"}
  S -->|no| X
  S -->|yes| AP
  AP --> PR["Propagation: new projects use it at once,<br/>existing projects get sync PRs, never silent"]
  classDef stop fill:#FBE5E1,stroke:#C0504D,color:#7F1D1D
  classDef ok fill:#E2F0D9,stroke:#548235,color:#1E4620
  class X stop
  class AP ok
```

### A.9 DR failover (break-glass)

```mermaid
sequenceDiagram
  autonumber
  actor IL as Incident lead
  actor A2 as Second approver
  participant RC as Release console
  participant EX as Release executor
  participant SEC as Secondary region
  participant ARC as Route 53 ARC
  IL->>RC: fail over project to the secondary region, with reason
  RC->>A2: break-glass approval request, paged
  A2->>RC: approve
  RC->>EX: start the failover runbook
  EX->>SEC: promote databases, Aurora global failover or replica promotion
  EX->>SEC: set ActivationState active, scale up, enable event sources
  EX->>ARC: switch routing control to the secondary region
  EX->>SEC: health checks and smoke tests
  EX-->>RC: failover complete, RTO and RPO recorded, GitHub variables updated
  Note over RC,EX: Failback later is planned and approved like a PROD release
```

### A.10 Sharing recertification and expiry

```mermaid
sequenceDiagram
  autonumber
  participant WF as Sharing workflow
  actor P as Provider owner
  participant GH as Infra repos
  participant AWS as AWS accounts
  WF->>P: recertification due, or expiry in 30 and 7 days
  alt re-approved
    P->>WF: confirm the access is still needed
    WF->>WF: extend expiry and record the decision
  else not re-approved in time
    WF->>GH: PRs removing consumer statements and provider grants
    GH->>AWS: deploy through normal gates
    WF-->>P: access revoked, consumers notified
  end
```

### A.11 Application release to PROD (default mode)

```mermaid
sequenceDiagram
  autonumber
  participant AP as App pipeline
  participant AWS as PROD account
  participant GS as Gate service
  actor R as Reviewer
  participant EX as Release executor
  AP->>AWS: prepare only: upload artifact, publish Lambda version or register task definition
  AP->>GS: evidence: deploy diff, tests, scans, signed provenance
  GS->>GS: G5: same artifact as STAGE, bake time, STAGE health, DR drill
  R->>GS: approve in the release console
  GS->>EX: release
  EX->>AWS: move live alias, update ECS service or sync the GitOps commit
  AWS-->>EX: healthy, or automatic rollback
  EX-->>AP: status
```


---

## 20. Landing zone workflow: AWS Organizations OU structure with Control Tower controls

**Status: rev 3 approved and implemented; §20.11 (OU tree editor) approved with changes (E1, E4); §20.12 (industry templates) is a design for review.** Mock: the *Landing zone* page in `mock-ui/index.html`.

**Inputs:**
- AWS Prescriptive Guidance *OU structure in regulated AWS landing zones* (the attached document).
- AWS Prescriptive Guidance *Designing a Control Tower landing zone: account structure*.
- The sample OU and network diagram you supplied ([docs/diagrams/landing-zone-sample-input.png](diagrams/landing-zone-sample-input.png)): a master payer account with AWS Organizations, a separate Network account, and per-account VPCs with public and private subnets, each attached to a central hub.

**Scope:**
- The workflow sets up a **new organization or a new AWS subscription** (greenfield). The customer answers a guided questionnaire, the platform proposes an OU structure, the customer adjusts it, and the platform generates and deploys the CloudFormation.
- It is a **separate admin-only workflow**, independent of the project wizard.
- Project templates still refuse Organizations, Control Tower and SSO types (§6, Tier 2).

### 20.1 Fixed rules (cannot be removed in the designer)

| # | Rule | Enforced by |
|---|---|---|
| R1 | **Every environment is always its own OU** and holds only its own environment's accounts. The customer picks 4, 5 (**recommended**: Sandbox, DEV, TEST, STAGE, PROD) or 6 environments in the questionnaire. | `OuTreeValidator` rejects any design that merges two environments into one OU or nests one environment OU inside another. |
| R2 | **No access between environment OUs**, except for networking flows that are declared, isolated and inspected (§20.4) | Resource control policies (RCPs) and SCPs per environment OU (§20.5), plus transit gateway route-table isolation (§20.4) |
| R3 | **Exactly one Security (Cyber) OU** with the Log Archive and Audit accounts, which hold GuardDuty, Security Hub and Config aggregation | Created by the Control Tower landing zone. The validator requires exactly one. |
| R4 | Policies attach to **OUs only**, never to single accounts ("OUs are policy targets, not folders", from the attached guide) | Validator |
| R5 | Every change goes to the **Policy Staging OU** first, then is promoted after approval | Workflow (§20.7) |

### 20.2 The guided questionnaire

The UI asks these questions in order. Each answer is turned into OUs, accounts, controls and network elements by an **answer handler**, one class per question (Open/Closed: a new question adds a class). The result is a proposed design, which the customer then edits in the OU tree editor.

| Step | Question | Choices (default **bold**) | Effect on the design |
|---|---|---|---|
| 1. Organization | Organization name, management (payer) account email, home region, governed regions, DR region pair | Regions from the region registry (§10.9); **us-east-1 / us-east-2** | Landing zone manifest; region-deny SCP; IPAM regions |
| 2. Environments | How many environments? | 4 (Sandbox, DEV, STAGE, PROD; testing runs in DEV) / **5 (Sandbox, DEV, TEST, STAGE, PROD), recommended** / 6 (adds UAT, renameable). Names are editable. | One isolated OU per environment (R1, R2). STAGE and PROD are production tier with reviewer approval. |
| 3. Account model | How many accounts per environment? | **One per portfolio per environment** / one per environment / one per product per environment (D6) | Accounts vended into each environment OU |
| 4. Grouping (asked on the Environments step) | Put the environment OUs under two parent OUs (Prod and NonProd)? | **No: keep every environment OU separate, directly under the root (recommended)** / two parents, Prod and NonProd | **Separate (recommended):** every environment OU gets its own copy of the baseline policies, so one policy change can't loosen production and non-production at once. That is an extra security layer. The baseline is packed into one combined SCP to stay within the 5-SCPs-per-OU quota. **Parents:** shared policies attach once and are inherited; fewer attachments, larger blast radius per change. |
| 5. Compliance | Any regulated workloads? | **None** / PCI DSS / HIPAA / GxP / other | Each selected scope adds its own OU (e.g. a **PCI OU** with PCI-STAGE and PCI-PROD child OUs, like the sample's PCI VPC) with stricter controls and Security Hub standards |
| 6. Security (Cyber) | Security tooling account in addition to Log Archive and Audit? Delegated administrators? Log retention? | **Yes: Security Tooling account; GuardDuty, Security Hub, Inspector and Macie delegated to Audit; logs kept 365 days (STAGE/PROD 7 years)** | Accounts in the Security OU; delegated-admin settings; Control Tower logging config |
| 7. Infrastructure | Which shared accounts? | **Network, Shared Services, Identity, Backup, Monitoring** · optional: CI/CD Automations | Infrastructure OU and its accounts |
| 8. Network | Hub and spoke through a central Network account? Central egress? Inspection? On-premises link? Top-level CIDR? | **Yes / central egress / AWS Network Firewall inspection / none / 10.0.0.0/8** · VPN or Direct Connect optional | Network design (§20.4) |
| 9. Cross-environment flows | Which flows between environments are allowed? | **None**, except every environment to Shared Services (DNS, artifacts, directory) and to the egress/inspection VPC | Inspected exception rules (§20.4) |
| 10. Sandbox | Sandbox account per developer or per team? Budget? Expiry? | **Per team; $500 a month; 30-day expiry with cleanup** | Sandbox OU accounts, budget and TTL policies; internet egress only, no route to other environments |
| 11. Other OUs | Policy Staging (always), Exceptions, Suspended, Individual Business Users? | **Policy Staging, Exceptions, Suspended** | Optional OUs. Transitional is off by default because a new organization has no accounts to move in. |
| 12. Controls profile | Starting set of Control Tower controls | **Strongly recommended** / Baseline / Regulated (adds the compliance scope's controls) | Controls per OU (§20.6) |

The answers are stored as a versioned `LandingZoneQuestionnaire`. Re-running it with different answers produces a new design version and a diff (§20.7), never an in-place overwrite.

### 20.3 Default proposed structure (all default answers: 5 environments, kept separate)

```mermaid
flowchart TD
  ROOT["Root: Management / payer account<br/>AWS Organizations · Control Tower · Account Factory · IAM Identity Center"]
  ROOT --> SEC["Security OU (Cyber) — fixed<br/>Log Archive · Audit · Security Tooling"]
  ROOT --> INF["Infrastructure OU<br/>Network (Transit Gateway, IPAM, egress, inspection) · Shared Services · Identity · Backup · Monitoring"]
  ROOT --> SBX["Sandbox OU — fixed<br/>Sandbox accounts 1..n"]
  ROOT --> DEV["DEV OU"]
  ROOT --> TST["TEST OU"]
  ROOT --> STG["STAGE OU"]
  ROOT --> PRD["PROD OU"]
  ROOT --> PST["Policy Staging OU"]
  ROOT --> EXC["Exceptions OU"]
  ROOT --> SUS["Suspended OU"]
```

**Compared with the sample diagram.** The sample keeps the Non-Production, Production and PCI VPCs in **one** Enterprise account. Under R1/R2 these tiers move to **separate accounts in separate OUs** (DEV, TEST, STAGE, PROD, and a PCI OU if selected). The VPC pattern (public and private subnets, attached to the hub) and the separate Network account are kept as drawn.

### 20.4 Isolated networking between environments

```mermaid
flowchart LR
  subgraph NET["Network account (Infrastructure OU)"]
    TGW["Transit Gateway<br/>(shared to the environment OUs with RAM)"]
    IPAM["VPC IPAM<br/>one pool per environment per region"]
    EGR["Egress + inspection VPC<br/>NAT · AWS Network Firewall"]
  end
  subgraph SS["Shared Services account"]
    SSV["Shared VPC<br/>DNS resolver · artifacts · directory"]
  end
  SBXV["Sandbox VPCs"] --> TGW
  DEVV["DEV VPC"] --> TGW
  TSTV["TEST VPC"] --> TGW
  STGV["STAGE VPC"] --> TGW
  PRDV["PROD VPC"] --> TGW
  TGW --> EGR
  TGW --> SSV
```

| Element | Design |
|---|---|
| Addressing | VPC IPAM in the Network account. The top-level CIDR is split into **non-overlapping pools per environment per region** (e.g. PROD us-east-1 10.40.0.0/14). The pools are shared with each environment OU through RAM, so VPCs can only take addresses from their own environment's pool. |
| VPCs | One VPC per workload account per region, with private subnets in at least 2 AZs (public subnets only when the egress model is local) and a transit gateway attachment. **Every VPC created is registered automatically in the platform's network registry (§10 networks)**, so the wizard's VPC and subnet dropdowns fill without manual entry. |
| Route isolation | **One transit gateway route table per environment**, plus `shared` and `egress` tables. An environment's attachments associate with its own table, which only has routes to its own environment, Shared Services and egress. **No DEV ↔ PROD route exists**, so traffic between environments can't be routed at all. |
| Sandbox | Sandbox route table: egress only. No route to any other environment or to Shared Services, except DNS. |
| Allowed exceptions (question 9) | Each exception is a declared rule: source environment, destination environment, CIDR, port and protocol, owner, expiry. It is applied as a route **through the inspection VPC** plus a Network Firewall stateful rule that allows only that port. It is never a direct route. Exceptions go through the approval workflow and show in the UI with their expiry. |
| Same-environment traffic | Within an environment, services talk across the environment's private range without opening ports one by one (§10 networks, org security group) |
| Hybrid (optional) | VPN or Direct Connect gateway on the transit gateway, with its own route table and propagation to the environments chosen in question 8 |

### 20.5 Access isolation between environment OUs (R2)

| Layer | Policy | Effect |
|---|---|---|
| **Resource control policy** (Organizations RCP) on each environment OU | Deny access to S3, STS, KMS, SQS and Secrets Manager resources unless `aws:PrincipalOrgPaths` is under the **same environment OU**, or the principal belongs to the Security, Network or platform accounts' break-glass and automation roles | A PROD bucket can't be read by a DEV role, even if someone writes a permissive bucket policy |
| **SCP** on each environment OU | Deny `sts:AssumeRole` into roles outside its own OU path (`aws:ResourceOrgPaths`); deny RAM shares to principals outside its own OU | Identities in DEV can't move into TEST, STAGE or PROD |
| Tag rules (§4.7, §4.10) | Unchanged: same-tag isolation inside an account | Project isolation inside an environment |
| Cross-account sharing (§4.x sharing workflow) | Allowed **only between accounts in the same environment OU**. Shares across environments are rejected when the request is made. | Keeps the existing sharing feature consistent with R2 |

### 20.6 Controls per OU (editable catalog)

Admins pick controls from a catalog showing each control's behaviour (preventive, detective or proactive) and severity. Mandatory Control Tower controls are always on. Control identifiers are checked against Control Tower `ListControls` when the plan is built.

| OU | Default controls (Strongly recommended profile) | Organizations policies |
|---|---|---|
| Root | AI services opt-out | Tag policy from the registry; region deny for governed regions |
| Security | Mandatory Control Tower controls; protect logging and audit resources | Deny disabling GuardDuty, Security Hub, Config and CloudTrail |
| Infrastructure | Disallow root user actions and access keys; restricted SSH and common ports | Only network admins can change transit gateway, IPAM and firewall resources |
| Every environment OU (baseline, attached to each OU directly when kept separate) | Disallow root user actions and access keys; MFA for root and console users; S3 public read/write prohibited; RDS public access and snapshots prohibited; encrypted EBS and RDS storage | §4.7 SCPs: tag immutability, same-tag isolation, data perimeter |
| Each environment OU | Inherited | §20.5 RCP and SCP |
| STAGE and PROD | Plus: detect CloudTrail and Config tampering; deny deleting stacks and data stores except through the release executor | Backup policy (daily, cross-region copy to the DR pair) |
| Sandbox | Root restrictions; S3 public prohibited | Expensive-service limits; expiry tag required; no transit gateway attachment except egress |
| Compliance OUs (e.g. PCI) | Regulated profile; the scope's Security Hub standard (e.g. PCI DSS) | Stricter data perimeter; deny non-compliant regions |
| Exceptions | Inherited **minus** an exempted control. Each exemption has an owner, a reason and an expiry. | n/a |
| Suspended | n/a | Deny all except break-glass |

### 20.7 Workflow and stacks

```mermaid
stateDiagram-v2
  [*] --> Questionnaire
  Questionnaire --> Proposed: answer handlers build a design
  Proposed --> Draft: admin edits OU tree / accounts / controls / network
  Draft --> Planned: Plan (validate fixed rules, render stacks, diff)
  Planned --> Approval: Submit
  Approval --> Applying: second admin approves (no self-approval)
  Approval --> Rejected
  Applying --> Verifying: stacks applied in order
  Verifying --> Completed: all checks pass
  Applying --> Failed
  Verifying --> Failed
  Failed --> Draft
```

For a new organization there are no accounts to move, so the Policy Staging step (R5) applies to **later changes**. The first build applies directly after approval and verification.

The design is applied as **ordered CloudFormation stacks**, kept separate because building the landing zone takes about an hour and each stack keeps its blast radius small:

| Order | Stack (deployed from the management account) | Main resource types |
|---|---|---|
| 1 | `lz-foundation` | `AWS::Organizations::Organization`, the four Control Tower prerequisite `AWS::IAM::Role`s, `AWS::Organizations::Account` (Log Archive, Audit), `AWS::ControlTower::LandingZone` |
| 2 | `lz-structure` | `AWS::Organizations::OrganizationalUnit` (nested), `AWS::Organizations::Policy` (SCP, RCP, TAG, BACKUP, AI opt-out), `AWS::ControlTower::EnabledBaseline` per OU, `AWS::ControlTower::EnabledControl` (in batches with `DependsOn`) |
| 3 | `lz-accounts` | `AWS::ServiceCatalog::CloudFormationProvisionedProduct` of the Control Tower **Account Factory** product, one per account, created enrolled in its OU (chained, because Account Factory provisions accounts one at a time) |
| 4 | `lz-network` | `AWS::CloudFormation::StackSet`s: the Network account (transit gateway, route tables, IPAM and pools, egress/inspection VPC, Network Firewall, `AWS::RAM::ResourceShare` to the environment OU ARNs), and workload accounts per environment OU (VPC from IPAM, subnets, transit gateway attachment, route table association) |
| 5 | `lz-bootstrap` | Service-managed `AWS::CloudFormation::StackSet` for the §5.4 account bootstrap, auto-deployed to the Workloads and Sandbox OUs |

**Approved structure diagram.** When a design is approved, the final stage of the workflow shows the selected OU structure as a diagram:
- The root, then a *Foundation* row (Security, Infrastructure, Policy Staging, Exceptions, Suspended and so on) and an *Environments (isolated)* row, with each OU's accounts.
- Parent OUs (if chosen) and compliance child OUs appear nested under them.
- An `OuDiagramRenderer` builds it from the approved design version as SVG plus a Mermaid source.
- It is committed to `landing-zone-infra` as `docs/ou-structure.svg` and `docs/ou-structure.mmd`, and can be downloaded from the UI.
- It is redrawn for every approved version, so the diagram always matches what was deployed.

After stack 4, the platform reads the StackSet outputs and **fills the environment, account and network registries** (§5.5, §10). The project wizard is then ready to use without manual setup.

**Approvals** reuse the release policy (§8): a platform admin submits, a different admin approves, and high-risk plans need two approvers. Stacks are applied through GitHub Actions from a `landing-zone-infra` repository, with a GitHub environment that requires reviewers, using the same pattern as §8.

### 20.8 Verification

| Check | Source |
|---|---|
| Fixed rules R1–R4 hold in the live organization | Organizations `ListOrganizationalUnitsForParent`, `ListTargetsForPolicy` |
| Stacks complete and drift-free; landing zone not drifted | CloudFormation drift detection, Control Tower `GetLandingZone` |
| Controls `Succeeded`, baselines enabled per OU | Control Tower `ListEnabledControls`, `GetEnabledBaseline` |
| Accounts enrolled in the correct OU | Service Catalog provisioned product status, Organizations `ListParents` |
| **No route between environment route tables** except the approved exceptions | EC2 `SearchTransitGatewayRoutes` per environment table |
| IPAM pools non-overlapping; every VPC registered in the network registry | IPAM `GetIpamPoolAllocations` vs the registry |

### 20.9 Backend design (object-oriented, open for extension)

| Component | Responsibility | Extension point |
|---|---|---|
| `LandingZoneQuestionnaire` + `AnswerHandler` (one per question) | Answers → contributions to the design | New handler per question |
| `LandingZoneDesign` | OU tree, accounts, environment links, controls, policies, network plan, version | n/a |
| `OuTreeValidator` rules | R1–R4, unique names, maximum depth 5, at most 5 SCPs per OU (an Organizations quota), compliance OUs complete | New rule classes |
| `IpamPlanner` | Splits the top-level CIDR into non-overlapping pools per environment per region | New allocation strategies |
| `StackRenderer` per stack + **element builders** | Foundation, Structure, Accounts, Network, Bootstrap; builders for OU, policy (one subclass per policy type), baseline, control (batched), account, transit gateway route domain, VPC | New builders registered in a registry, as with blocks (§6) |
| `ControlCatalog` port | Lists controls and baselines. Local fake for tests; AWS adapter later. | New sources |
| `OuDiagramRenderer` (SVG, Mermaid) | Approved design → structure diagram shown at the final stage and committed to the repo | New output formats |
| `LandingZoneRun` saga, `Verifier` rules | §20.7 order with compensation; §20.8 checks | New step and check classes |
| Adapters | `OrganizationsPort`, `ControlTowerPort`, `NetworkPort`. **Local mode** keeps an in-memory organization and network, so the whole workflow runs on Docker Desktop with no AWS account. | AWS adapters later |

API (admin role required): `GET/PUT /v1/admin/landing-zone/questionnaire`, `POST /v1/admin/landing-zone:propose`, `GET/PUT /v1/admin/landing-zone/design`, `POST /v1/admin/landing-zone:plan`, `POST …/plans/{id}:submit|approve|reject`, `GET /v1/admin/landing-zone/runs/{id}`, `GET /v1/admin/landing-zone/controls`.

### 20.10 Decisions

| # | Decision | Status / recommendation |
|---|---|---|
| L1 | New or existing organization | **Decided:** new organization / new subscription |
| L2 | Environment OUs | **Decided:** every environment always its own isolated OU; networking only, declared and inspected |
| L3 | Security OU | **Decided:** exactly one Security (Cyber) OU |
| L4 | Environment count and grouping | **Decided:** asked in the questionnaire (4, 5 or 6; 5 recommended). Recommendation shown in the UI: **keep every environment OU separate** (no Prod/NonProd parents) for an extra security layer |
| L5 | Vend accounts with Account Factory | Recommend **yes** (needed for a new organization) |
| L6 | IAM Identity Center managed by Control Tower | Recommend **yes**, with one permission set per role per environment OU |
| L7 | Inspection for allowed cross-environment flows | Recommend **AWS Network Firewall** in the egress/inspection VPC |
| L8 | Landing Zone Accelerator, AFT or CfCT add-ons | Recommend **none**; native CloudFormation types cover this |

### 20.11 OU tree editor

**Status: approved with changes (E1 allows root-level custom OUs; E4 disables accounts instead of removing them).**

After the questionnaire proposes a structure, a platform admin can adjust it on the Review step before requesting approval:
- add custom OUs, under the root or inside an environment, Infrastructure or another custom OU
- add accounts, disable generated workload accounts, and move accounts
- rename, move and remove the custom OUs

The fixed rules (§20.1) still hold. Anything the questionnaire decides (environments, grouping, compliance scopes, shared accounts, optional OUs) is still changed in the questionnaire, not in the editor.

#### Edits are stored as an ordered list, applied on top of the questionnaire

The design keeps storing the **answers**, plus an ordered list of **tree edits**. The final structure is always:

```
designer(answers)  →  proposed tree  →  apply edit 1 … edit n  →  final tree  →  validator, stacks, diagram
```

- Changing an answer later keeps the edits, and they are applied again to the new proposal. Storing a finished tree instead would throw away every edit whenever an answer changed.
- An edit that no longer fits is **reported as a problem, never dropped silently**. For example: "Edit 3 (rename 'Payments'): OU 'payments' no longer exists." The admin undoes or fixes that edit. Request approval stays disabled while any problem remains.
- Edits are versioned with the design, so the approver sees the questionnaire answers and each manual change.

#### Isolation domains

Every OU belongs to one **isolation domain**. Accounts and custom OUs can move only inside their own domain. This keeps R1: an environment OU holds only its own environment's accounts.

| Domain | OUs in it | Isolation |
|---|---|---|
| An environment (DEV, PROD, PCI-PROD, …) | The environment OU and the custom OUs below it | Inherited from the environment OU: SCPs, RCP isolation (the org-path conditions already use `…/ou-…/*`, §20.5), the RAM share of the environment's shared VPC (§20.4) and the bootstrap StackSet target |
| Infrastructure | The Infrastructure OU and the custom OUs below it | Inherited from Infrastructure |
| **A root-level custom OU** (E1) | That OU and the custom OUs below it | **Its own boundary.** The OU gets the baseline SCP, the chosen controls profile, and its own isolation RCP and SCP (no access to other OUs' resources or roles), like an environment OU. It gets no shared VPC and no Transit Gateway route; network access for it is a later change. |

#### What can be edited

| OU | Rename / move / remove | Add child OU | Accounts |
|---|---|---|---|
| Root (organization) | n/a | **Yes**: a root-level custom OU (its own domain) | None |
| Security (Control Tower) | No (R3) | No | Fixed (Log Archive, Audit, Security Tooling come from step 4) |
| Sandbox (Control Tower) | No | No | Fixed (from step 10) |
| Environment OUs (DEV … PROD, compliance STAGE/PROD) | No (names from step 2, R1) | **Yes** | Add; **disable or enable** the generated workload accounts; move within the environment |
| Prod / NonProd parents, compliance OUs | No (from the grouping and compliance answers) | No | None |
| Infrastructure | No | **Yes** | Add custom accounts; shared accounts are chosen in step 5 |
| Policy Staging, Exceptions, Suspended, Business Users, Automations | No (step 11) | No | Fixed |
| **Custom OUs** | **Rename; move within its domain; remove only when empty** | Yes (up to the 5-level depth limit) | Add, move within the domain; disable or enable; remove accounts that were added in the editor |

**Disable, not remove (E4).** A generated workload account can't be removed, only **disabled**:
- A disabled account stays in the design and is shown greyed out in the tree and the diagram.
- It is not vended (left out of `lz-accounts`), gets no network registration, and doesn't count toward problems.
- **Enable** brings it back. An account added in the editor can still be removed, since removing it just takes back the add.

**Move first, then remove.** A custom OU can be removed only when it has no child OUs and no accounts, including disabled ones. Until then, the Remove action is disabled with the hint: "Move its accounts and child OUs to another OU first." The server refuses the edit with the same message.

Each OU in the API response carries the edits it allows, so the UI shows only valid actions and doesn't repeat these rules:
- OU level: `"allowed_edits": ["add_child", "add_account", "rename", "move", "remove"]`
- Each account: `{"name", "enabled", "added", "allowed_edits": ["move", "disable" | "enable", "remove"]}`
- For `remove`, a non-empty custom OU lists it under `"blocked_edits": {"remove": "Move its accounts and child OUs to another OU first."}`

#### Edit operations (one class per operation, registered by name: Open/Closed)

| `op` | Fields | Effect | Refused when |
|---|---|---|---|
| `add_ou` | `parent` (OU key, or `null` for the root), `name` | Adds a custom OU with key `custom_<slug(name)>`. It joins its parent's domain, or starts a new domain at the root. | Parent doesn't allow `add_child`; name already used; depth over 5 |
| `rename_ou` | `ou`, `name` | Renames a custom OU | Not a custom OU; name already used |
| `move_ou` | `ou`, `parent` | Moves a custom OU | Not custom; the new parent is in another domain, or is the OU itself or one of its children. A root-level custom OU stays at the root. |
| `remove_ou` | `ou` | Removes a custom OU | Not custom; has child OUs or accounts ("Move its accounts and child OUs to another OU first.") |
| `add_account` | `ou`, `suffix` | Adds `<org>-<suffix>` with a plus-addressed email, like generated accounts | OU doesn't allow `add_account`; name already used; suffix not 2–40 lowercase letters, digits or hyphens |
| `disable_account` | `account` | Marks a workload account disabled | Fixed account (Security, Sandbox, shared accounts, Automations); already disabled |
| `enable_account` | `account` | Re-enables a disabled account | Not disabled |
| `remove_account` | `account` | Removes an account added in the editor | Not added in the editor (use `disable_account`) |
| `move_account` | `account`, `ou` | Moves an account | Target is in another domain, or doesn't allow accounts |

The existing rules still apply: unique OU names (`UniqueOuNames`), at most 5 levels deep (`MaximumDepth`), at most 5 SCPs per OU (`ScpQuotaRule`). **New validator rules:** `UniqueAccountNames`, and `AccountsStayInTheirDomain` (a safety net under the edit checks).

#### Backend changes

| Component | Change |
|---|---|
| `app/landing_zone/edits.py` | `TreeEdit` base class with `apply(design, namer) -> list[str]` (problems), one subclass per `op`, `TreeEditRegistry`, `TreeEditor.apply(design, edits)` that numbers problems by edit position |
| `OuNode`, `AccountPlan` | OU: `custom`, `domain`, `allowed_edits()`, `blocked_edits()`, `subtree_accounts()`. Account: `enabled`, `added`, `fixed`. `LandingZoneDesign.accounts()` returns enabled accounts only. |
| `GuardrailPlan` | A root-level custom OU gets the baseline, isolation and perimeter policies and the profile's controls, like an environment OU |
| `LandingZoneService` | `_design_of` applies the stored edits after the designer; propose and create take `{answers, edits}` |
| API | `POST …:propose` and `POST …/designs` bodies become `LandingZoneRequest {answers, edits: TreeEdit[] = []}`, a Pydantic union keyed by `op` (E3). Responses add `edits` to the design, and `allowed_edits` / `blocked_edits` to each OU and account. Accounts become objects. |
| Migration | `landing_zone_designs.edits` JSON column, default `[]` |
| Network registration, executor | Use the enabled `subtree_accounts()` of each environment OU, so accounts in child OUs get the shared VPC registered too |
| Diagram | Disabled accounts are drawn greyed and marked "(disabled)" |

#### UI (Review step)

- After **Propose structure**, the OU tree becomes editable. Each OU row shows only the actions in its `allowed_edits`: **Add OU**, **Add account**, **Rename**, **Move to…**, **Remove**. A blocked action is shown disabled, with its reason. Each account shows **Move to…**, **Disable** / **Enable** or **Remove**. An **Add OU at root** action sits above the tree. Small inline forms, no modal dialogs.
- Every edit is added to the draft and the structure is **proposed again at once** (E2). The server is the single source of truth for the tree, problems, diagram and files.
- A **Manual changes (n)** list under the tree shows each edit in plain words ("Added OU Payments under PROD", "Disabled acme-retail-prod"), with **Undo** on each. Problems name the edit they come from.
- The Approvals detail view lists the manual changes, so the second admin can see what was changed by hand.

#### Testing (TDD, 100% coverage)

- Backend:
  - one test module per edit class: it applies, and each refusal
  - `TreeEditor` replay: order, and stale edits become problems
  - the new validator rules
  - `allowed_edits` / `blocked_edits` per OU kind and account
  - root-level custom OU policies and controls
  - disabled accounts left out of vending and network registration
  - API round trip (propose and create with edits, stored and returned)
  - the migration
- Frontend:
  - the draft's edit list: add, undo, request payload
  - each tree action producing the right edit and re-proposing
  - only allowed actions shown, and blocked actions with their reason
  - disable and enable
  - the manual changes list
  - stale-edit problems blocking Request approval

#### Decisions

| # | Decision | Status |
|---|---|---|
| E1 | Custom OUs directly under the root | **Decided: allowed.** Each root-level custom OU is its own isolation domain with baseline, isolation and perimeter policies and the profile's controls. It gets no shared VPC. |
| E2 | Re-propose after every edit | **Decided: yes.** |
| E3 | Change the propose/create request body to `{answers, edits}` | **Decided: yes.** |
| E4 | Removing generated workload accounts | **Decided: disable instead of remove.** Disabled accounts stay in the design, aren't vended, and can be re-enabled. A custom OU is removed only after its accounts and child OUs are moved elsewhere. |

### 20.12 Industry templates and control packs

**Status: approved (T1–T6 as recommended) and implemented.**

Customers can start from a ready-made **industry template** instead of designing a landing zone from scratch. A template sets the questionnaire answers, the OU structure (including preset custom OUs) and a set of **control packs**: Control Tower controls with the OUs they apply to. The customer can use the template as is, or adjust it:
- pick a different combination of environments
- add or remove OUs in the tree editor (§20.11)
- turn control packs on or off

The design records which template and version it started from, and lists every change made to it.

#### 20.12.1 Research findings

Sources:
- [aws-samples/aws-control-tower-controls-cdk](https://github.com/aws-samples/aws-control-tower-controls-cdk), including its Control Catalog export of 760 controls
- *AWS Control Tower User Guide* (PDF, 729 pages)
- [Frameworks supported](https://docs.aws.amazon.com/controltower/latest/controlreference/frameworks-supported.html)
- [Control Catalog ontology](https://docs.aws.amazon.com/controlcatalog/latest/userguide/ontology-overview.html)

| # | Finding | Effect on this design |
|---|---|---|
| F1 | Controls are enabled by **global identifier**, `arn:aws:controlcatalog:::control/<id>`. The sample states that regional identifiers (`arn:aws:controltower:<region>::control/AWS-GR_…`) are **no longer supported**. | **Our `lz-structure` stack uses regional identifiers today.** This work moves every control to global identifiers (§20.12.6). |
| F2 | The catalog has 760 controls: <ul><li>66 preventive: 53 SCP, 9 RCP, 4 EC2 declarative policies</li><li>459 detective: 263 Config rules, 196 Security Hub controls</li><li>235 proactive (CloudFormation hooks)</li></ul> | Packs mix all three behaviors. Proactive controls need the CloudFormation-hooks prerequisite control (`CT.CLOUDFORMATION.PR.1`). Security Hub-based detective controls need Security Hub, which our Security OU design already enables. |
| F3 | Control Catalog maps controls to **17 frameworks** through `ListControlMappings`: <ul><li>PCI DSS v3.2.1 and v4.0</li><li>NIST SP 800-53 r5, NIST SP 800-171 r2, NIST CSF v1.1</li><li>FedRAMP r4</li><li>ISO/IEC 27001:2013 Annex A</li><li>SSAE-18 SOC 2</li><li>CIS AWS Benchmark v1.2/1.3/1.4, CIS v7.1/v8.0</li><li>ACSC Essential Eight, ACSC ISM</li><li>CCCS Medium</li><li>AWS Well-Architected v10</li></ul> **HIPAA, GDPR and GxP are not mapped directly.** | Templates show "aligned with" frameworks, using mapping data from the catalog. They never claim compliance. Healthcare aligns through NIST 800-53 r5; the EU template uses data-residency controls plus ISO 27001. |
| F4 | Up to **100 control operations** can be in flight, but **10** run at a time (the rest queue). Five account operations run at once. | Our `DependsOn` batches of 10 controls already respect this. Templates with ~60 controls per OU still deploy in one stack. |
| F5 | Limits: <ul><li>**10 SCPs per OU** in Control Tower</li><li>OUs nested at most 5 levels</li><li>**≤1,000 accounts per OU** (fewer above 15 governed Regions)</li><li>10,000 accounts per organization</li></ul> | The SCP quota rule moves from 5 to the Control Tower limit of 10, and counts Control Tower's own SCPs (§20.12.6). A warning appears when an OU's planned accounts × governed Regions nears the registration limits. |
| F6 | Region deny can be applied **per OU** with parameters (`AllowedRegions`, `ExemptedPrincipalArns`, `ExemptedActions`), as well as for the whole landing zone. | The data-residency pack uses the per-OU control. Our hand-written region-deny statement is dropped from the baseline SCP when that pack is on, which frees SCP space. |
| F7 | A **digital sovereignty** control group (65 controls) covers data residency, granular access, encryption and resiliency. Examples: disallow cross-Region networking or S3 replication, disallow VPN, key material from CloudHSM or an external source. | Used by the EU sovereignty template and the optional strict-residency pack |
| F8 | **Landing zone 4.0**: <ul><li>Config, CloudTrail, SecurityRoles and **Backup** become optional integrations, with their own baselines</li><li>Control Tower no longer creates the Security OU</li><li>Drift alerts go to EventBridge</li></ul> We pin **3.3** today. | Templates don't depend on 4.0. Moving to 4.0, which adds a central Backup vault for regulated templates, is a separate decision (T5). |
| F9 | The user guide recommends these OUs: Security, Sandbox, **Infrastructure**, **Workloads**, with **Production and Staging always separate**. | Matches rule R1. Every template keeps Production and Staging as separate OUs. |
| F10 | The CDK sample's configuration is a list of `{controls (+ parameters, tags), OU ids}`. | That's what a control pack is: a set of controls plus an OU selector. |
| F11 | **Preventive controls flow down to nested OUs; detective and proactive controls do not and must be enabled on each nested OU** (user guide, *Nested OUs and controls*). | The pack resolver puts preventive controls on the top-most targeted OU only, and detective and proactive controls on every targeted OU, nested ones included. This also gives OUs added in the tree editor (§20.11) their own detective controls. |
| F12 | CloudFormation allows **500 resources per stack**. A regulated template with many OUs approaches that in `lz-structure`. | A validation problem blocks approval when any stack would exceed 500 resources. |

#### 20.12.2 Concepts

| Concept | What it is | Where it lives (Open/Closed) |
|---|---|---|
| **Control catalog snapshot** | The controls the packs use: global id, name, behavior, severity, implementation, parameters, and **frameworks** (from `ListControlMappings`) | `backend/app/landing_zone/catalog/controls.yaml`. Refreshed by `scripts/refresh_control_catalog.py` (read-only Control Catalog API; decision T2). Checked against `ListControls` when the plan is built (§20.6). |
| **Control pack** | A named, versioned set of controls, with a **selector** that says which OUs receive them, and optional parameters (for example, allowed Regions) | One YAML file per pack in `catalog/packs/`. A new pack adds a file. |
| **OU selector** | Chooses target OUs from the final tree (after edits): `workloads`, `production_tier`, `nonproduction_tier`, `sandbox`, `infrastructure`, `compliance:<scope>`, `custom_domains` | One class per selector, in a registry |
| **Industry template** | A versioned bundle: questionnaire answers, preset tree edits (§20.11), control packs, aligned frameworks and a description | One YAML file per template in `catalog/templates/`. A new industry adds a file. |
| **Environment catalog** | The environments a design can include (§20.12.4) | Code constant with a tier per environment |

#### 20.12.3 Control packs

The controls below are the pack contents, by global id (the `<id>` in `arn:aws:controlcatalog:::control/<id>`) and catalog name. **Prev** = preventive, **Det** = detective, **Pro** = proactive.

**`foundation`** (all workload OUs). Identity and public-exposure basics.

| Control (global id) | Behavior | Name |
|---|---|---|
| `5kvme4m5d2b4d7if2fs5yg2ui` | Prev (SCP) | Disallow actions as a root user |
| `8ui9y3oace2513xarz8aqojl7` | Prev (SCP) | Disallow creation of access keys for the root user |
| `24izmu4k16gv9tvd7sexnyrfy` | Det | Detect whether MFA for the root user is enabled |
| `1fvktjhpo9wdpt3pjb2wsz7nt` | Det | Detect whether MFA is enabled for IAM users of the console |
| `6wmutsohbkwhfw6sf7cbt5e81` | Det | S3 account-level Block Public Access set |
| `4jc77cq1lcr7g64xywwypykv8` | Det | Detect public access to RDS database instances |
| `1h4eyqyyonp19dlrreqf1i3w0` | Det | Detect public access to RDS snapshots |
| `6rilu41n0gb9w6mxrkyewoer4` | Det | Detect unrestricted incoming SSH |
| `clmlaa2in1wkntwekh7uw2jyx` | Prev (declarative) | Disallow public sharing of AMIs |
| `ek6wc2bmgzmho1kk6bn236mqt` | Prev (declarative) | Disallow public sharing of EBS snapshots |

**`data-protection`** (all workload OUs). Encryption at rest and in transit.

| Control | Behavior | Name |
|---|---|---|
| `dkjyeuczqj3rnyhn9116p16pw` | Prev (SCP) | Require an attached EBS volume to be encrypted at rest |
| `97hes2glndlye96adkdcdeef4` | Prev (SCP) | Require an EBS snapshot to be created from an encrypted volume |
| `chlzfpsllhs3knp1ixr773wa6` | Prev (SCP) | Require that an EBS snapshot cannot be publicly restorable |
| `7mo7a2h2ebsq71l8k6uzr96ou` | Prev (RCP) | Require encryption of data in transit for calls to S3 |
| `e34kieahgkm0lggs5g0s412jt` | Det | Detect whether RDS storage encryption is enabled |
| `d4wgeffz6izrb627c2yb8nq8d` | Det | S3 default encryption enabled |
| `47j0mbl42qhyollch0c07aawc` | Pro | Require an RDS instance to be encrypted at rest |
| `b7p5zuz380l9pblepsai1u6an` | Pro | Require an S3 bucket to use SSE-KMS |

**`network-hardening`** (all workload OUs).

| Control | Behavior | Name |
|---|---|---|
| `df2ta5ytg2zatj1q7y5e09u32` | Det | Detect unrestricted incoming TCP traffic |
| `e94oghk9gn3wb5xhpw9l53xr9` | Det | Network ACLs don't allow 0.0.0.0/0 to ports 22/3389 |
| `cdn8m939ffm43gw43z7fzlmoj` | Pro | Require network ACLs to block 0.0.0.0/0 to ports 22/3389 |
| `10au7g2tdfmykh2cunfbpbam1` | Det | EC2 instances use IMDSv2 |
| `2wsx5sll20kxurworrzvjn7by` | Pro | Require an EC2 launch template to have IMDSv2 |
| `ev4nb47hdhfom2ic1k0ljc7am` | Pro | Require launch templates not to auto-assign public IPs |

**`logging-integrity`** (workload OUs and Infrastructure).

| Control | Behavior | Name |
|---|---|---|
| `624yg0j9d8swiglwfc1m4kvnm` | Det | CloudTrail log file validation enabled |
| `cok7rgoujcdjcy6bjzgpvnq8w` | Pro | Require a CloudTrail trail to have log file validation |
| `blnba8rkwuvh4lm6aczhfk3t6` | Det | VPC flow logging enabled in all VPCs |
| `ajlgwooddm54wepz191t6gd0a` | Pro | Require ELB load balancers to have logging |
| `62smpoz33dsy0oa7u1iwa58lz` | Det | GuardDuty enabled |

**`key-management`** (production-tier and compliance OUs).

| Control | Behavior | Name |
|---|---|---|
| `bpnmuwwmpvn362b2l34xxrqfx` | Prev (RCP) | Require S3 uploads to use SSE-KMS |
| `beyhbq47poryf052dlel7oig5` | Prev (SCP) | Require a KMS key with the bypass-policy-lockout safety check |
| `8tq2qsio9o9nliasf359rvnso` | Prev (SCP) | Require KMS key policies to limit grants to AWS services |
| `esv514s4zvnxdunuijbgerpn3` | Det | KMS key rotation enabled |
| `54a6rhgyml01y7vexkrn7bgd2` | Det | Secrets Manager automatic rotation enabled |

**`production-resilience`** (production-tier OUs).

| Control | Behavior | Name |
|---|---|---|
| `avr20py8ssve39u69tyuxcanz` | Pro | Require RDS instances with multiple Availability Zones |
| `1b4fdyb4pwzlryd3wds4nu754` | Det | RDS instances with multiple Availability Zones |
| `1cxi1br09glocqagbfwu2kgxu` | Pro | Require RDS deletion protection |
| `4docid6lj7n5tstdmm7btegt1` | Pro | Require DynamoDB point-in-time recovery |
| `aqh482zxh1libhd8e5pff5r1w` | Det | EC2 instances protected by a backup plan |
| `dm91qhaj7bjtyrovbq0szj49u` | Det | DynamoDB tables in a backup plan |

**`pci-cde`** (`compliance:PCI` OUs: the cardholder data environment).

| Control | Behavior | Name |
|---|---|---|
| `41ngl8m5c4eb1myoz0t707n7h` | Prev (SCP) | Disallow internet access for a customer-managed VPC instance. Fits our central-egress design: workload VPCs have no internet gateway. |
| `5rlqt6yj6u0v0gb62pqdy4ae` | Prev (SCP) | Disallow VPN connections |
| `5svkm0sfsp3chc06m683cygz` | Det | CloudTrail logs all S3 write data events |
| `65l0pkpmktv0d9qw0c7gdhv5d` | Det | CloudTrail logs all S3 read data events |
| `6qvep4e99ha6pgc0osehy0w4t` | Pro | Require RDS parameter groups to require TLS |
| `3bsf69bolxub33ycbh9oiiphi` | Det | GuardDuty Malware Protection enabled |

**`data-residency`** (all workload OUs). Parameter `AllowedRegions`, which defaults to the governed Regions.

| Control | Behavior | Name |
|---|---|---|
| `ka8e3pkqefnjsxuyc26ji580` | Prev (SCP, parameterized) | Deny access based on the requested Region, per OU |
| `dvuaav61i5cnfazfelmvn9m6k` | Prev (SCP) | Disallow cross-Region networking (EC2, CloudFront, Global Accelerator) |
| `53u8m2z255npa7rldrk77vm5z` | Prev (SCP) | Disallow EC2 VM import and export |

**`strict-residency`** (optional, off by default: T6).

| Control | Behavior | Name |
|---|---|---|
| `3zbcht7oxkzts9r1z20nz5lcw` | Prev (SCP) | Disallow cross-Region replication for S3 buckets. **Conflicts with DR/HA projects whose S3 buckets replicate to the second Region (§4.11)**; the wizard hides replicated S3 for these OUs. |
| `d0dnxm99zg7gfsow9ei70qhea` | Prev (SCP) | Require KMS customer-managed keys with external key material |

**Controls profiles (§20.6) become packs too**, so the "Start from scratch" path behaves as before, now with global identifiers:
- Baseline = `foundation`
- Strongly recommended = `foundation` + `data-protection` + `network-hardening`, plus `production-resilience` on production-tier OUs
- Regulated = Strongly recommended + `logging-integrity` + `key-management`

The same control from two packs on one OU is enabled once.

#### 20.12.4 Environment combinations

Today a customer chooses 4, 5 or 6 environments. This becomes a **choice of environments from a catalog**, with 4, 5 and 6 kept as one-click presets:

| Environment | Tier | Notes |
|---|---|---|
| Sandbox | sandbox | Optional (recommended). Control Tower creates the Sandbox OU. |
| DEV | non-production | |
| QA | non-production | Functional test |
| TEST | non-production | Integration test |
| UAT | non-production | Business acceptance; renameable (e.g. VALIDATION for GxP) |
| PERF | non-production | Performance and load testing |
| STAGE | production | **Always included** (F9: Staging distinct from Production) |
| PROD | production | **Always included** |

The rules:
- STAGE and PROD are always included, plus at least one non-production environment.
- A design has at most 8 environments.
- Every environment remains its own isolated OU (R1).
- Names stay editable.
- The IPAM planner already splits the CIDR for any number of environments.

`environment_count` is replaced by `environment_ids: [ids]` (`environments()` stays the method that lists them). Old answers with `environment_count` still load, mapped to the matching preset (decision T3).

#### 20.12.5 Industry templates (v1)

Each template fills in the questionnaire and the tree editor. Everything stays editable, and the Review step shows "Based on *template* v1" with the list of differences.

| Template | Aligned frameworks (F3) | Environments | Structure (beyond Security, Infrastructure, Sandbox, environments) | Accounts | Packs | Notable answers |
|---|---|---|---|---|---|---|
| **Financial services** (banking, payments, insurance) | PCI-DSS-v4.0, SSAE-18-SOC-2, NIST-CSF-v1.1 | Sandbox, DEV, TEST, UAT, STAGE, PROD | PCI OU (PCI-STAGE, PCI-PROD); root-level custom OU **Third-party Integrations** (vendor-connected accounts in their own isolation domain); Exceptions, Suspended | One per product | all except data-residency and strict-residency | Regulated profile; logs kept 7 years; Direct Connect; inspection on; Security Tooling account; sandbox $300 a month, 14-day expiry |
| **Healthcare & life sciences** (HIPAA-aligned, GxP) | NIST-SP-800-53-r5 (HIPAA Security Rule crosswalk), ISO-IEC-27001 | Sandbox, DEV, TEST, **VALIDATION** (UAT renamed, for GxP IQ/OQ/PQ), STAGE, PROD | HIPAA and GxP compliance OUs; root-level custom OU **Research** (de-identified data, isolated from clinical workloads) | One per product | foundation, data-protection, network-hardening, logging-integrity, key-management, production-resilience | Regulated profile; logs kept 7 years; inspection on |
| **Public sector** (FedRAMP Moderate-aligned commercial Regions) | NIST-SP-800-53-r5, FedRAMP-r4, NIST-SP-800-171-r2 | Sandbox, DEV, TEST, STAGE, PROD | Exceptions, Suspended | One per portfolio | foundation, data-protection, network-hardening, logging-integrity, key-management, production-resilience, **data-residency (US Regions)** | Governed Regions us-east-1 and us-west-2. Note: FedRAMP High and ITAR need AWS GovCloud, which this tool doesn't target. |
| **Retail & e-commerce** | PCI-DSS-v4.0, CIS-AWS-Benchmark-v1.4 | Sandbox, DEV, QA, PERF (peak-season load tests), STAGE, PROD | PCI OU for the cardholder data environment only, so the rest of retail stays out of PCI scope; root-level custom OU **Store Edge** (in-store and IoT accounts) | One per portfolio | foundation, data-protection, network-hardening, production-resilience, pci-cde | Strongly recommended profile; sandbox per developer |
| **SaaS & technology** | SSAE-18-SOC-2, CIS-v8.0, AWS-WAF-v10 | Sandbox, DEV, STAGE, PROD | Custom OU **Tenants** under PROD (account-per-tenant silo model); Automations OU (CI/CD) | One per product | foundation, data-protection, network-hardening, production-resilience | Strongly recommended profile; local egress allowed |
| **EU data sovereignty** (GDPR-aligned) | ISO-IEC-27001, NIST-CSF-v1.1 (GDPR has no catalog mapping; residency comes from controls) | Sandbox, DEV, TEST, STAGE, PROD | Exceptions, Suspended | One per portfolio | foundation, data-protection, network-hardening, logging-integrity, key-management, **data-residency (EU Regions)**; strict-residency offered | Home Region eu-central-1; governed Regions eu-central-1 and eu-west-1 |
| **Start from scratch** | n/a | Recommended five | Recommended defaults | One per portfolio | From the controls profile | Today's questionnaire |

Example template file (`catalog/templates/saas.yaml`):

```yaml
id: saas
version: 1
name: SaaS & technology
industry: Technology
description: Account-per-tenant SaaS with SOC 2-aligned controls.
frameworks: [SSAE-18-SOC-2-Oct-2023, CIS-v8.0, AWS-WAF-v10]
answers:
  environments: [sandbox, dev, stage, prod]
  account_model: product
  infrastructure: [network, shared_services, identity, backup, monitoring, cicd]
  network: {egress: local}
  controls_profile: recommended
edits:
  - {op: add_ou, parent: prod, name: Tenants}
packs: [foundation, data-protection, network-hardening, production-resilience]
```

#### 20.12.6 Changes to the platform

| Area | Change |
|---|---|
| Answers | Add `template: {id, version} \| null`, `environment_ids: [ids]` (replaces `environment_count`; T3), and `control_packs: [ids] \| null` (null means the profile's packs). Add `pack_parameters` (for example, `data-residency.AllowedRegions`, which defaults to the governed Regions). |
| Catalog | `app/landing_zone/catalog/`: `ControlCatalogSnapshot`, `ControlPack`, `PackRegistry`, `OuSelector` subclasses, `PackResolver`, `TemplateRegistry`, and `ControlCatalogRefresher` (`uv run --with boto3 python -m app.landing_zone.catalog.refresh`). Everything is loaded from the YAML files and validated (unknown control, selector or pack ids fail fast). The snapshot was generated from the sample repo's Control Catalog export, so names, behaviors and severities match the catalog. |
| Guardrails | `ControlCatalog` (regional `AWS-GR_` names, §20.6) is replaced by a `PackResolver`: final tree + packs → controls per OU, with duplicates removed and inheritance applied (F11). **Change from the first draft:** our own baseline SCP keeps its root-user and region-deny statements, because it also covers OUs the packs don't target (Policy Staging, Exceptions, Business Users, Automations). The raised quota of 10 leaves room. |
| `lz-structure` | `AWS::ControlTower::EnabledControl` uses `arn:aws:controlcatalog:::control/<id>` (F1), with `Parameters` for parameterized controls. Batches of 10 stay (F4). The CloudFormation-hooks prerequisite is enabled on OUs that get proactive controls (F2). |
| Validation | `ScpQuotaRule` uses the Control Tower limit of **10** SCPs per OU (F5), counting our SCPs, Control Tower's SCP-based controls, and FullAWSAccess. Exactly how Control Tower packs controls into SCPs is unverified (O1), so the rule counts one SCP per 5 SCP-type controls. New problem: `StackSizeRule` (F12). New **warnings**, returned with each proposal and shown without blocking approval (`DesignAdvisor`): a pack that reaches no OU, the unresolved CloudFormation-hooks prerequisite (O2), strict residency vs DR replication, and an OU planned beyond the registration limit (F5). |
| API | `GET /v1/admin/landing-zone/templates` returns summaries: industry, frameworks, environments, OU count, distinct controls by behavior and total enablements (controls × OUs). `GET …/templates/{id}` returns the full template. `GET …/control-packs` returns packs with their controls, and the profile → packs mapping. Proposals add, per OU, the controls that apply (`id`, `name`, `behavior`, `severity`, `packs`) and counts. |
| Bundle | `design.json` records the template and version, the packs and their parameters. `docs/controls.md` lists the controls per OU with their framework mappings, for auditors. |
| UI | <ul><li>**New first step, "Start"**: template cards showing industry, aligned frameworks, environments, OU and control counts, and a description. Choosing one fills in the questionnaire and edits. "Start from scratch" keeps today's flow.</li><li>**Environments step**: the environment catalog as checkboxes, with the 4/5/6 presets as buttons.</li><li>**Controls step**: the profile plus pack toggles. Each pack shows target OUs, control counts by behavior and aligned frameworks, with an expandable control list. Turning off a template's pack warns: "Removes alignment with PCI-DSS-v4.0 for PCI OUs".</li><li>**Review step**: a "Based on *template* v1" banner with the differences and **Reset to template**. Each OU in the tree shows its control count.</li></ul> |

#### 20.12.7 Testing (TDD, 100% coverage)

- **Catalog loading:**
  - every template and pack file validates
  - unknown ids fail
  - every control id in a pack exists in the snapshot
- **Each OU selector** against designs with grouping, compliance scopes and custom OUs
- **`PackResolver`:**
  - removes duplicate controls
  - passes parameters through
  - selects production-tier OUs only
- **Each template:**
  - proposes with **no problems**
  - every stack passes cfn-lint (added to the lint variants)
  - SCP quota respected
  - environments, OUs and packs as documented
- **Environment catalog:** the required STAGE and PROD, the maximum of 8, and old `environment_count` answers still load
- **Structure stack:**
  - global identifiers
  - parameters on the region-deny control
  - batches of 10
  - the hooks prerequisite
- **UI:** template cards, filling in from a template, differences and reset, environment checkboxes and presets, pack toggles with warnings, controls per OU

#### 20.12.8 Decisions and open questions

| # | Decision | Recommendation |
|---|---|---|
| T1 | The six industry templates in §20.12.5 (plus Start from scratch) | **Approve the list.** More industries (energy, media, telecom) are new YAML files later. |
| T2 | Framework mappings come from `ListControlMappings`, a read-only call that needs AWS credentials in any account | **Run `scripts/refresh_control_catalog.py` once with your credentials** and commit the snapshot. Until then, the UI shows template frameworks as *intended alignment (unverified)*. |
| T3 | Replace `environment_count` with an environment list (catalog of 8, with STAGE and PROD required) | **Yes**, keeping 4/5/6 as presets |
| T4 | Move all controls to global identifiers and replace the profile catalog with packs | **Yes.** It's required (F1), and the profiles keep their meaning. |
| T5 | Landing zone 4.0 (optional integrations, central Backup vault) | **Stay on 3.3 for this change**; plan 4.0 separately |
| T6 | The strict-residency pack (blocks S3 cross-Region replication) | **Optional, off by default**, because it breaks DR/HA S3 replication |
| O1 | How Control Tower packs SCP-based controls into SCPs per OU | Verify on a real landing zone. Until then, count one SCP per 5 SCP-type controls (conservative). |
| O2 | The global id of the CloudFormation-hooks prerequisite (`CT.CLOUDFORMATION.PR.1`) is not in the sample's 2025 export | Resolve with `ListControls` in the refresh script and pin it in the snapshot |

---

## 21. Read-back: editing generated repositories in the UI

Users change infrastructure the platform already generated by loading it back into the UI. The platform reads back **only repositories it generated**. It never reverse-engineers CloudFormation text: every generated repo carries the platform's own input (`infra.json`, `design.json`), and a **signed manifest** proves the input and every generated file are exactly what the platform wrote.

### 21.1 Research findings

| # | Finding | Consequence |
|---|---|---|
| R1 | Parsing the CloudFormation back into the input is lossy. Projects: ownership, environments, regions and network selections never reach `template.yaml`; connections are merged into IAM statements, `Lambda::Permission`s and bucket notifications; logical IDs are not invertible (`a-1b` and `a1b` both give `A1b`). Landing zone: sandbox budget and expiry, the industry template, the control packs (expanded into `EnabledControl`s and de-duplicated by inheritance), IPAM-derived CIDRs and plus-addressed emails. | The **input file is the source of truth**; CloudFormation is only used to detect hand edits. |
| R2 | Generation is deterministic (no UUIDs or timestamps; fixed key order, §6.1), so regenerating from the stored input reproduces the committed files byte for byte while the generator, registry and control catalog are unchanged. | Hand edits are detected by hashing, and expected content is rebuilt by regenerating. |
| R3 | `design.json` held the answers and the **final** OU tree, not the ordered `edits` (§20.11), so the repo alone could not rebuild the design. | `design.json` now records `edits` too. |
| R4 | The `cloudinfra-marker` ownership marker lived outside the git tree, and no GitHub custom property, topic or commit trailer was set. Anyone can create a repo with an `infra.json`. | Ownership is proved by a **server-signed manifest**, cross-checked with the database; custom properties are only a discovery filter. |
| R5 | The project commit SHA was discarded, and `GitHubPort` had no read operations. | The project row stores `commit_sha`; `GitHubPort` gains `read_files` and repository properties. |
| R6 | Prior art: Copier (`.copier-answers.yml` + three-way update), cruft (`.cruft.json`), JHipster (`.yo-rc.json`), Projen (`.projen/files.json` + anti-tamper check), Infrastructure Composer (`Metadata: AWS::Composer::Groups`). | We follow **Projen's anti-tamper model** now (decision RB1) and keep Copier's three-way update as the later extension. |
| R7 | GitHub repository custom properties exist only on organization repos, are typed and can be locked to org owners; topics are public and editable by any repo admin. Commits made by a GitHub App through the API are signed by GitHub ("Verified"). | Custom properties on org repos, topics as the fallback; neither is trusted alone. |
| R8 | `yaml.safe_load` fails on short-form tags (`!Ref`); cfn-lint's decoder (already a dependency) parses them. Our templates use long form only. | Not needed for this phase. Any future template-level merge (RB4) uses cfn-lint's decoder. |

### 21.2 The manifest

Every commit the platform makes writes `.cloudinfra/manifest.json` next to the generated files:

```json
{
  "schema": 1,
  "kind": "landing-zone",
  "id": "4f0c…",            // project name, or landing zone design id
  "revision": 3,            // landing zone design version; 1 for a new project
  "generator": {"name": "cloudinfra-landing-zone", "version": "0.1.0"},
  "input": "design.json",
  "files": {"design.json": "sha256:…", "stacks/lz-structure.yaml": "sha256:…"},
  "signature": {"algorithm": "HMAC-SHA256", "key_id": "2026-10", "value": "…"}
}
```

- `files` lists the SHA-256 of **every** generated file, the input included.
- The signature is an HMAC over the canonical JSON of the manifest without `signature` (sorted keys, no whitespace). The keys live only in the control plane (Secrets Manager → `MANIFEST_SIGNING_KEYS`, a JSON map of key id → secret; `MANIFEST_ACTIVE_KEY` picks the signing key). A copied or hand-written manifest fails verification; rotation adds a key and switches the active id, and old ids keep verifying.
- Locally the default key is `local-dev` with a fixed, non-secret value.
- Files the user adds (not in `files`) are ignored. Files the generator stops producing are not deleted (commits only add or overwrite, §7.2).

The repository also gets custom properties `cloudinfra-managed=true`, `cloudinfra-kind` and `cloudinfra-id` (topics on personal-account repos).

### 21.3 Read-back checks

A `RepositoryReader` runs an ordered chain of checks (one class each, Open/Closed). A **blocking** finding stops the chain and nothing is loaded; **warnings** are shown and loading continues.

| Check | Blocks when | Warns when |
|---|---|---|
| `RepositoryExistsCheck` | The repository does not exist | |
| `PropertiesCheck` | `cloudinfra-managed` is not `true`, or kind/id do not match | |
| `ManifestSignatureCheck` | The manifest is missing or unreadable, the key id is unknown, or the HMAC does not match | |
| `RecordCheck` | Kind or id differ from the item asked for, or no database record matches the id and revision | |
| `IntegrityCheck` | Any file listed in the manifest is missing or its hash differs (**hand edited**). For each such file the result includes a diff against the regenerated content, when the regenerated content still matches the manifest hash. | |
| `InputCheck` | The input file no longer validates against today's model | |
| `HeadCheck` | | The repository's HEAD is not the commit the platform recorded (commits that did not touch generated files) |
| `RegenerationCheck` | | Regenerating from the input today gives different files (generator, registry or control catalog changed). Saving the change will update them. |

### 21.4 Flow

1. The user picks **Edit** (landing zone: "Edit the current landing zone" on the Start step).
2. `GET /v1/admin/landing-zone/repository:read-back` (or `GET /v1/projects/{name}/repository:read-back`) reads HEAD and runs the checks.
3. Result: `{verified, commit_sha, findings: [{check, severity, message, files}], design: {id, revision}, request}`. `request` is present only when `verified` is true: `{answers, edits}` for the landing zone, the `ProjectRequest` for a project.
4. The UI loads the request into a draft (`LandingZoneDraft.fromRequest`) and opens the Review step. Findings are shown above the steps; hand-edited files are listed with their diffs and loading is refused.
5. The landing zone continues through the normal workflow: create → submit → approve, which commits a new version with a new manifest.

### 21.5 Platform changes

| Area | Change |
|---|---|
| `app/readback/` | `ManifestSigner`, `Manifest`, `ManifestSealer`; `ReadBackSubject` (`ProjectSubject`, `LandingZoneSubject`: repository, input parsing, regeneration, record lookup); the checks in §21.3; `RepositoryReader`. |
| `GitHubPort` | `read_files(owner, name) → RepositorySnapshot(commit_sha, files)`; `set_repository_properties` and `repository_properties`. `LocalGitHub` implements them with `git ls-tree`/`cat-file` and its settings file. |
| Settings | `manifest_signing_keys`, `manifest_active_key`. |
| Landing zone | `design.json` adds `edits`; the commit is sealed with the manifest and the repository properties are set; `GET …/repository:read-back`. |
| Projects | The commit is sealed; repository properties set on creation; `projects.commit_sha` (migration) stored by `CommitFilesStep`; `GET /v1/projects/{name}/repository:read-back`. |
| UI | Start step: "Edit the current landing zone" card; findings panel with hand-edited files and diffs; `LandingZoneDraft.fromRequest`. |

### 21.6 Testing (TDD, 100% coverage)

- **Manifest:** sign/verify round trip; tampered field, unknown key id and rotated keys; canonical form independent of key order.
- **LocalGitHub:** `read_files` returns the HEAD tree and SHA; empty repository; properties stored and returned.
- **Each check:** passes on a sealed repo and produces exactly its finding on the failure it owns.
- **Reader:** stops at the first blocking finding; warnings do not block; request returned only when verified.
- **Landing zone:** approve writes the manifest, properties and `edits`; read-back after approve is verified and returns the same answers and edits; editing `stacks/lz-structure.yaml` or `design.json` blocks with a diff; a repo with no manifest blocks.
- **Projects:** provisioning writes the manifest and properties and stores `commit_sha`; read-back verified and returns the stored request; not-ours and hand-edited cases.
- **UI:** the edit card loads the design into the draft and opens Review; blocked results show findings and diffs and keep the draft unchanged.

### 21.7 Decisions

| # | Decision | Choice |
|---|---|---|
| RB1 | Hand edits to generated files | **Strict (Projen-style):** detect, show the diff and refuse to load. Revert in GitHub, or change through the UI. |
| RB2 | Source of truth when the database and the repository disagree | **The repository's signed input**, provided it verifies; the database only confirms the platform wrote it. |
| RB3 | Ownership marker | Signed manifest + database record (proof); custom properties on org repos, topics elsewhere (discovery only). |
| RB4 | Later: keep hand edits (Copier-style three-way update over parsed templates, conflicts in the PR) | Phase 2 |
| RB5 | Project "Change infrastructure" in the UI (`ProjectDraft.fromRequest`, change request, PR per §9.8) | Designed in §21.8 |
| RB6 | Optimistic lock (a change records the commit it was read from and fails if HEAD moved) | Projects: included in §21.8 (C5). Landing zone designs: Phase 2 |
| RB7 | Repositories generated before the manifest existed | Rejected by read-back; approving any new landing zone design stamps the repo. |

### 21.8 Change infrastructure for projects (RB5)

A developer changes a provisioned project in the UI. The platform reads the project back (§21.3), lets the developer edit it in the same wizard, and opens a **pull request** on the infrastructure repository with the regenerated files and a new signed manifest. People review and merge the PR in GitHub (§9.8, Appendix A.7); the platform records the new revision when it learns of the merge.

#### What can change (decision C1)

| Field | v1 | Why |
|---|---|---|
| Services, their settings, connections | **Editable** | The core of §9.8: add a table, grant access, raise memory |
| Network attach and VPC choice per environment/region | **Editable** | GitHub environment variables are reconfigured by the change job |
| Environments | **Add only** | New environments are bootstrapped by the change job. Removing one is a teardown (§21.9) |
| Project name, portfolio, product | **Locked** | They are the repository, the tags and every IAM boundary (§4) |
| Data classification | **Locked** | Changes encryption and tag conditions; needs its own reviewed flow |
| Resilience mode and regions | **Locked** | Needs a data-replication and failover plan (§10) |

The server enforces these rules (`ChangeRule` classes, Open/Closed); the UI only mirrors them by disabling locked fields.

#### Removing services (decision C3)

Removing a service deletes its CloudFormation resources on the next deploy unless a retain policy keeps them (S3 and DynamoDB already use `RetainExceptOnCreate`/`Retain`, §6.4). The change preview lists every removed service with **retained** or **deleted**, and creating the change requires `confirm_removals: true` when anything is deleted.

#### Flow

1. **Projects page → Change infrastructure.** The UI calls `GET /v1/projects/{name}/repository:read-back`. If it is not verified, the findings are shown (§21.4) and nothing else happens.
2. The wizard opens with `ProjectDraft.fromRequest(request)`, locked fields disabled, and a banner "Changing *name* (revision *n*, commit *abc1234*)".
3. **Preview:** `POST /v1/projects/{name}/changes:preview` with `{request, base_commit}` returns the usual preview plus `changed_files` (paths whose content differs from the repository's main branch), `removed_services` (`{id, type, retained}`) and `added_environments`.
4. **Open change request:** `POST /v1/projects/{name}/changes` with `{request, base_commit, confirm_removals}`.
   - Validates the request (§6.6), the `ChangeRule`s, and that something actually changed.
   - **Optimistic lock (RB6, included):** `base_commit` must equal the repository's main HEAD and the project's recorded commit, otherwise 409 "The repository changed since you loaded it".
   - **One open change per project** (decision C4): 409 while another is open.
   - Records a `project_changes` row (`revision = project.revision + 1`, state `queued`) and queues a **change job** on the existing worker.
5. **Change job (saga, §13):** bootstrap new environments and regions → reconfigure GitHub environment variables → commit the regenerated, sealed files to branch `cloudinfra/change-{revision}` → open the PR "Change infrastructure: revision *n*" whose body lists the changed services, files and removals. State becomes `open` with the PR number and URL. Undo deletes the branch.
6. **Merge (decision C2):** reviewers merge the PR in GitHub (CODEOWNERS and branch rules apply). The `pull_request` webhook (`closed`, merged) marks the change `merged` and updates the project: `request`, `revision`, `commit_sha` (the merge commit). Closing without merging marks it `closed`. Locally, `POST /v1/projects/{name}/changes/{id}:merge` and `:close` stand in for GitHub (like the release simulator, §8).
7. After the merge, read-back returns the new revision; the manifest on main says revision *n*, so `RecordCheck` passes.

**Implementation notes.**
- Existing environments run an `outputs:{env}:{region}` step that re-reads their bootstrap outputs and is never undone; only environments the change adds get a `bootstrap:` step that a failure removes.
- GitHub environment variables (for example a new VPC choice) are updated when the change job runs, before the PR is merged, because the deploy workflow reads them as soon as the merge lands on main. A closed change leaves those variables in place; the next change or the reconciler (§5.5.4) brings them back in line.

#### Platform changes

| Area | Change |
|---|---|
| Database | `projects.revision` (default 1). New `project_changes`: id, project_name, revision, request, base_commit, branch, pull_request_number, pull_request_url, state (`queued`, `open`, `merged`, `closed`, `failed`), created_by, merge_commit, timestamps. `jobs.kind` (`provision` or `change`) and `jobs.change_id`. |
| `GitHubPort` | `commit_files(…, branch=…)`, `delete_branch`, `open_pull_request(owner, name, branch, title, body) → PullRequest(number, url)`, `merge_pull_request(…) → sha` and `close_pull_request` (local stand-ins; the real client receives webhooks instead). `LocalGitHub` keeps pull requests in its settings file and merges by fast-forward. |
| Provisioning | `ChangePlanner` builds the change saga from the same step classes (bootstrap, configure environments) plus `CommitBranchStep` and `OpenPullRequestStep`. Sealing uses the change's revision. |
| Read-back | `ProjectSubject.revision` reads `projects.revision`. |
| API | `POST …/changes:preview`, `POST …/changes`, `GET …/changes`, `GET …/changes/{id}`, `POST …/changes/{id}:merge` and `:close` (local only), `POST /v1/github/webhooks` handles `pull_request` for the real adapter later. |
| UI | Projects page: **Change infrastructure** per provisioned project, and the open change's PR link and state. Wizard in change mode: locked fields disabled, removal list and confirmation on Preview, **Open change request** instead of Create, then the job's progress and the PR link. |

#### Testing (TDD, 100% coverage)

- **ChangeRules:** each locked field rejected; environments add-only; no-op change rejected.
- **Preview:** changed files, removed services with retained/deleted, added environments.
- **Create:** stale `base_commit` → 409; second open change → 409; deletions without confirmation → 422; queued job and change row.
- **Change job:** branch commit with a manifest at the new revision; PR opened; new environment bootstrapped and configured; failure undoes the branch.
- **Merge/close:** project request, revision and commit updated on merge; unchanged on close; read-back verified at the new revision afterwards.
- **UI:** Change infrastructure loads the project, locks fields, shows removals and requires confirmation, opens the change and links the PR; refused read-back shows findings.

#### Decisions

| # | Decision | Recommendation |
|---|---|---|
| C1 | Editable fields in v1 | As in the table above: services, settings, connections, network, add environments |
| C2 | Who merges | **People, in GitHub.** The platform never merges its own PR; it learns of the merge by webhook (locally: a simulate button) |
| C3 | Removing services | **Allowed** with the retained/deleted list and explicit confirmation when anything is deleted |
| C4 | Concurrent changes | **One open change per project**; close it to start another |
| C5 | RB6 optimistic lock | **Included here**: base commit must match main HEAD |

### 21.9 Teardown: removing an environment or decommissioning a project, with locked backups and restore

Two teardown flows: **remove an environment** from a project, and **decommission** a whole project. Both are **backup-first**:
1. Nothing is deleted until every data store has a completed backup copied into a **locked vault in the central Backup account**.
2. Those backups cannot be deleted by anyone for **60 days**. After that, only **super users**, manually in the AWS console, can delete them; the platform never deletes a backup.
3. Every teardown leaves a **teardown record**, so the environment or project can be **restored** from its last revision and its backups.

#### 21.9.1 Backups

| Topic | Design |
|---|---|
| What is backed up | Every data store in the environment's stacks, found from the deployed stack's resources (`ListStackResources`) by type: S3 buckets, DynamoDB tables and global tables (backed up in the primary region), RDS/Aurora clusters and instances, EFS file systems. A `BackupTarget` class per resource type maps it to its AWS Backup resource ARN (Open/Closed; new database blocks add one). S3 needs versioning, which every generated bucket already has (§6.4). |
| Not backed up | CloudWatch Logs (AWS Backup does not support them), Lambda code (it is rebuilt from the application repository), IAM roles and other stateless resources (rebuilt from the template). The preview says so. |
| How | AWS Backup on-demand backup job into the workload account's `cloudinfra-teardown` vault, then a **copy job** to the central vault `cloudinfra-teardown-{region}` in the **Backup account** (same region; the landing zone's backup policy already copies production data to the DR region, §20.6). The platform waits until every copy is `COMPLETED`. |
| Locked vault | The central vault has **AWS Backup Vault Lock in compliance mode**: `MinRetentionDays: 60`, no `MaxRetentionDays`, `ChangeableForDays: 3` (after 3 days the lock can no longer be changed or removed, even by the root user). Recovery points are copied **without a lifecycle**, so they are never deleted automatically. |
| Who can delete | The vault access policy denies `backup:DeleteRecoveryPoint`, `backup:DeleteBackupVault`, `backup:PutBackupVaultAccessPolicy` and `backup:DeleteBackupVaultLockConfiguration` to every principal except the **`CloudInfraBackupSuperUser`** role, which needs MFA and is assumable only by a named super-user group. An SCP on all OUs repeats the denial. The production-protection SCP (§20.6) stops exempting the release executor for `backup:DeleteRecoveryPoint`. Vault Lock still blocks even super users for the first 60 days. |
| Checks before deleting | The vault is locked (`DescribeBackupVault`: `Locked = true`, `MinRetentionDays >= 60`); every expected data store has exactly one completed recovery point in it. Any failure stops the teardown **before anything is deleted**. |
| Where the vault comes from | A new landing zone stack, **`lz-backup`**, deploys the locked vault, its KMS key (key policy allows copies from the organization) and the super-user role into the Backup account in every governed region. The bootstrap StackSet adds the `cloudinfra-teardown` vault to every workload account. Cross-account backup is turned on in the management account (`UpdateGlobalSettings`). A landing zone without a Backup account cannot run teardowns; the UI says why. |

#### 21.9.2 Remove an environment

1. **Request:** Projects page, then **Tear down environment** on a project with more than one environment.
   - The preview lists, per region: the stacks to delete, each data store and its backup, and what is not backed up.
   - The requester types the project name to confirm.
2. **Blockers** (one `TeardownBlocker` class each):
   - an open change (§21.8 C4);
   - a release in progress in that environment;
   - the project's last environment (use decommission instead);
   - later, active sharing agreements (§4.11).
3. **Approval per environment (decision TD1):** every environment's deletion has its own approval item.
   - A reviewer approves a non-production environment; STAGE and PROD need a platform admin.
   - Nobody approves their own request.
   - Nothing in an environment is touched (not even backups) until that environment is approved.
4. **Teardown job, one per approved environment.** It runs **forward-only with checkpoints**: deletions cannot be undone, so a failed step stops the job as `failed_needs_attention`. **Retry** resumes from the failed step, and every step is idempotent. The steps:
   1. Back up every data store, copy to the locked vault, verify (§21.9.1).
   2. Lift the production stack policy for this deletion only (recorded).
   3. Delete the application stack in each region, secondary region first.
   4. Empty and delete data stores that retain policies kept, now that they are backed up (decision TD2).
   5. Delete the bootstrap stack (deploy and execution roles).
   6. Delete the GitHub environment and update `ENVIRONMENT_ORDER`.
   7. **Commit revision *n+1* to main** (decision TD4):
      - `infra.json` without the environment;
      - `config/{env}.json` removed;
      - `teardowns/{id}.json` (the record, below);
      - a new signed manifest.

      The project's request, revision and commit are updated, so read-back stays verified.

   The job runs with the release executor's role, which is the only role the production SCP lets delete stacks and data stores.

#### 21.9.3 Decommission a project

A decommission request lists **every** environment of the project, and **each environment is approved separately** (TD1), with typed confirmation on the request.

**Order:**
- An approved non-production environment is torn down at once (its own job and revision, as in §21.9.2).
- STAGE and PROD wait until every non-production environment in the request is torn down. PROD goes last.

**When every environment is torn down:**
- Commit the final revision with the teardown record and a README notice.
- **Archive** the repository (read-only) and set its custom property `cloudinfra-state=decommissioned`.
- Mark the project `decommissioned`.

**When an environment is rejected:**
- That environment stays, and the remaining environments of the request are not torn down.
- Environments already torn down stay torn down (their backups and revisions exist).
- The request ends `partially_completed` and the project stays `active` with the environments that are left.

The platform never deletes the repository: it is the design record a restore starts from.

#### 21.9.4 Teardown record

Stored in the database (`teardowns`) **and** committed to the repository as `teardowns/{id}.json`, so a restore does not depend on the platform's database alone. It holds:
- id, project, scope (`environment` or `project`), environments;
- the revision and request **before** the teardown, and its commit;
- per environment and region: account and stack names;
- per data store: service id, CloudFormation type, physical name, source ARN, **central recovery point ARN**, vault, completion time and `locked_until` (completion + 60 days);
- per environment: its approval (approver, decision, comment, time) and state (`pending_approval`, `approved`, `rejected`, `backing_up`, `deleting`, `completed`, `failed_needs_attention`);
- requested by, overall state (`in_progress`, `completed`, `partially_completed`, `rejected`), timestamps.

#### 21.9.5 Restore

**Restore** on a teardown record (approval as in TD1) rebuilds what was torn down:
1. For a decommissioned project: unarchive the repository and set the project back to `active`.
2. Bootstrap the environment again (the account must still be bound to the portfolio).
3. Run AWS Backup **restore jobs** from the central recovery points into the original physical names. DynamoDB and RDS restore into new resources; S3 restores into a bucket created for it.
4. Create the application stack with a CloudFormation **IMPORT change set** that adopts the restored data stores. All three types support resource import, and the generated templates already give them retain policies.
5. A normal deploy of the environment adds the stateless resources.
6. Commit revision *n+1* with the environment back in `infra.json`. The record is marked `restored`.

Restore needs only the record and the recovery points, which stay for 60 days at least, and until a super user deletes them.

#### 21.9.6 Platform changes

| Area | Change |
|---|---|
| `AwsPort` | `stack_resources`, `start_backup`, `start_copy`, `backup_status`, `vault_lock`, `set_stack_policy`, `delete_stack`, `empty_and_delete` (per data store type), `start_restore`, `import_stack`. `LocalAws` keeps stacks, vaults and recovery points in its JSON state, and **enforces the lock**: deleting a recovery point fails before 60 days, and always fails for any role except the super-user role (to test the policy). |
| `GitHubPort` | `delete_environment`, `archive_repository`, `unarchive_repository`; `commit_files` can delete paths. |
| Database | `teardowns` (the record above), `teardown_environments` (one approval and state per environment) and `teardown_recovery_points`; `projects.status` gains `decommissioned`; `jobs.kind` gains `teardown` and `restore`. |
| Services | `TeardownService` (preview, request, approve/reject, retry, restore), `TeardownBlocker`s, `BackupTarget`s, the teardown and restore planners on the existing worker. |
| Landing zone | `lz-backup` stack; super-user role; SCP and vault policy as in §21.9.1; the bootstrap StackSet's local vault. |
| API | `POST /v1/projects/{name}/teardowns:preview`, `POST …/teardowns`, `GET …/teardowns`, `GET …/teardowns/{id}`, `POST …/teardowns/{id}/environments/{env}:approve`, `:reject` and `:retry` (per environment), `POST …/teardowns/{id}:restore`. |
| UI | **Tear down environment** and **Decommission** on the Projects page, with the preview and typed confirmation; an approvals list with one item per environment; a teardown detail page with job steps, backups and their `locked_until` dates, and **Restore**. |

#### 21.9.7 Testing (TDD, 100% coverage)

- **BackupTarget per type:** source ARN; unsupported types listed as "not backed up".
- **Blockers:**
  - an open change;
  - a release in progress;
  - the last environment.
- **Approvals per environment:**
  - one approval item per environment, also in a decommission;
  - reviewer for non-prod, platform admin for STAGE/PROD;
  - no self-approval;
  - typed confirmation;
  - nothing in an environment runs before its own approval.
- **Job:**
  - backups and copies complete before any delete;
  - an unlocked vault, or a failed backup or copy, stops with nothing deleted;
  - stacks deleted secondary-first;
  - retained data stores emptied and deleted;
  - bootstrap and GitHub environment removed;
  - revision *n+1* committed and read-back verified;
  - retry resumes after a failed delete.
- **Lock (local stand-in):**
  - deleting a recovery point before 60 days fails for everyone;
  - after 60 days it fails for the platform and succeeds only for the super-user role;
  - the platform has no code path that deletes one.
- **Decommission:**
  - each environment waits for its own approval;
  - STAGE and PROD wait for the non-production environments, PROD last;
  - when all are done: repository archived and marked, project `decommissioned`;
  - one rejection leaves the rest, and the request ends `partially_completed`.
- **Restore:**
  - restore jobs to the original names;
  - IMPORT then deploy;
  - revision committed;
  - the project and repository reactivated after a decommission.
- **UI:** previews, confirmation, approval, job progress, backups with lock dates, restore.

#### 21.9.7a Implementation notes

- **Finding data stores.** They come from the template the environment's current request generates (the main resource of each service, its name property resolved with the project, account and region), not from `ListStackResources`. A real AWS adapter can cross-check the deployed stack. A data store whose physical name is not in the template (an RDS cluster without an identifier, any EFS file system) **blocks** the teardown rather than being skipped.
- **Environment states:**
  - `pending_approval`;
  - `approved` (waiting for its turn);
  - `queued`;
  - `running` (backups and deletions show as job steps);
  - `completed`;
  - `rejected` or `cancelled`;
  - `failed_needs_attention`.
- **The Backup account** is resolved when the teardown is requested (configured `backup_account_id`, else the applied landing zone's `<org>-backup` account) and **stored on the teardown**, so a restore uses the same vaults. AWS Backup is reached through `AwsPort.backup(account)`.
- **Restore** is requested with `POST …/teardowns/{id}:restore` and decided with `:approve-restore` or `:reject-restore`, by someone other than the requester; a platform admin is needed when STAGE or PROD come back. Restore is refused while a backup is missing, or when an environment was added back to the project in the meantime.
- **SCPs.** The recovery-point protection is a statement in the existing baseline and infrastructure SCPs, so no OU gains an SCP (quota of 10, §20.12.6).
- **Workload vaults.** Each workload account gets its local `cloudinfra-teardown` vault from a second service-managed StackSet in every governed region.
- **Changes during a teardown.** A teardown or restore in progress blocks new changes (§21.8) on the project.

#### 21.9.8 Decisions

| # | Decision | Recommendation |
|---|---|---|
| TD1 | Approvals | **Decided: one approval per environment, also within a decommission.** Reviewer for non-prod environments; platform admin for STAGE/PROD; never self-approval; typed project name |
| TD2 | Data stores kept by retain policies | **Delete them after their backups are verified in the locked vault** (otherwise teardown leaves billed, unmanaged buckets and tables) |
| TD3 | Backup retention | **Decided: 60 days minimum for every environment**; Vault Lock compliance mode; no automatic deletion; manual deletion by super users only |
| TD4 | How the repository is updated | **Platform commits revision *n+1* directly to main** after approval (like the landing zone, §20.7), because the infrastructure is already gone; no pull request |
| TD5 | The repository on decommission | **Archived, never deleted by the platform** |
| TD6 | Logs | Not backed up in v1 (AWS Backup does not support CloudWatch Logs); exporting logs to S3 is a later option |
| TD7 | Restore in v1 | **Included:** restore an environment or a whole project from its teardown record |

**Found while researching (separate fixes):** curated blocks silently ignored unknown `config` keys, and the UI had no fields for their settings; both are fixed by §6.4.1. (The UI sends `config.properties` only for schema-driven resources, which read it, so no settings were being dropped.) §6.1 says "sorted keys" but templates keep insertion order; only `infra.json` is sorted.

---

## 22. Multi-cloud: one platform for AWS, Google Cloud and Azure

The platform's workflows are cloud-neutral: the questionnaire and the OU-tree editor, approvals, read-back, change requests, teardown, releases, cost centers and topology. Its **outputs** are AWS-specific: CloudFormation, IAM, Organizations and Control Tower, AWS Backup. This section splits the two.
- A **cloud-neutral core** holds the concepts and workflows.
- **Provider plug-ins** (AWS, Google Cloud, Azure) implement them, registered by id: Open/Closed. A fourth cloud is a new package, not a change to the core.

### 22.1 Research findings

| # | Finding | Consequence |
|---|---|---|
| M1 | The code already has extension points for most concepts. Blocks, binders, lint rules, file renderers, provisioning steps, topologies, stack renderers, answer handlers, selectors, packs, templates, design rules, risk and gate rules, read-back checks, teardown blockers and backup targets are all registries or ABCs. But their **contracts** are AWS-shaped: `cloudformation_types`, ARNs, IAM statements, `AwsPort`. Some things are hard-coded with no abstraction: `Template` (a CloudFormation document), naming, IAM policies, the deploy workflow, the landing-zone stacks, and AWS-only lists such as `STATEFUL_TYPES`. | Keep the extension points and make their contracts neutral. Move the AWS details behind a provider. |
| M2 | Nothing records a cloud. Ids are sized for AWS: 12-digit accounts, `vpc-`/`subnet-`/`sg-` patterns, `String(12)` columns. Region tables hold AWS ids. The UI says "Control Tower", "OU", "CloudFormation" and "VPC" everywhere. | A `provider` dimension on requests, designs and registry rows; wider ids; UI wording from the provider. |
| M3 | **Native IaC per cloud.** Google Cloud: **Infrastructure Manager** (managed Terraform, GA, with previews and drift, Git or local source). Deployment Manager is shut down after 30 June 2027. Infrastructure Manager runs Terraform **≤ 1.5.7** only. Azure: **Bicep** with **deployment stacks** (GA; `actionOnUnmanage`, deny settings) and **what-if**. Stack what-if is new and maturity is unverified. | Generated documents per cloud: CloudFormation (AWS), Terraform HCL for Infrastructure Manager (Google Cloud), Bicep deployment stacks (Azure). |
| M4 | **Identity.** GitHub OIDC works on every cloud. AWS: an IAM role per environment account. Google Cloud: Workload Identity Federation with a mandatory attribute condition on repository and environment. Azure: a user-assigned managed identity with a federated credential `repo:ORG/REPO:environment:ENV`, at most 20 per identity, exact match. | The trust subject the platform already computes (`repo:…:environment:…`) is neutral. Each provider turns it into its own trust. |
| M5 | **Hierarchy.** Organization → OU → account (AWS); organization → folder → project (Google Cloud); tenant → management group → subscription, plus resource groups (Azure). Vending: Account Factory; Fabric FAST project factory or the Enterprise Foundations Blueprint; the ALZ subscription-vending AVM module. Google Cloud has **no managed landing-zone service** like Control Tower. Azure ALZ: use the **Bicep or Terraform AVM** accelerators; classic ALZ-Bicep was retired in February 2026. | A neutral hierarchy model: nodes and isolation units. One designer and tree editor. Vending and landing-zone IaC per provider. |
| M6 | **Guardrails.** AWS: SCPs (actions), RCPs (resource perimeter), Control Tower controls. Google Cloud: Organization Policy, including custom CEL constraints and dry-run; IAM deny policies; VPC Service Controls; SCC Security Posture (preventive and detective); Compliance Manager (detective). Azure: Azure Policy deny/modify/deployIfNotExists and regulatory initiatives (mostly **audit**). Deny assignments come only through deployment stacks. **No RCP equivalent.** | A neutral guardrail model (preventive, detective, proactive) with **neutral control packs** that each provider maps to its own controls. Where a cloud can only detect, the pack says so. |
| M7 | **ABAC.** AWS compares principal and resource tags. Google Cloud IAM conditions compare **resource tags to literals**; labels cannot drive IAM. Azure ABAC works only on **storage data-plane** actions. | Isolation is "same project, same environment" everywhere, but the mechanism differs. Google Cloud uses one tag-conditioned binding per value. Azure uses **one resource group per project and environment** as the scope. |
| M8 | **Locked backups.** AWS: Vault Lock compliance mode. Google Cloud: Backup and DR vaults with enforced, indelible retention, but **only VMs, disks, Cloud SQL, AlloyDB and Filestore**. For **GCS and Firestore**, copy or export into a **Bucket Lock**ed bucket in a vault project. Bucket Lock is irreversible and puts a lien on that project. Azure: a **locked immutable vault** (irreversible), Resource Guard multi-user authorization, and Blob vaulted backup that must be **in the same region**. **Cosmos DB backups live in the account and die with it**, so export to an immutable, locked Blob container first. | A neutral `BackupStrategy` per data-store kind and provider. The 60-day lock holds on every cloud, through each cloud's own mechanism. |
| M9 | **Service mapping** for the curated blocks: S3 / GCS / Blob Storage; Lambda / Cloud Run functions / Azure Functions Flex Consumption; DynamoDB / Firestore / Cosmos DB for NoSQL; SQS / Pub/Sub / Service Bus; S3 events / Eventarc or GCS notifications / Event Grid. Google Cloud and Azure have no paired-region model like AWS: Google Cloud uses dual- and multi-region services, and Azure pairs are fixed with some regions unpaired. | Curated services become **neutral kinds** with one implementation per provider. Resilience stays neutral (primary/secondary); each provider supplies how a service replicates. |
| M10 | **Plan and drift.** AWS: change sets and drift detection. Google Cloud: Infrastructure Manager previews and resource drifts (computed per preview). Azure: what-if (noisy) and stack deny settings that prevent drift rather than detect it. | Release rows (Add/Modify/Remove/replacement) come from each provider's plan. Risk rules read block metadata (`stateful`, `permission`), not AWS type lists. |

### 22.2 Neutral vocabulary

| Neutral concept | AWS | Google Cloud | Azure |
|---|---|---|---|
| Organization | Organization | Organization | Entra tenant + root management group |
| Hierarchy node | OU | Folder | Management group |
| Isolation unit (one per environment) | Account | Project | Subscription (+ one resource group per project) |
| Unit vending | Account Factory | Project factory (FAST / Foundations Blueprint) | Subscription vending (AVM) |
| IaC document / deploy unit | CloudFormation template / stack | Terraform HCL / Infrastructure Manager deployment | Bicep / deployment stack |
| Plan | Change set | Infrastructure Manager preview | What-if (stack what-if) |
| Deployer identity | IAM role trusted by GitHub OIDC | Service account via Workload Identity Federation | User-assigned identity with federated credential |
| Ownership labels | Tags (`org:*`) | Labels (cost) + tags (IAM) | Tags |
| Preventive policy | SCP | Org Policy / IAM deny | Azure Policy deny |
| Resource perimeter | RCP | VPC Service Controls | Policy deny + private endpoints (partial) |
| Detective control | Config rule / Control Tower detective | SCC posture / Compliance Manager | Azure Policy audit / Defender for Cloud |
| Private network | VPC + Transit Gateway | Shared VPC + Network Connectivity Center | Hub-spoke VNet / Virtual WAN |
| Firewall | Network Firewall | Cloud NGFW / hierarchical firewall policies | Azure Firewall |
| Locked backup | AWS Backup vault, Vault Lock | Backup and DR vault + Bucket Lock exports | Locked immutable Backup vault + immutable Blob exports |
| Object storage / function / key-value table / queue | S3 / Lambda / DynamoDB / SQS | GCS / Cloud Run functions / Firestore / Pub/Sub | Blob / Functions / Cosmos DB / Service Bus |

### 22.3 Architecture

```
app/core/            neutral: request and design models, workflows, registries, topology, IPAM, tags
app/providers/base.py  CloudProvider ABC + ProviderRegistry
app/providers/aws/     today's AWS code, moved behind the ABCs (CloudFormation, IAM, Control Tower, AWS Backup)
app/providers/gcp/     Terraform for Infrastructure Manager, Workload Identity Federation, Org Policy/SCC, Backup and DR + Bucket Lock
app/providers/azure/   Bicep deployment stacks, federated identity, Azure Policy, locked immutable vault
```

A **`CloudProvider`** gives the core one object per concern. Each is an ABC with a per-provider implementation:

| Component | Responsibility | AWS today |
|---|---|---|
| `Vocabulary` | UI words (account/project/subscription, OU/folder/management group, …) | — |
| `RegionCatalog` | Regions, defaults, pairing hint | `Region` table |
| `BlockSet` | Curated block per neutral kind, plus the Tier-2 raw-type resolver and schema catalog | S3, Lambda, DynamoDB, SQS blocks; CloudFormation schema catalog |
| `AccessModel` | Access levels → permissions; the isolation condition (same project and environment) | `access.py`, `policies.py` |
| `IacDialect` | Document type, file names, serializer, native linter, naming and references | `Template`, naming, `NoAliasDumper`, cfn-lint |
| `LabelPolicy` | `org:*` keys → valid tag/label keys and values | `TagSet` |
| `IdentityTrust` | GitHub OIDC trust per environment | bootstrap stack, `trust_subject` |
| `WorkflowRenderer` | deploy.yml and the GitHub variables it reads | `DeployWorkflowRenderer`, `EnvironmentVariables` |
| `ProviderPort` (adapter by mode) | bootstrap, delete deploy unit, delete data store, adopt/import, backup service | `AwsPort`, `LocalAws` |
| `BackupStrategies` | Data-store detection and backup/restore per kind, lock check | `BackupTarget`s, `BackupPort` |
| `PlanReader` | Plan rows and stateful/permission predicates for releases | change set rows, `STATEFUL_TYPES` |
| `LandingZoneProvider` | Hierarchy rules and limits, guardrail builder, control catalog and pack mapping, vending, network, landing-zone bundle and executor | `landing_zone/cloudformation/*`, control catalog |

**What stays in the core, unchanged in behaviour:**
- Request validation rules, binders' intent (`access.grant`, `event.notify`), settings.
- Topology (single/DR/HA), cost centers, environments.
- Read-back, signed manifests, change requests, teardown orchestration (approvals, scheduling, checkpoints, records), release gates.
- The landing-zone questionnaire, OU-tree editor, selectors, pack resolver, industry templates (neutral answers), IPAM math.

### 22.4 Model changes

| Area | Change |
|---|---|
| Request | `ProjectRequest.provider` (default `aws` for existing data). Curated `type` becomes a neutral kind: `storage.bucket`, `compute.function`, `database.table`, `messaging.queue`. The AWS ids (`s3.bucket`, …) stay accepted as aliases, so stored `infra.json` files still read back. Tier-2 raw types are provider-qualified (`AWS::SNS::Topic`, `google_pubsub_topic`, `Microsoft.ServiceBus/namespaces`). Settings are per provider block (runtimes differ). |
| Registry | `regions` and `account_bindings` gain `provider`. Account ids widen to 64 characters, with a provider-specific validator (12 digits / project id / GUID). Each provider binds environments to its own isolation units. |
| Networks | `vpc_id` → `network_ref`, `security_group_ids` → `firewall_refs`, widened, plus `provider`. Validators come from the provider. |
| Landing zone | `landing_zone_designs.provider`. Answers split into neutral answers (environments, grouping, account model, optional OUs, packs, network intent) and provider answers (AWS: management email, Control Tower home region; Azure: billing scope; Google Cloud: billing account, org id). One landing zone per provider, each in its own repository (`landing-zone-<provider>-infra`). |
| Controls | **Neutral packs** (`foundation`, `data-protection`, `pci-cde`, …) with a provider mapping file each. AWS maps to Control Tower ids. Google Cloud maps to Org Policy constraints, IAM deny and SCC posture detectors. Azure maps to Azure Policy definitions and initiatives. Each mapped control keeps `behavior` (preventive/detective/proactive), so packs show honestly where a cloud only detects. |
| Teardown | `BackupStrategy` per (provider, data-store kind); recovery points keep a provider-neutral `ref`. Ids widen; `provider` on teardowns. Decommission archives the repository on every cloud; the platform never deletes isolation units (as on AWS today). |
| Releases | Change rows carry the provider. Risk rules use block metadata (`stateful`, `permission`) instead of AWS type lists. |
| API/UI | `GET /v1/providers` returns vocabulary, regions and catalog per provider. The project wizard and landing zone start with a provider choice; every AWS word in the UI comes from the vocabulary. The Tier-2 search becomes `GET /v1/catalog/{provider}/types`. |
| Policy | §1 technology policy becomes "AWS, Google Cloud, Azure, GitHub and open source". The platform's own control plane stays on AWS (§2.2a). |

### 22.5 What differs between clouds (the platform shows it, does not hide it)

| Topic | AWS | Google Cloud | Azure |
|---|---|---|---|
| Project isolation (ABAC) | Principal tag = resource tag | Tag-conditioned IAM bindings per value | Scope: one resource group per project and environment (ABAC only for storage data) |
| Resource perimeter | RCP | VPC Service Controls | None: Azure Policy deny + private endpoints |
| Managed landing zone | Control Tower | None: platform-run Terraform (FAST-style) | ALZ accelerator modules (platform-run) |
| Detective vs preventive packs | Both | Both (SCC Premium for postures) | Mostly detective (audit) |
| Drift | Detect | Detect per preview | Prevent with deny settings; what-if only predicts |
| Locked backup coverage | All supported stores | Vault for SQL/AlloyDB/Filestore/VM; GCS and Firestore via exports into locked buckets | Vault for Blob (same region); Cosmos via exports into immutable containers |
| Region pairs | Any two regions | Dual/multi-region service locations | Fixed pairs; some regions unpaired |
| IaC limits | 500 resources per stack | Terraform ≤ 1.5.7 in Infrastructure Manager | Stack-unsupported resource types |

### 22.6 Delivery

| Phase | Scope | Exit |
|---|---|---|
| **MC-1 Neutral core** | Provider ABCs and registry. Move the AWS code behind them. `provider` columns (default `aws`), widened ids, neutral UI wording from the vocabulary API. **No behaviour change.** | Every existing test passes unchanged, apart from renamed fields; 100% coverage. |
| **MC-2 Google Cloud projects** | Blocks (GCS, Cloud Run functions, Firestore, Pub/Sub) and binders; Terraform for Infrastructure Manager; Workload Identity Federation bootstrap; deploy workflow; plan rows from previews; backup strategies (Backup and DR vault, Bucket Lock exports); local stand-ins. | A Google Cloud project previews, provisions, reads back, changes and tears down locally. |
| **MC-3 Google Cloud landing zone** | Folders and projects, Org Policy/IAM deny/SCC pack mapping, project factory, Shared VPC + Network Connectivity Center, vault project with locked buckets. | Templates propose without problems; the generated Terraform validates. |
| **MC-4 Azure projects** | Blocks (Blob, Functions Flex, Cosmos DB, Service Bus) on Bicep deployment stacks; federated identity; what-if plan rows; locked immutable vault + Cosmos exports. | As MC-2. |
| **MC-5 Azure landing zone** | Management groups and subscription vending (AVM), Azure Policy pack mapping, hub-spoke/vWAN, backup subscription with Resource Guard. | As MC-3; generated Bicep builds. |

Each phase gets its own detailed design section and TDD, like §21.

### 22.7 Decisions

| # | Decision | Recommendation |
|---|---|---|
| MC1 | IaC per cloud | **Native per cloud:** CloudFormation, Terraform for Infrastructure Manager, Bicep deployment stacks. Each cloud keeps its managed state, plan and protection features, and the AWS work is kept. The alternative, OpenTofu everywhere, needs a state backend per cloud and loses change sets, stack policies and deployment-stack deny settings. |
| MC2 | Clouds per project | **One provider per project.** Cross-cloud connections are a later feature. |
| MC3 | Curated services | **Neutral kinds with one implementation per provider**; raw types stay provider-qualified; old AWS ids remain aliases. |
| MC4 | Landing zones | **One per provider**, sharing the questionnaire, OU-tree editor, neutral packs and industry templates. |
| MC5 | Unequal guarantees | **Accept and show them** (§22.5): isolation by resource group on Azure, VPC Service Controls on Google Cloud, detective-only controls marked as such. |
| MC6 | Backups | **The 60-day lock on every cloud** through its own immutable mechanism (§22.1 M8); deletion after 60 days only by super users. |
| MC7 | Platform credentials for Google Cloud and Azure | Control plane stays on AWS. **Google Cloud:** Workload Identity Federation trusting the platform's AWS role (supported). **Azure:** a federated credential if the platform can present an OIDC token, else a certificate in Secrets Manager. **Open question:** verify the AWS-to-Azure federation path in MC-4. |
| MC8 | Order | **MC-1 → MC-2 → MC-3 → MC-4 → MC-5**: Google Cloud before Azure, as asked |
| MC9 | Technology policy | Extend §1 to AWS, Google Cloud, Azure, GitHub and open source |

### 22.8 MC-1 in detail: the neutral core, with AWS as its first provider

Goal: the same behaviour as today, with every AWS-specific piece reached through a `CloudProvider`. It is delivered in five steps, each with its own TDD commits (red, then green) and the full suite at 100% coverage.

| Step | What moves or changes | Visible change |
|---|---|---|
| **MC-1a Provider registry and dimension** | `app/providers/base.py`: `CloudProvider` ABC, `Vocabulary`, `ProviderRegistry.default()` (AWS only). `provider` on `ProjectRequest` (default `aws`), projects, regions (key `(provider, id)`), account bindings (unique per environment, portfolio and provider; ids widened to 64 characters with a provider validator), networks, landing-zone designs and teardowns. The migration backfills `aws`. `GET /v1/providers` (id, name, vocabulary, default region pair). | New endpoint; `provider` in responses |
| **MC-1b Project synthesis** | Moves to `app/providers/aws/project/`: S3/Lambda/DynamoDB/SQS blocks, AWS binder bodies, naming, IAM policies and access actions, the CloudFormation `Template`, AWS lint rules and cfn-lint, the CloudFormation schema catalog, `template.yaml`/`config/{env}.json`/deploy-workflow renderers, and the GitHub environment variables. The core keeps the request model, validation, settings, block and binder base classes with neutral contracts, the synthesizer orchestration over an `IacDocument` ABC, and `infra.json`/README rendering. Neutral contracts:<ul><li>`cloudformation_types` → `provider_types`</li><li>`arn()` → `resource_ref()`</li><li>new block metadata `stateful` and `permission`</li></ul>Curated kinds are neutral (`storage.bucket`, `compute.function`, `database.table`, `messaging.queue`; connection `access.grant`), with the AWS ids (`s3.bucket`, …, `iam.access`) as **aliases**. Stored requests are not rewritten, so existing repositories still read back verified. | Catalog returns neutral kinds; the Tier-2 search moves to `GET /v1/catalog/{provider}/types` |
| **MC-1c Provisioning, teardown, releases** | `AwsPort` → `ProviderPort` (the AWS adapter keeps its methods). `ProvisioningContext.aws` → `cloud`. The worker picks the provider from the request. `BackupTarget`s → AWS `BackupStrategy`s; recovery points keep `recovery_point_ref`. Release risk uses block metadata instead of `STATEFUL_TYPES` and the IAM type checks. | `recovery_point_arn` → `recovery_point_ref` |
| **MC-1d Landing zone** | `LandingZoneProvider` ABC. The AWS implementation takes `landing_zone/cloudformation/*`, the control catalog and refresh, AWS limits (OU depth, Control Tower registration, SCP quota, 500 resources) and AWS-only design rules. The core keeps the questionnaire handlers, the design tree and edits, selectors, the pack resolver, templates, IPAM and validation/advice registries. | None |
| **MC-1e UI and networks** | UI words come from the provider's vocabulary (account/OU/CloudFormation/VPC/Control Tower). The provider picker stays hidden while only one provider is registered. Networks become `network_ref`, `subnet_refs`, `firewall_refs`, with AWS validators (`vpc-`, `subnet-`, `sg-`, 12-digit accounts). | Networks API and screen field names |

**Kept for later phases (on purpose):**
- Pack files and landing-zone answers stay in their current AWS shape.
- Splitting them into neutral definitions plus provider mappings happens in **MC-3**, when Google Cloud gives a second implementation to abstract from.
- This keeps stored designs and `design.json` readable.

#### MC-1 implementation notes

- **`CloudProvider`** (`app/providers/base.py`) gives the core:
  - its vocabulary and default regions;
  - a **project toolkit**: blocks, binders, IaC dialect, validator, linter, repository bundle, raw-type catalog and GitHub workflow variables;
  - a **teardown toolkit**: data-store inventory, what its backup service cannot keep, and the vault name;
  - a **landing-zone toolkit**: repository, renderer, limits as checks, and advice;
  - a **resource classifier** for release risk: stateful and permission rows;
  - **network id checks**.

  `ProviderRegistry.default()` registers AWS.
- **Adapters are per cloud.** `AwsPort` became `ProviderPort`. `AdapterFactory.clouds(settings)` returns one port per registered cloud, picked by the `<provider>_mode` setting. The worker uses the job's provider. Bootstrap outputs are `deployer_identity` and `execution_identity`; backups use `source_ref` and `ref`.
- **Release risk reads plan rows through the provider's classifier**, not through block metadata. A plan row is any resource type (IAM roles, permissions), not only a curated block.
- **The core is guarded by tests.** `app/synth`, `app/provisioning`, `app/teardown`, `app/releases` and `app/landing_zone` must contain no AWS ids, ARNs, condition keys, `AWS_*` variables or imports of `app.providers.aws`.
- **Still in AWS shape, on purpose (MC1-4, done in MC-3):**
  - the questionnaire's answers and its designer handlers (security and log accounts created by Control Tower, email plus-addressing);
  - the control catalog snapshot and the pack files (they list Control Tower control ids);
  - the diagram's labels;
  - the default regions on the request model.
- **UI wording comes from the vocabulary.** The vocabulary gained `cloud` and `firewall_group`. The UI reads it from `GET /v1/providers` through `VocabularyProvider`, falling back to AWS's words while loading. These places use it so far: the networks screen, the wizard's network step, the landing-zone page title, subtitle and controls step, and the OU tree. The remaining AWS wording (the Tier-2 search, the landing-zone question steps) moves with MC-2 and MC-3, when a second vocabulary shows each place to change.

#### MC-1 decisions

| # | Decision | Recommendation |
|---|---|---|
| MC1-1 | Move the AWS code into `app/providers/aws/`, rather than leaving it in place behind adapters | **Move.** The core then has no AWS imports, and a lint test enforces it. |
| MC1-2 | Neutral kind ids with AWS aliases; stored requests are never rewritten | **Yes** |
| MC1-3 | API and DB renames: networks refs, `recovery_point_ref`, widened ids, `provider` everywhere (default `aws`) | **Yes**, in one migration |
| MC1-4 | Split packs and landing-zone answers in MC-3, not MC-1 | **Yes** |
| MC1-5 | Hide the provider picker until a second provider exists | **Yes** |

### 22.9 MC-2 in detail: Google Cloud projects

Goal: a project on Google Cloud goes through the same flows as on AWS:
- wizard, preview, provisioning;
- read-back, Change infrastructure;
- releases with risk;
- teardown with locked backups, and restore.

Everything runs locally against stand-ins, like AWS today. The Google Cloud landing zone (folders, organization policies, the vault project) is MC-3. Until then, the vault project and environment projects are configured in the registry.

#### 22.9.1 How each concept maps

| Concept | Google Cloud | Notes |
|---|---|---|
| IaC document | **Terraform JSON** (`main.tf.json` + `variables.tf.json`), deployed by **Infrastructure Manager** | JSON is Terraform's native alternative syntax: deterministic to generate, no HCL serializer, read-back friendly. It stays within **Terraform 1.5.7**, the newest version Infrastructure Manager runs, so `import` blocks are available but `removed` blocks are not. Google provider **≥ 7.21** (needed for Direct VPC egress). |
| Deploy unit | One Infrastructure Manager deployment per environment project and region: `cloudinfra-{project}-{region}` | DR/HA: a primary and a secondary deployment, with variables `region_role` and `activation_state` (the CloudFormation conditions become `count` expressions). |
| Isolation unit | One Google Cloud **project per environment and portfolio** (account bindings with provider `gcp`) | The ids are project ids (6–30 characters). |
| Deployer identity | **Workload Identity Federation**: a pool and GitHub provider per environment project, with an attribute condition on repository id and environment. The deploy service account is impersonated by `principalSet://…/attribute.repository/{org}/{repo}` for that environment only. | `BootstrapOutputs.deployer_identity` = deploy service account; `execution_identity` = the Infrastructure Manager service account that applies the configuration. |
| Platform credentials | Workload Identity Federation **trusting the platform's AWS role** (keyless) | MC7 |
| Ownership tags | **Labels**: `org:project` → `org_project`, values lowercased, max 63 characters (a `LabelPolicy`) | Labels drive cost; IAM never relies on them. |
| Plan | `gcloud infra-manager previews create`, then export the plan JSON; rows from `resource_changes[].change.actions` (`create` → Add, `update` → Modify, `delete` → Remove, `delete`+`create` → replacement) | Feeds release risk (§8.4.2) |
| Raw resource types (Tier 2) | Any `google_*` resource of the provider schema; a committed snapshot of type names and required arguments, refreshed by a script (`terraform providers schema -json`) | Like the CloudFormation schema catalog |
| Contract | A Secret Manager secret `cloudinfra-{project}-contract` holding the same contract JSON | Application repositories read it like the SSM parameter on AWS |

#### 22.9.2 Curated services

| Neutral kind | Google Cloud resource | Defaults (like §6.4) |
|---|---|---|
| `storage.bucket` | `google_storage_bucket` | Uniform bucket-level access; public access prevention enforced; versioning; noncurrent versions expire after 30 days; Google-managed encryption (CMEK for `confidential`+ comes with MC-3's keys). **Single:** regional bucket. **DR/HA:** dual-region bucket in the chosen pair (custom placement); HA adds turbo replication. `force_destroy = false`, so a non-empty bucket is never deleted by a deploy. |
| `compute.function` | `google_cloudfunctions2_function` (Cloud Run functions) with its **own service account** | Settings: runtime (`python313`, `python312`, `nodejs22`, `nodejs20`, `java21`, `go125`), entry point, memory (128–32768 MiB), timeout (1–3600 s). Internal ingress. **Direct VPC egress** into the registered Shared VPC subnet when compute attaches to the network. The secondary region is standby: deployed, but without event triggers. |
| `database.table` | `google_firestore_database` (Native mode) | Point-in-time recovery on; delete protection in STAGE/PROD; `deletion_policy = ABANDON`, so removing it from the configuration keeps the data (retained). **Single:** regional location. **DR/HA:** the multi-region location of the pair's continent (`nam5`, `eur3`). Firestore has no partition or sort keys, so the AWS `partition_key`/`sort_key` settings are not offered. |
| `messaging.queue` | `google_pubsub_topic` + pull `google_pubsub_subscription` with a dead-letter topic | Message retention 7 days; exactly-once delivery |

**Connections:**
- **`access.grant`** binds the function's service account **on the exact resource**: the bucket, topic or subscription IAM member, or a Firestore role conditioned on the database name. Roles per level are read, write and readwrite (for example `roles/storage.objectViewer` and `roles/storage.objectUser`). No project-wide roles.
- **`event.notify`** (bucket → function) is an Eventarc trigger on `google.cloud.storage.object.v1.finalized` for that bucket, with a trigger service account.
  - **Eventarc cannot filter by object prefix.** The platform passes the prefix and suffix to the function as `CLOUDINFRA_EVENT_PREFIX`/`_SUFFIX`, and the preview says the function must filter.

**Retention when a service is removed (§21.8 C3):**
- Firestore is retained (ABANDON).
- A bucket is deleted only if it is empty: `force_destroy = false` makes the deploy fail rather than lose data. The change preview shows "deleted unless empty".
- Functions and Pub/Sub are deleted.

**Lint rules (the AWS ones, translated):**
- no primitive roles (`roles/owner`, `roles/editor`, `roles/viewer`);
- no project-level grants to function service accounts;
- no `allUsers`/`allAuthenticatedUsers`;
- public access prevention on every bucket;
- every function has its own service account.

#### 22.9.3 Repository and workflow

The repository contains `main.tf.json`, `variables.tf.json`, `config/{env}.tfvars` (input values), `infra.json`, a README, the deploy workflow and the signed manifest (§21.2). The deploy workflow:
1. `google-github-actions/auth` with the environment's Workload Identity provider and deploy service account.
2. `gcloud infra-manager previews create … --local-source=.`
3. `gcloud infra-manager deployments apply projects/$GCP_PROJECT_ID/locations/$REGION/deployments/cloudinfra-$PROJECT_NAME-$REGION --local-source=. --service-account=$IM_SERVICE_ACCOUNT --inputs-file=config/$ENVIRONMENT.tfvars` (each region's inputs, and the cost center from the repository variable `ORG_COST_CENTER`, are appended to that file first)

These run per region, with the secondary region in standby. STAGE and PROD keep the release executor (§8): it applies the reviewed preview.

GitHub environment variables: `GCP_PROJECT_ID`, `GCP_WORKLOAD_IDENTITY_PROVIDER`, `GCP_DEPLOY_SERVICE_ACCOUNT`, `IM_SERVICE_ACCOUNT`, `GCP_PRIMARY_REGION`/`GCP_SECONDARY_REGION`, and, when attached, `NETWORK`/`SUBNETWORK` per region.

#### 22.9.4 Networks

A registered Google Cloud network is checked like this:
- **`network_ref`:** a Shared VPC self-link, `projects/{host}/global/networks/{name}`.
- **`subnet_refs`:** `projects/{host}/regions/{region}/subnetworks/{name}`, at least one in the network's region.
- **`firewall_refs`:** network tags, lowercase, used by firewall rules.

Functions attach through Direct VPC egress with those tags.

#### 22.9.5 Teardown and restore

| Data store | Backup into the locked vault (§21.9.1) | Restore |
|---|---|---|
| Bucket | **Storage Transfer Service** copies the objects into `cloudinfra-teardown-{region}-{vault project}`, a bucket in the vault project with a **locked 60-day retention policy (Bucket Lock)**, under `{project}/{environment}/{id}/` | Transfer back into a new bucket with the original name, then an `import` block adopts it |
| Firestore database | **Managed export** into the same locked bucket | Managed import into a new database with the original id, then an `import` block adopts it |
| Cloud SQL / AlloyDB (Tier 2) | **Backup and DR vault** with enforced minimum retention of 60 days | Restore from the vault, then import |
| Anything else that holds data | Blocks the teardown (as on AWS) | — |

The Bucket Lock retention policy is irreversible. Objects cannot be deleted for 60 days, and the bucket (and, through the lien Bucket Lock places, the vault project) cannot be deleted while any object is retained. After 60 days, only the super-user group may delete, through a vault-project IAM deny policy that exempts it (MC-3 creates the vault project; MC-2 uses a configured `gcp_backup_project`).

**Not backed up:**
- Pub/Sub messages (transient);
- Cloud Logging (keep with log sinks);
- function code (rebuilt from the application repository).

Delete steps: delete the Infrastructure Manager deployment (secondary region first), then the retained Firestore database and empty buckets, then the bootstrap (Workload Identity provider and service accounts), then the GitHub environment.

#### 22.9.6 Platform changes

| Area | Change |
|---|---|
| `app/providers/gcp/` | `GcpProvider` with vocabulary (cloud "Google Cloud", project, folder, Terraform configuration, Infrastructure Manager deployment, organization policy, Shared VPC, network tag), default regions `us-east1`/`us-east4`, network checks, and the project, teardown and release toolkits. |
| Project toolkit | Blocks and binders above; `TerraformJsonDialect`; GCP lint rules; bundle (Terraform files, config, workflow, README); GCP workflow variables; provider-schema snapshot catalog with its refresh script. |
| Teardown toolkit | Inventory from the Terraform document (data stores by type, names resolved from variables); notes; vault bucket name. |
| Release classifier | Stateful types: buckets, Firestore, Cloud SQL, AlloyDB, Spanner, Bigtable, Pub/Sub subscriptions, KMS keys, secrets. Permission types: `google_*_iam_*`, service accounts, IAM deny and org policies. |
| Adapters | `LocalGcp` (`ProviderPort`: Workload Identity bootstrap records, deployment delete, data-store delete, import, backup) and a local backup stand-in that enforces Bucket Lock (refuses deletion before 60 days, and to anyone but the super-user group after). `gcp_mode = "local"`. |
| Registry and seed | GCP regions; example account bindings (project ids) per portfolio and environment; example Shared VPC networks; `gcp_backup_project` setting (per provider, like `backup_account_id`). |
| UI | **A cloud picker appears** in the wizard (first step) and on the networks screen now that two providers exist. Regions, catalog, settings fields and vocabulary follow the chosen cloud. The landing zone stays AWS until MC-3. |

#### 22.9.7 Delivery (TDD, 100% coverage, like MC-1)

| Step | Scope |
|---|---|
| **MC-2a** | `GcpProvider` registered: vocabulary, regions, network checks, label policy, seed data, `LocalGcp` adapter. |
| **MC-2b** | Terraform JSON dialect, curated blocks, binders, lint rules, raw-type snapshot. Golden tests per service and connection, DR/HA shapes, and a structural check of every generated document against the bundled provider schema (required arguments, known types). The real `terraform validate` runs in the generated repository's workflow. |
| **MC-2c** | Bundle, workflow and variables, Workload Identity bootstrap, provisioning, read-back and change requests end to end on GCP. |
| **MC-2d** | Release plan rows and classifier; teardown inventory, locked-bucket backups, Backup and DR vault stand-in, restore with import. |
| **MC-2e** | UI: cloud picker, GCP regions, catalog, settings and words; teardown and networks screens for GCP. |

**MC-2b implementation notes.**
- **Package.** The code is in `app/providers/gcp/project/`. The four curated blocks implement small capabilities: `GrantTarget`, `Workload` and `EventSource`. `ResourceBindingBinder` (alias `iam.access`) and `EventarcBinder` wire them together. `RawResourceResolver` handles Tier-2 types and `TerraformJsonDialect` writes the document.
- **Multi-region documents.** In DR/HA, resources that belong to the whole project are created only by the primary deployment (`count = local.is_primary ? 1 : 0`). These are service accounts, the dual-region bucket, multi-region Firestore, topics, bindings and the contract. References to them are indexed (`[0]`). Functions and their invoker binding are deployed in every region.
- **Pub/Sub dead letters.** A queue also grants the Pub/Sub service agent the two bindings that dead-lettering needs: publish to the dead-letter topic and subscribe to the subscription.
- **Request rules.** Google Cloud adds four rules:
  - both regions on one continent (when storage spans them);
  - dual-region buckets only in US/EU/Asia, and multi-region Firestore only in US/EU;
  - one event trigger per function;
  - the id `contract` is reserved.

  `RequestValidator.rules` is now public so a provider can extend the defaults.
- **Preview notes.** `ProjectToolkit` gains an optional `PreviewAdvisor`, and `notes` is added to the preview response. Google Cloud uses it to say which functions must filter event prefixes or suffixes themselves.
- **Lint.** Lint flags:
  - primitive roles;
  - public members;
  - buckets without enforced public access prevention;
  - workload project roles without a condition;
  - arguments that don't match the bundled provider schema (nested blocks and `dynamic` included).
- **Repository bundle.** The bundle contains:
  - `main.tf.json` and `variables.tf.json`;
  - `config/<env>.tfvars`;
  - a workflow that runs `terraform validate` on 1.5.7, signs in through Workload Identity Federation, then previews and applies one Infrastructure Manager deployment per region. Each region's inputs are appended to the environment's tfvars file, because gcloud takes either an inputs file or input values, not both.
- **Bootstrap outputs.** `BootstrapOutputs` gains `federation`, the workload identity provider.
- **Schema snapshot.** `python -m app.providers.gcp.project.refresh [version]` regenerates the snapshot.

**MC-2c implementation notes.**
- **What already worked.** After MC-1, provisioning, the sealed manifest, read-back and Change infrastructure needed no Google Cloud specific code. The worker picks the job's cloud adapter; the runner takes that provider's toolkit and workflow variables.
- **Labels.** Each provider now has a `TagPolicy`. AWS keeps the tags as they are; Google Cloud's `LabelPolicy` turns them into labels (`org:cost-center` → `org_cost_center`, values lowercased, with characters labels can't hold replaced, at most 63 characters). The preview shows the labels.
- **Labels in the document.** Ownership values known when the code is generated (portfolio, product, data classification, resilience) are written into `local.labels` directly. The cost center can change in the registry, so it is a variable without a default, passed from `ORG_COST_CENTER` at deploy.
- **Deployment names.** Deployments are `cloudinfra-{project}-{region}`, as designed, and function code is `bootstrap/{project}.zip`.
- **Removal wording.** Blocks can say what removal does (`removal_effect()`). The change summary carries it as `removal` next to `retained`, and the pull request and the UI's change preview use it. A Google Cloud bucket says "deleted only if empty"; it still needs confirming, like any removal that can delete data.

**MC-2d implementation notes.**
- **Release rows.** `ResourceClassifier` gains `rows(document)`, the (address, type) rows a first plan of a document has, so the local pipeline simulator no longer reads CloudFormation directly. On Google Cloud:
  - `TerraformResourceClassifier` marks data types stateful (buckets, Firestore, Cloud SQL, AlloyDB, Spanner, Bigtable, BigQuery, Filestore, subscriptions, KMS, secrets) and `*_iam_*`, service accounts, deny and organization policies as permission changes;
  - `TerraformPlanReader` turns `terraform show -json` of a preview's plan into rows: create → Add, update → Modify, delete → Remove, delete-and-create (either order) → a replacement. Data sources and no-ops are skipped.
- **Teardown inventory.** `TerraformInventory` reads the configuration the current request generates:
  - each service's main resource, its name resolved for the environment (`${var.…}` and the bucket's `substr(sha1(var.project_id), 0, 8)`);
  - buckets, Firestore, Cloud SQL and AlloyDB are backed up. A primary-only resource (dual-region bucket, multi-region Firestore) is backed up once, in the primary region;
  - Spanner, Bigtable, BigQuery and Filestore block the teardown, and so does a name the configuration does not give.
- **Vault.** Local backups now have a per-cloud `BackupStyle`. On Google Cloud, objects and Firestore exports go to the Bucket-Locked bucket `cloudinfra-teardown-{region}-{vault project}` (refs `gs://…`), and Cloud SQL and AlloyDB to the Backup and DR vault `projects/{vault project}/locations/{region}/backupVaults/cloudinfra-teardown`. After 60 days only `group:cloudinfra-backup-super-users` may delete.
- **Per-provider teardown settings.** `TeardownToolkit` now names the deploy units a teardown deletes (`cloudinfra-{project}-{region}` and the bootstrap on Google Cloud), the vault with the backup account in its name, and the message when no vault is configured. The backup account resolves per provider (`Settings.backup_accounts()`); the landing zone's Backup account applies only to AWS until MC-3.
- **Buckets on deletion.** Firestore (`ABANDON`) is deleted by the teardown after its deployment, like retained stores on AWS. Buckets are deleted with the deployment; the real adapter empties the backed-up buckets first, because `force_destroy = false` makes deleting a non-empty bucket fail.

**MC-2e implementation notes.**
- **Cloud picker.** It is the first field of the wizard's first step (Ownership), not a separate step. It lists the clouds the platform reports, AWS first, and is locked when changing a project. Choosing another cloud takes its default region pair and clears the services, connections and network choices, which belong to the old cloud.
- **Wizard data.** The wizard loads every cloud's regions and each cloud's catalog once; each step shows the chosen cloud's. The type search, network options, words and preview follow the chosen cloud. A service not in the chosen cloud's catalog is a raw type and gets the properties editor.
- **Preview.** The preview shows the cloud's main file (`document_file` in `GET /v1/providers`: `template.yaml`, `main.tf.json`), the targets in the cloud's own words ("Target projects") and the notes of §22.9.2. The policy-check message no longer names AWS-only controls.
- **Admin, projects and teardown screens.**
  - Regions and Networks in Admin have the cloud picker too. Networks are listed and added per cloud (`GET /v1/admin/networks?provider=`), and a new one starts in the cloud's default region.
  - The projects list has a Cloud column.
  - The teardown request speaks the project's cloud: "project" and "Infrastructure Manager deployments" on Google Cloud.
- **API changes.** Network options take `provider` (`GET /v1/networks/options?portfolio_id=&provider=`, AWS by default). The client's `searchCloudFormation` became `searchTypes(provider, text)`, and `catalog`, `regions` and `setRegionEnabled` take the cloud.



#### 22.9.8 Decisions

| # | Decision | Recommendation |
|---|---|---|
| MC2-1 | Document format | **Terraform JSON** within Terraform 1.5.7 (Infrastructure Manager), google provider ≥ 7.21 |
| MC2-2 | Deploy units | **One Infrastructure Manager deployment per environment project and region**; DR/HA with dual-region buckets and multi-region Firestore |
| MC2-3 | Isolation | **Exact-resource IAM bindings to each function's own service account**; no project-wide roles. Tag-conditioned deny policies come with the landing zone (MC-3). |
| MC2-4 | Bucket events by prefix | Eventarc can't filter by prefix: **pass prefix and suffix to the function and say so in the preview** |
| MC2-5 | Data kept on removal | **Firestore retained (ABANDON); buckets deleted only when empty** (`force_destroy = false`) |
| MC2-6 | Teardown backups | **Storage Transfer and Firestore export into a Bucket-Locked bucket (60 days) in the vault project**; Backup and DR vault for Cloud SQL/AlloyDB; anything else blocks |
| MC2-7 | Tier-2 types | **Committed provider-schema snapshot**, refreshed by a script |
| MC2-8 | Network attachment | **Direct VPC egress** with the registered subnet and network tags |
| MC2-9 | Contract | **Secret Manager** secret with the same JSON |
| MC2-10 | Cloud picker | **Shown in the project wizard and networks screen now**; the landing zone stays AWS-only until MC-3 |

### 22.10 MC-3 in detail: the Google Cloud landing zone

**Status: approved (MC3-1…MC3-10 as recommended); implementation in progress.**

**Goal.** An admin designs a Google Cloud landing zone with the same questionnaire, tree editor, industry templates and control packs as on AWS (§20). The platform then generates Terraform for Infrastructure Manager, gets it approved by a second admin, applies it, and fills the registries:
- environment projects become account bindings;
- Shared VPC subnets become networks;
- the vault project replaces the `gcp_backup_project` setting.

Everything runs locally against stand-ins, like AWS today.

This phase also finishes the split that MC-1 deferred (MC1-4): landing-zone answers and control packs become neutral definitions with one mapping per cloud.

#### 22.10.1 Research findings

| # | Finding | Consequence |
|---|---|---|
| G1 | Google Cloud has **no managed landing-zone service** like Control Tower. Google's references are the Enterprise Foundations Blueprint and Cloud Foundation Fabric (FAST): Terraform that an organization admin runs in stages from a **seed project**. | The platform generates its own Terraform JSON, applied by Infrastructure Manager from a seed project (MC3-1, MC3-2). FAST is the reference for structure and roles, not a dependency. |
| G2 | Hierarchy: organization → **folders** (nested up to 10 levels, at most 300 folders per parent) → **projects**. Project ids are 6–30 characters and **globally unique**. | Folders take the place of OUs and projects take the place of accounts. The limits become Google Cloud checks, and project ids get an organization hash (MC3-7). |
| G3 | **Organization Policy** constraints (managed constraints such as `iam.disableServiceAccountKeyCreation`, `storage.publicAccessPrevention`, `gcp.resourceLocations`, plus custom CEL constraints) attach to the organization, folders or projects. They are **inherited by every descendant**. There is **one policy per constraint per resource**; list constraints merge with the parent's policy unless the policy resets inheritance. Dry-run is available. | Preventive controls go on the top-most targeted folder, as on AWS. Two packs that set the same constraint on one folder are merged into one policy, and the platform warns when they conflict. |
| G4 | **IAM deny policies** attach to the organization, folders or projects. They deny permissions to principals, with exception principals and tag conditions. | Used for the vault (only super users may delete after the lock) and to stop identities moving between environments (MC3-4). |
| G5 | **VPC Service Controls** perimeters stop data leaving a set of projects through Google APIs. A project can be in at most one regular perimeter. This is Google Cloud's equivalent of the AWS RCP data perimeter (§22.2). | **One perimeter per environment** holds that environment's projects: R2 on Google Cloud. It is applied in dry-run first (MC3-4). |
| G6 | **Security Command Center.** Security Health Analytics detectors find misconfigurations (open firewall, public bucket, no MFA, keys not rotated). **Security Posture** deploys detectors and organization-policy constraints together, to the organization, a folder or a project. Postures need SCC **Premium or Enterprise**. | Detective pack controls map to posture detectors and are **deployed only with Premium/Enterprise**. On Standard, the design shows them as not deployed (MC3-5). Detectors deployed on a folder apply to everything below it, so detective controls are inherited too, unlike AWS (F11). |
| G7 | Google Cloud has **no proactive controls** (the CloudFormation-hooks equivalent). Custom Org Policy constraints check resources when they are created or updated, so they are preventive. | Proactive controls in a pack have no Google Cloud mapping. The packs view says so (MC5 "show, don't hide"). |
| G8 | Networking: a **Shared VPC host project** owns the VPC, and service projects use its subnets. **Network Connectivity Center** joins VPCs as spokes. Its **star topology** lets edge spokes reach the center only, never each other. **Cloud NAT** is regional per VPC. **Private Service Connect** publishes one service from one VPC into another, on one port. Hierarchical **firewall policies** attach to folders. | Each environment gets its own Shared VPC host. The hub (center) is shared services and on-premises connectivity, and the environments are edges, so no route exists between environments. Declared cross-environment flows are Private Service Connect services (MC3-3). |
| G9 | **Bucket Lock** (an irreversible retention policy) and **Backup and DR vaults** (enforced minimum retention) hold teardown backups (§22.9.5). | The landing zone creates the vault project, its locked buckets per region, a Backup and DR vault per region, and the IAM deny policy (MC3-6). |
| G10 | **Tags** (Resource Manager tag keys and values) are inherited down folders and projects, and IAM and Org Policy conditions can test them. Labels cannot. | An `environment` tag key with one value per environment, bound to each environment folder, lets policies tell environments apart. |
| G11 | Infrastructure Manager runs Terraform ≤ 1.5.7 and needs a service account with the roles the configuration uses. Here those are organization-level: folder admin, Org Policy admin, project creator, billing user, Shared VPC admin, security admin, Access Context Manager admin. | The one-time **seed bootstrap** grants them (MC3-2). The platform never holds a person's organization-admin rights. |

#### 22.10.2 How each concept maps

| Concept (§20) | AWS | Google Cloud |
|---|---|---|
| Root | Management account, Organizations, Control Tower | Organization node, plus a seed project `{org}-lz-seed` with the Infrastructure Manager service account |
| Hierarchy node | OU | Folder |
| Isolation unit | Account (Account Factory) | Project, with billing account, enabled APIs, environment tag binding and labels |
| Security (R3) | Security OU: Log Archive, Audit, Security Tooling | Security folder: `{org}-logging` (organization log sink into a log bucket with locked retention), `{org}-security` (SCC, plus Security Tooling if chosen) |
| Infrastructure | Network, Shared Services, Identity, Backup, Monitoring, CI/CD accounts | Infrastructure folder: `{org}-net-hub` (NCC hub, shared services VPC, hybrid connectivity), `{org}-shared-services`, `{org}-vault` (MC3-6), `{org}-monitoring`, `{org}-cicd`. Identity is Cloud Identity, so there is no Identity project. |
| Environment OU (R1) | OU per environment | Folder per environment, with an `environment` tag binding, a Shared VPC host project `{org}-net-{env}`, and workload projects as service projects |
| No access between environments (R2) | RCP + SCP + transit-gateway route tables | **VPC Service Controls perimeter per environment** + **IAM deny on each environment folder** (no impersonating service accounts from other environments) + **no route** (separate VPCs, NCC star topology) |
| Policies on nodes only (R4) | SCPs on OUs | Org policies, IAM deny and firewall policies on folders and the organization, never on projects (the validator enforces it) |
| Policy Staging (R5) | Policy Staging OU | Policy Staging folder. Org policies are applied there in dry-run, then promoted. |
| Preventive control | SCP / RCP / declarative policy | Org Policy constraint (managed or custom CEL), IAM deny |
| Detective control | Config rule / Security Hub control | SCC posture detector (Premium/Enterprise) |
| Proactive control | CloudFormation hook | None (G7) |
| Hub and spoke | Transit Gateway with route table per environment | NCC star topology: hub = center, environments = edges |
| Egress | Central egress VPC + Network Firewall | Cloud NAT in each environment's host VPC, plus egress rules in the environment folder's firewall policy. Central egress is not offered (advice). |
| Inspection | AWS Network Firewall | Cloud NGFW Enterprise firewall endpoints (optional, paid), on the hub and on each flow's consumer side |
| Cross-environment flow | Route through inspection + stateful rule | Private Service Connect: the producer environment publishes the service on one port, and the consumer environment gets an endpoint and a firewall rule, with an owner and expiry |
| Addressing | VPC IPAM pools | No managed IPAM. The platform's `IpamPlanner` (already neutral) splits the top-level CIDR into one range per environment per region, and each host VPC's subnet takes its range. |
| On-premises | VPN / Direct Connect | HA VPN / Cloud Interconnect on the hub, as an NCC hybrid spoke |
| Sandbox | Sandbox OU, budget, expiry | Sandbox folder: projects with a `google_billing_budget`, an `expires_on` label, and no Shared VPC (Cloud NAT egress only) |
| Locked backup vault | Backup account vault, Vault Lock | Vault project: locked buckets + Backup and DR vaults + IAM deny (MC3-6) |
| Deploy units | Stacks `lz-foundation` … `lz-bootstrap` | Infrastructure Manager deployments in the seed project, in order (§22.10.5) |
| Repository | `landing-zone-infra` | `landing-zone-gcp-infra` |

#### 22.10.3 Neutral answers and provider answers (MC1-4)

`LandingZoneAnswers` keeps every neutral question:
- organization name, home and governed regions, template, environments, grouping;
- unit model (one project per portfolio, product or environment), compliance scopes, security tooling, log retention;
- shared units, network intent, sandbox, optional nodes, controls profile, packs and their parameters.

The cloud-specific answers move into `provider_answers`, validated by the provider's own model:

| Provider | Provider answers | Notes |
|---|---|---|
| AWS | `management_email` | Account emails use plus addressing on it, as today |
| Google Cloud | `organization_id` (digits), `billing_account` (`XXXXXX-XXXXXX-XXXXXX`), `domain` (for `iam.allowedPolicyMemberDomains`), `groups`: organization admins, network admins, security admins, billing admins, backup super users. Each group defaults to `gcp-<role>@<domain>`. `scc_tier`: `standard` / **`premium`** / `enterprise`. | The platform does not create Cloud Identity groups: they must exist (MC3-8) |

**Compatibility:**
- Stored AWS designs keep `management_email` at the top level. A before-validator moves it into `provider_answers`, so old designs and `design.json` still load and read back verified.
- Network intent stays neutral: `on_premises` becomes `none` / `vpn` / `dedicated`, with `direct_connect` accepted as an alias of `dedicated`.
- `egress: central` is an AWS-only choice. On Google Cloud it is accepted and advised against: "Google Cloud uses Cloud NAT in each environment's VPC".

**Naming.** The designer's account naming becomes a per-provider **`UnitNamer`**.
- **AWS:** `{org}-{suffix}` plus the email.
- **Google Cloud:** `{org}-{suffix}-{h4}`, where `h4` is 4 hex characters of a hash of `organization_id`, because project ids are global. The 30-character limit is a check.

`AccountPlan.email` becomes optional (AWS only), and `OuNode.created_by_control_tower` becomes `created_by_service` (the provider's landing-zone service; on Google Cloud nothing is pre-created).

#### 22.10.4 Control packs: one definition, one mapping per cloud

A pack file keeps the neutral part: id, version, name, description, selectors, `optional`, `order`. The controls move into **mapping files** under `catalog/mappings/<provider>/<pack>.yaml`. Each mapping lists that cloud's control ids and maps the pack's parameters (for example, `AllowedRegions` → `gcp.resourceLocations` values `in:<region>-locations`).

- **AWS:** the mapping holds today's Control Tower global ids, so AWS designs resolve exactly as before (the regression tests stay).
- **Google Cloud:** a **`GcpControlSnapshot`** (`catalog/gcp_controls.yaml`) lists each control's id, name, behavior, implementation (`ORG_POLICY`, `CUSTOM_CONSTRAINT`, `IAM_DENY` or `SCC_DETECTOR`) and frameworks (SCC compliance mappings: CIS Google Cloud Foundations, PCI DSS, NIST 800-53, ISO 27001). A refresh script (read-only, needs credentials) confirms the detector names and frameworks. Until it runs, the frameworks show as "intended alignment (unverified)", as with T2.

Google Cloud mapping (v1), pack by pack:

| Pack | Preventive (Org Policy / IAM deny) | Detective (SCC detectors) |
|---|---|---|
| `foundation` | `iam.disableServiceAccountKeyCreation`, `iam.disableServiceAccountKeyUpload`, `iam.allowedPolicyMemberDomains` (the domain), `iam.automaticIamGrantsForDefaultServiceAccounts`, `storage.publicAccessPrevention`, `compute.skipDefaultNetworkCreation`, `compute.vmExternalIpAccess` (deny all) | `MFA_NOT_ENFORCED`, `PUBLIC_BUCKET_ACL`, `OPEN_SSH_PORT`, `OPEN_RDP_PORT`, `ADMIN_SERVICE_ACCOUNT`, `USER_MANAGED_SERVICE_ACCOUNT_KEY` |
| `data-protection` | `storage.uniformBucketLevelAccess`, `sql.restrictPublicIp`, `sql.restrictAuthorizedNetworks`, custom constraint `custom.cloudinfraSqlRequireSsl` | `PUBLIC_SQL_INSTANCE`, `SQL_NO_ROOT_PASSWORD`, `BUCKET_POLICY_ONLY_DISABLED` |
| `network-hardening` | `compute.requireOsLogin`, `compute.disableSerialPortAccess`, `compute.requireShieldedVm`, `compute.restrictVpcPeering`, `compute.restrictSharedVpcHostProjects` (the environment's host only) | `OPEN_FIREWALL`, `FLOW_LOGS_DISABLED`, `DEFAULT_NETWORK`, `LEGACY_NETWORK` |
| `logging-integrity` | IAM deny: no `logging.sinks.delete` or `logging.buckets.delete` outside the security admins group | `AUDIT_LOGGING_DISABLED`, `BUCKET_LOGGING_DISABLED`, `LOG_NOT_EXPORTED` |
| `key-management` | `gcp.restrictNonCmekServices` (storage, Cloud SQL, BigQuery), `gcp.restrictCmekCryptoKeyProjects` (the environment's key project) | `KMS_KEY_NOT_ROTATED`, `KMS_PUBLIC_KEY` |
| `production-resilience` | IAM deny on production-tier folders: no `resourcemanager.projects.delete` and no deleting data stores outside the release executor's service account | `SQL_BACKUP_DISABLED`, `OBJECT_VERSIONING_DISABLED` |
| `data-residency` | `gcp.resourceLocations` from `AllowedRegions` | — |
| `strict-residency` | `gcp.resourceLocations` without multi-regions; custom constraint denying dual-region buckets | — (and the advice "breaks DR/HA dual-region storage", as T6) |
| `pci-cde` | All of the above on the PCI folders, plus `compute.restrictLoadBalancerCreationForTypes` (internal only) | The PCI DSS posture's detectors |

Proactive controls in a pack have no Google Cloud mapping and show as "no equivalent on Google Cloud".

**Resolver.** `PackResolver` takes the provider's **`InheritanceRule`**:
- AWS: preventive controls are inherited, detective and proactive ones are not (F11).
- Google Cloud: all are inherited (G3, G6), so every control goes on the top-most targeted folder.

The Google Cloud bundle merges two packs' policies for the same constraint on one folder, and the `DesignAdvisor` warns when the merged values conflict. For example, two `gcp.resourceLocations` lists are intersected, and an empty intersection is a problem.

#### 22.10.5 Repository and deployments

`landing-zone-gcp-infra` holds `design.json`, the diagrams, `docs/controls.md`, `scripts/bootstrap-seed.sh`, a workflow, and one directory per Infrastructure Manager deployment (`main.tf.json` + `variables.tf.json`, Terraform JSON as in MC-2, google provider ≥ 7.21). The deployments are applied in order from the seed project:

| Order | Deployment | Main resources |
|---|---|---|
| 0 | *Seed bootstrap (one-time, by an organization admin running `scripts/bootstrap-seed.sh`)* | Seed project, Infrastructure Manager service account and its organization roles, Workload Identity Federation for the repository (MC3-2) |
| 1 | `lz-foundation` | Tag key `environment` and its values; organization-level org policies (domain restriction, no default networks); custom constraints; organization log sink into `{org}-logging`; Essential Contacts |
| 2 | `lz-structure` | Folders (nested), tag bindings, folder org policies (merged per constraint), IAM deny policies, hierarchical firewall policies |
| 3 | `lz-projects` | Project factory: `google_project` (billing, folder, labels, `auto_create_network = false`), `google_project_service`, tag bindings, sandbox budgets |
| 4 | `lz-network` | Hub VPC and NCC hub (star topology); one Shared VPC host project per environment (VPC, subnets per region from the IPAM plan, Cloud NAT, private Google access, DNS); NCC VPC spokes (environments as edges, hub as center); service-project attachments; Private Service Connect flows; optional NGFW endpoints; HA VPN / Interconnect hybrid spoke |
| 5 | `lz-security` | Access Context Manager policy; one VPC Service Controls perimeter per environment, dry-run then enforced (MC3-4); SCC posture per targeted folder (Premium/Enterprise only) |
| 6 | `lz-vault` | `{org}-vault` project: per region, a Bucket-Locked bucket `cloudinfra-teardown-{region}-{vault project}` (60-day locked retention, uniform access, public access prevention) and a Backup and DR vault (60-day enforced minimum retention); IAM deny on the project (no deletes except the backup super-user group) |

**Workflow.** The workflow signs in through the seed's Workload Identity Federation and runs `gcloud infra-manager previews create` for every deployment. After approval it applies them in order. The approval workflow (§20.7) is unchanged.

**Read-back.** It uses the signed manifest, as for the AWS landing zone (§21).

**Checks.** Lint uses the bundled provider-schema rule (MC-2b) and the MC-2b lint rules (no primitive roles, no public members, public access prevention). The real `terraform validate` runs in the repository's workflow.

#### 22.10.6 Checks, advice and outputs

| Kind | Google Cloud |
|---|---|
| Checks (block submit) | Folder depth ≤ 10; ≤ 300 folders per parent; project ids 6–30 characters and unique; policies only on folders and the organization (R4); one regular VPC Service Controls perimeter per project; merged list constraints not empty; existing R1–R3 rules (neutral) |
| Advice (shown, never blocking) | Detective controls not deployed on SCC Standard; proactive controls with no equivalent; `egress: central` not used; strict residency vs DR/HA dual-region storage; project-creation quota (an organization starts with a small quota of projects; request more before applying large designs) |
| Executor outputs | Project ids per environment and portfolio/product → **account bindings** (`provider = gcp`); each environment host's subnetwork per region → **networks** (`network_ref` self-link, `subnet_refs`, `firewall_refs` = network tags); the vault project → the **teardown vault** for Google Cloud |

The backup-account resolver for Google Cloud reads the applied landing zone's vault project. `gcp_backup_project` remains an explicit override, as `backup_account_id` is on AWS.

#### 22.10.7 Platform changes

| Area | Change |
|---|---|
| Answers | Neutral `LandingZoneAnswers` + `provider_answers` (§22.10.3), with the AWS migration validator. `on_premises: dedicated`. |
| Designer | `UnitNamer` and the security/infrastructure handlers' unit lists come from the provider (`LandingZoneProvider.units()`). `created_by_service`. |
| Catalog | Neutral pack files; `catalog/mappings/aws/*.yaml` (today's ids) and `catalog/mappings/gcp/*.yaml`; `GcpControlSnapshot` and its refresh script; `InheritanceRule` per provider. Templates keep neutral answers and gain `regions: {aws: […], gcp: […]}` for the templates that fix regions (public sector: us-east1/us-west1; EU sovereignty: europe-west3/europe-west1). |
| Provider | `GcpProvider.landing_zone()`: repository `landing-zone-gcp-infra`, `GcpLandingZoneBundle` (the deployments above), checks, advice, inheritance rule, unit namer. |
| Workflow | One landing zone per provider (MC4): `latest_applied(provider)`, versions per provider, `provider` on every landing-zone endpoint (default `aws`). Executors are per provider (`AdapterFactory.landing_zone_executors(settings)`), with `LocalGcpLandingZone` returning project ids, networks and the vault project. |
| API | `GET …/templates?provider=`, `GET …/control-packs?provider=` (controls per cloud, with "no equivalent" and "needs SCC Premium" marked), and `provider` on propose, create and read-back. |
| UI | The Start step gets the cloud picker. Question steps show provider answers (AWS: management email; Google Cloud: organization id, billing account, domain, groups, SCC tier) and read their words from the vocabulary. The Controls step shows each cloud's controls and their gaps. Review and diagram say "folder" and "project". |

#### 22.10.8 Delivery (TDD, 100% coverage)

| Step | Scope | Exit |
|---|---|---|
| **MC-3a Neutral split** | Answers and provider answers (AWS migration), pack mappings with the AWS ids moved, `InheritanceRule`, `UnitNamer`, landing zones per provider in the workflow and API | Every AWS landing-zone test passes unchanged apart from renamed fields; stored designs read back verified |
| **MC-3b Google Cloud design** | Provider answers, namer, `GcpControlSnapshot` and mappings for every pack, checks and advice | Every industry template proposes on Google Cloud with no problems |
| **MC-3c Google Cloud bundle** | The seven deployments, `design.json`, diagrams, `controls.md`, seed script, workflow; lint with the provider schema | Every template's deployments pass the lint and schema rules; golden tests per deployment |
| **MC-3d Apply and registries** | `LocalGcpLandingZone` executor; account bindings, networks and the vault project filled; teardown vault resolved from the landing zone | Approve → applied → a Google Cloud project provisions into the vended projects and tears down into the landing zone's vault, locally |
| **MC-3e UI** | Cloud picker on the landing-zone page, provider questions, per-cloud controls and templates, folder/project wording | 100% frontend coverage |

**MC-3a implementation notes.**
- **Answers.**
  - `LandingZoneAnswers.provider_answers` holds what only one cloud asks. The landing-zone service validates it with the cloud's `LandingZoneToolkit.answers` model before proposing or saving, and refuses invalid answers with 422 ("Invalid provider answers: management_email.").
  - A before-validator moves a stored design's top-level `management_email` into `provider_answers`, and `direct_connect` reads as `dedicated`. Design responses return answers in the new shape.
- **Naming.** `UnitNamer` (`app/landing_zone/naming.py`) names the units. The designer is built per cloud (`LandingZoneToolkit.designer()`), and the design carries its namer so the tree editor names the accounts it adds the same way. AWS's `AwsAccountNamer` keeps names plus plus-addressed emails. `AccountPlan.email` is optional, and `OuNode.created_by_control_tower` became `created_by_service` (API and UI too).
- **Packs.** Pack files are neutral, and a pack that still lists controls is refused at load time.
  - **Where the mappings live:** each cloud's mappings and snapshot are in its provider package: `app/providers/aws/landing_zone/catalog/controls.yaml` and `mappings/<pack>.yaml`. This differs from §22.10.4, which put the mappings under the core `catalog/mappings/<provider>/`; keeping them in the provider package keeps the core free of cloud data.
  - `ProviderControls` brings a cloud's snapshot, mappings, `InheritanceRule` (`PreventiveInherited` for AWS, `AllInherited` for Google Cloud) and `ControlPrerequisite`s. AWS's CloudFormation-hooks prerequisite is now `HooksPrerequisite` in the AWS package.
  - `GET …/control-packs` and `…/templates` take `provider`. Template previews use the cloud's default regions and placeholder provider answers.
- **Advice.** The core advice is the packs' warnings for the cloud's controls (`DesignAdvisor.for_cloud`). The strict-residency warning names S3, so it moved to the AWS advice.
- **Diagrams.** The root box's detail comes from the cloud (`LandingZoneToolkit.root_detail`). AWS: "Management / payer account", "Control Tower {home region}".
- **One landing zone per cloud.**
  - Versions are unique per provider (migration `a7d3c5e19b42`), and `latest_applied` and `next_version` take the provider.
  - The design list (`?provider=`) and read-back (`?provider=`, AWS by default) are per cloud.
  - The backup-account fallback reads only the AWS landing zone's Backup account.
- **The core holds no cloud words.** A test keeps "Control Tower", "CloudFormation" and `created_by_control_tower` out of `app/landing_zone`. The one place that still names `management_email` is the migration of stored AWS answers.

**MC-3b implementation notes.**
- **Provider answers.** `GcpLandingZoneAnswers` (`app/providers/gcp/landing_zone/answers.py`) checks:
  - the organization id (digits) and the billing account (`XXXXXX-XXXXXX-XXXXXX`, uppercase letters and digits);
  - the domain, and each named group's address;
  - the SCC tier (Premium by default).

  A group not named defaults to `gcp-<role>@<domain>`.
- **Project ids (refines MC3-7).** `"{org}-{suffix}"` is kept to 25 characters, plus 4 hex characters of a hash of the organization id **and the full name**. Ids always fit 30 characters, and two long names that share their first 25 characters still get different ids. The plain `{org}-{suffix}-{h4}` exceeded 30 characters for the healthcare template's platform projects (for example `payments-core-validation`). `ProjectIds` still checks 6–30 characters and that no id repeats.
- **Units.** A `UnitCatalog` per cloud names the Security and Infrastructure units, the network host per environment and the nodes the cloud's service creates.
  - AWS keeps Log Archive, Audit and the five shared accounts.
  - Google Cloud has `logging`, `security` (+ `security-tooling`) and `net-hub`, `shared-services`, `vault`, `monitoring` (no Identity project), plus a `net-{environment}` host project in each workload environment folder (not in Sandbox). Nothing is created by a service.
  - The compliance child folders (e.g. PCI-PROD) get their host projects with the network deployment in MC-3c.
- **Controls.** The Google Cloud snapshot (`app/providers/gcp/landing_zone/catalog/controls.yaml`) holds 44 controls: Org Policy constraints, two custom constraints, two IAM deny policies and Security Command Center detectors. Every pack maps to some of them, and none is proactive. Every control goes on the top-most targeted folder (`AllInherited`).
- **Checks and advice.**
  - Checks: folder depth ≤ 10, ≤ 300 folders per parent, project ids.
  - Advice: detective controls need Premium/Enterprise; no central egress; strict residency vs dual-region storage; a project-quota reminder above 25 projects.
- **Templates** carry `regions: {aws, gcp}` where they fix regions (public sector: us-east1/us-west1; EU sovereignty: europe-west3/europe-west1). Every template proposes on Google Cloud with no problems.
- **Bundle so far.** `landing-zone-gcp-infra` renders `design.json` (shared with AWS through `app/landing_zone/document.py`), the diagrams (root: "Organization {id}", "Seed project {org}-lz-seed") and `docs/controls.md`. The deployments come with MC-3c.
- **Applying.** Landing-zone executors are per cloud (`AdapterFactory.landing_zone_executors`, picked by each cloud's mode). Google Cloud has none until MC-3d, so approving a Google Cloud design is refused before anything is committed: "Applying a Google Cloud landing zone is not available yet."

**MC-3c implementation notes.**
- **Deployments.** They live in `app/providers/gcp/landing_zone/deployments/`, one class per deployment with a shared `DeploymentContext` (design, provider answers, resolved controls, address plan).
  - **Inputs:** each deployment is Terraform JSON with organization-level provider settings (`billing_project` = the seed project, `user_project_override`). It declares the same four inputs, which `config/landing-zone.tfvars` fills from the provider answers: organization id, billing account, seed project, home region.
  - **Cross-deployment references:** Infrastructure Manager deployments don't share state, so later deployments find what earlier ones made through data sources:
    - folders by display name under their parent (`google_active_folder`, chained);
    - the environment tag and its values by short name;
    - project numbers by project id.
- **What each deployment holds:**
  - **lz-foundation:** the `environment` tag key and one value per environment folder; the custom constraints that resolved packs use; the security admins as essential contact.
  - **lz-structure:**
    - folders with `deletion_protection` and environment tag bindings;
    - one `google_org_policy_policy` per (folder, constraint). `ConstraintRules` sets list constraints: locations from `AllowedRegions`, the organization's directory customer id for member domains, `under:` the folder for CMEK keys and Shared VPC hosts, internal load balancers only;
    - IAM deny policies with the provider answers' groups as exceptions;
    - a firewall policy on each environment folder that denies SSH and RDP from the internet.
  - **lz-projects:** every enabled unit as a project (billing, `deletion_policy = PREVENT`, no default network, labels) with the APIs its role needs; budgets for sandbox projects.
  - **lz-network:** the hub VPC and an NCC hub with the `STAR` preset (hub spoke `center`, environments `edge`); one Shared VPC per environment with subnets from the IPAM plan, flow logs, Private Google Access and Cloud NAT per region; service-project attachments; declared flows as Private Service Connect endpoints; the HA VPN gateway when the link is VPN; NGFW endpoints per region when inspection is on.
  - **lz-security:** the organization audit sink into a locked log bucket in the logging project; the access policy and one dry-run perimeter per environment; one combined posture per folder with detective controls (Q2), only on SCC Premium/Enterprise.
  - **lz-vault:** per region a Bucket-Locked bucket and a Backup and DR vault (60 days); the deny policy that only backup super users escape; output `vault_project`.
- **Flows.** A flow's endpoint is created only once its `flow_N_service_attachment` input is set (`count`). The producer side and the attachment URI are the destination team's; the README lists this.
- **Seed, workflow and README.** `scripts/bootstrap-seed.sh <owner>/<repo>` creates:
  - the seed project and its APIs;
  - `lz-infra-manager` with its organization roles and billing user;
  - a Workload Identity pool and provider whose attribute condition is the repository.

  `.github/workflows/apply.yml` validates every deployment with Terraform 1.5.7, then previews and applies them in order. The README lists the deployments and what is left to a person: enforcing the dry-run perimeters, flow attachments, VPN tunnels, the Interconnect order.
- **Compliance folders** (e.g. PCI-PROD) now get their own host project, like the other environments.
- **New check:** a vault bucket name must fit 63 characters.
- **Verified with real Terraform.** Every deployment of the default design (with a VPN link and a flow) and of the financial-services template passes `terraform validate` with Terraform 1.5.7 and google provider 8.5.0. So does MC-2b's project configuration (DR with network attachment, and every curated service and connection). The tests check every template against the bundled schema.
- **Deferred:** the IAM deny against impersonation from other environments (MC3-4) waits for Q1. With the wrong principal set it would also block the Workload Identity tokens the deploy workflows use. Until then, environments are kept apart by separate VPCs with no route between them, the dry-run perimeters, and IAM bindings that stay inside each environment.

#### 22.10.9 Decisions and open questions

| # | Decision | Recommendation |
|---|---|---|
| MC3-1 | Landing-zone IaC | **Generated Terraform JSON on Infrastructure Manager**, like MC-2. FAST and the Foundations Blueprint are the reference for structure and roles, but are not vendored: their modules need newer Terraform than 1.5.7 in places, and generated JSON stays deterministic and readable back. |
| MC3-2 | Bootstrap | **A one-time seed bootstrap run by an organization admin** (`scripts/bootstrap-seed.sh`: seed project, Infrastructure Manager service account and its organization roles, Workload Identity Federation for the repository), like the AWS management account. After it, every change goes through the platform. |
| MC3-3 | Networking | **One Shared VPC host per environment; NCC star topology** with the hub as center and environments as edges, so no route exists between environments. **Cross-environment flows as Private Service Connect services** on one port, with owner and expiry. NGFW Enterprise inspection is optional. |
| MC3-4 | Environment isolation (R2) | **A VPC Service Controls perimeter per environment** (dry-run on first apply, enforced after the dry-run shows no violations), **IAM deny on environment folders** against impersonation from other environments, and separate VPCs |
| MC3-5 | Detective controls | **SCC posture detectors, only with Premium or Enterprise**. On Standard, packs show them as not deployed, and the design advises it. |
| MC3-6 | Vault | **`{org}-vault` project in the Infrastructure folder**, with Bucket-Locked buckets and Backup and DR vaults per governed region, and an IAM deny that only the backup super-user group escapes (after the lock). It replaces `gcp_backup_project`, which stays as an override. |
| MC3-7 | Project ids | **`{org}-{suffix}-{h4}`** (hash of the organization id), checked against 6–30 characters |
| MC3-8 | Groups | **The admin names existing Cloud Identity groups**; the platform checks their format and never creates groups (that needs Workspace or Cloud Identity admin rights) |
| MC3-9 | Packs | **Neutral pack files plus mapping files per provider**; AWS behavior unchanged |
| MC3-10 | Repository | **`landing-zone-gcp-infra`**; AWS keeps `landing-zone-infra` |

| # | Open question | Plan |
|---|---|---|
| Q1 | The exact IAM deny principal set for "principals outside this environment" (G4) | Verify on a real organization during MC-3c. Until then, deny for `principalSet://goog/public:all`, with the environment's deploy and workload service accounts and the admin groups as exceptions. |
| Q2 | Whether a folder can hold more than one posture deployment | Generate **one combined posture per targeted folder**, which works either way |
| Q3 | SCC tier and Security Posture availability in the customer's organization | Asked in the provider answers (`scc_tier`); refresh script confirms detector names |
| Q4 | NCC star topology for VPC spokes in all chosen regions | Check in the refresh script; fall back to separate VPC peerings to the hub (no transitive routing) if unavailable |
