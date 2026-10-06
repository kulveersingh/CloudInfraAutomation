import { vi } from "vitest";
import type {
  AccountInfo, CatalogControlInfo, CatalogEntry, ControlPackCatalog, CostCenterSettings, IndustryTemplate, TemplateSummary, EnvironmentInfo, JobStatus, LandingZoneDesign, LandingZoneDesignDetail,
  CloudProviderInfo, LandingZoneProposal, LandingZoneReadBack, NetworkInfo, ProjectChange, Teardown, TeardownPreview, ProjectChangePreview, ProjectReadBack, ProjectRequest, NetworkOption, OuInfo, PipelineStage, PlatformApiPort, Portfolio, PreviewResult,
  ProjectSummary, RegionInfo, Release,
} from "../api/types";
import { LandingZoneDraft } from "../landingZone/LandingZoneDraft";

export const PORTFOLIOS: Portfolio[] = [
  {
    id: "pf-payments", name: "Payments", cost_center: { value: "CC-4400", source: "portfolio" },
    products: [
      { id: "pr-invoicing", name: "Invoicing", kind: "product", classification_ceiling: "confidential",
        cost_center: { value: "CC-4410", source: "product" } },
      { id: "pl-payments-core", name: "Payments Core", kind: "platform", classification_ceiling: "restricted",
        cost_center: { value: "CC-4400", source: "portfolio" } },
    ],
  },
  {
    id: "pf-retail", name: "Retail", cost_center: { value: "CC-5100", source: "portfolio" },
    products: [
      { id: "pr-storefront", name: "Storefront", kind: "product", classification_ceiling: "internal",
        cost_center: { value: "CC-5120", source: "product" } },
    ],
  },
];

export const ENVIRONMENTS: EnvironmentInfo[] = [
  { id: "dev", name: "DEV", tier: "nonprod", position: 2, requires_approval: false },
  { id: "prod", name: "PROD", tier: "prod", position: 5, requires_approval: true },
];

export const REGIONS: RegionInfo[] = [
  { provider: "aws", id: "us-east-1", name: "US East (N. Virginia)", enabled: true },
  { provider: "aws", id: "us-east-2", name: "US East (Ohio)", enabled: true },
  { provider: "aws", id: "ap-southeast-2", name: "Asia Pacific (Sydney)", enabled: false },
];

export const GCP_REGIONS: RegionInfo[] = [
  { provider: "gcp", id: "europe-west1", name: "Belgium", enabled: true },
  { provider: "gcp", id: "us-east1", name: "South Carolina", enabled: true },
  { provider: "gcp", id: "us-east4", name: "Northern Virginia", enabled: true },
  { provider: "gcp", id: "asia-southeast1", name: "Singapore", enabled: false },
];

export const AZURE_REGIONS: RegionInfo[] = [
  { provider: "azure", id: "eastus2", name: "East US 2", enabled: true },
  { provider: "azure", id: "centralus", name: "Central US", enabled: true },
  { provider: "azure", id: "westus2", name: "West US 2", enabled: true },
  { provider: "azure", id: "westcentralus", name: "West Central US", enabled: true },
  { provider: "azure", id: "swedencentral", name: "Sweden Central", enabled: false },
];

export const AZURE_CATALOG: CatalogEntry[] = [
  { type: "storage.bucket", name: "Storage account", category: "Storage", multi_region: "replicated", settings: [] },
  { type: "compute.function", name: "Function app (Flex Consumption)", category: "Compute", multi_region: "replicated",
    settings: [] },
];

export const GCP_CATALOG: CatalogEntry[] = [
  { type: "storage.bucket", name: "Cloud Storage bucket", category: "Storage", multi_region: "replicated", settings: [] },
  { type: "compute.function", name: "Cloud Run function", category: "Compute", multi_region: "replicated", settings: [] },
];

const KEY_RULE = "1 to 255 characters of letters, digits and _ . -";

export const CATALOG: CatalogEntry[] = [
  { type: "lambda.function", name: "Lambda function", category: "Compute", multi_region: "replicated", settings: [
    { kind: "choice", name: "runtime", label: "Runtime", default: "python3.13", choices: ["python3.13", "java21"] },
    { kind: "text", name: "handler", label: "Handler", default: "lambda_function.lambda_handler",
      pattern: "^[A-Za-z0-9_.:/$-]{1,128}$", rule: "1 to 128 characters of letters, digits and _ . : / $ -", optional: false },
    { kind: "integer", name: "memory_mb", label: "Memory", default: 256, minimum: 128, maximum: 10240, unit: "MB" },
  ] },
  { type: "s3.bucket", name: "S3 bucket", category: "Storage", multi_region: "replicated", settings: [] },
  { type: "dynamodb.table", name: "DynamoDB table", category: "Database", multi_region: "global", settings: [
    { kind: "text", name: "sort_key", label: "Sort key", default: null, pattern: "^[A-Za-z0-9_.-]{1,255}$", rule: KEY_RULE,
      optional: true },
  ] },
];

export const COST_CENTERS: CostCenterSettings = {
  default: "CC-1000",
  pattern: "^CC-[0-9]{4}$",
  portfolios: [{
    id: "pf-payments", name: "Payments", cost_center: "CC-4400",
    effective: { value: "CC-4400", source: "portfolio" },
    products: [{ id: "pr-invoicing", name: "Invoicing", cost_center: null,
                 effective: { value: "CC-4400", source: "portfolio" } }],
  }],
};

export const PREVIEW: PreviewResult = {
  files: { "template.yaml": "Resources:\n  UploadsBucket: {}\n", "README.md": "# demo" },
  tags: { "org:project": "demo-app", "org:cost-center": "CC-4410" },
  targets: { prod: { account_id: "555555555555", regions: ["us-east-1", "us-east-2"], networks: {
    "us-east-1": { network_id: "net-prod-use1", network_ref: "vpc-0aaa1111bbbb22223", subnet_refs: ["subnet-0a", "subnet-0b"] },
  } } },
  lint: [],
  notes: [],
};

export const GCP_PREVIEW: PreviewResult = {
  files: { "main.tf.json": "{\"resource\": {\"google_storage_bucket\": {}}}\n", "README.md": "# demo" },
  tags: { org_project: "demo-app", org_cost_center: "cc-4410" },
  targets: { dev: { account_id: "cloudinfra-payments-dev", regions: ["us-east1"], networks: {} } },
  lint: [],
  notes: ["uploads → processor: Eventarc cannot filter by object prefix, so processor must check CLOUDINFRA_EVENT_PREFIX."],
};

export const PROJECTS: ProjectSummary[] = [
  { name: "invoice-ingest", portfolio_id: "pf-payments", product_id: "pr-invoicing", resilience_mode: "dr",
    status: "active", revision: 1, open_change: null, environments: ["dev", "prod"], provider: "aws" },
];

export const PROVIDERS: CloudProviderInfo[] = [{
  id: "aws", name: "Amazon Web Services", default_regions: { primary: "us-east-1", secondary: "us-east-2" },
  document_file: "template.yaml", region_pairs: {}, landing_zone: true,
  vocabulary: { cloud: "AWS", isolation_unit: "account", hierarchy_node: "OU", iac_document: "CloudFormation template",
    deploy_unit: "stack", preventive_policy: "SCP", private_network: "VPC", firewall_group: "security group",
    landing_zone_service: "Control Tower", control_catalog: "Control Tower controls" },
}, {
  id: "gcp", name: "Google Cloud", default_regions: { primary: "us-east1", secondary: "us-east4" },
  document_file: "main.tf.json", region_pairs: {}, landing_zone: true,
  vocabulary: { cloud: "Google Cloud", isolation_unit: "project", hierarchy_node: "folder",
    iac_document: "Terraform configuration", deploy_unit: "Infrastructure Manager deployment",
    preventive_policy: "organization policy", private_network: "Shared VPC", firewall_group: "network tag",
    landing_zone_service: "Google Cloud Setup", control_catalog: "Security Command Center postures" },
}, {
  id: "azure", name: "Azure", default_regions: { primary: "eastus2", secondary: "centralus" },
  document_file: "main.json", landing_zone: false,
  region_pairs: { eastus2: "centralus", centralus: "eastus2", westus2: "westcentralus" },
  vocabulary: { cloud: "Azure", isolation_unit: "subscription", hierarchy_node: "management group",
    iac_document: "ARM template", deploy_unit: "deployment stack", preventive_policy: "Azure Policy",
    private_network: "VNet", firewall_group: "network security group", landing_zone_service: "Azure Landing Zones",
    control_catalog: "Azure Policy initiatives" },
}];

export const GCP_PROVIDER = PROVIDERS[1];

/** Another cloud's words, to show the UI takes them from the provider. */
export const OTHER_CLOUD: CloudProviderInfo[] = [{
  ...PROVIDERS[0], vocabulary: { cloud: "Azure", isolation_unit: "subscription", hierarchy_node: "management group",
    iac_document: "Bicep file", deploy_unit: "deployment stack", preventive_policy: "Azure Policy", private_network: "VNet",
    firewall_group: "network security group", landing_zone_service: "Azure Landing Zones",
    control_catalog: "Azure Policy initiatives" },
}];

export const TEARDOWN_PREVIEW: TeardownPreview = {
  scope: "environment", backup_account: "999999999999", retention_days: 60, blockers: [],
  environments: [{
    environment: "dev", account_id: "222222222222", regions: ["us-east-1"], approver_role: "reviewer",
    stacks: ["invoice-ingest", "cloudinfra-bootstrap-invoice-ingest"],
    data_stores: [{ service_id: "uploads", resource_type: "AWS::S3::Bucket", physical_name: "invoice-ingest--uploads",
      region: "us-east-1", retained: true }, { service_id: "ledger", resource_type: "AWS::RDS::DBCluster",
      physical_name: "ledger-db", region: "us-east-1", retained: false }],
    not_backed_up: ["processor (lambda.function): rebuilt from the template and the application repository",
      "CloudWatch Logs: not supported by AWS Backup"],
  }],
};

export function teardown(overrides: Partial<Teardown> = {}): Teardown {
  return {
    id: "td-1", project_name: "invoice-ingest", scope: "environment", state: "in_progress", requested_by: "jordan",
    base_revision: 1, base_commit: "abcdef1234567890abcdef1234567890abcdef12", created_at: "2026-10-04T10:00:00",
    environments: [{ environment: "dev", state: "pending_approval", approver_role: "reviewer", decided_by: null,
      decision_comment: null, revision: null, error: null, job_id: null, recovery_points: [] }],
    restore: null, ...overrides,
  };
}

export const PROJECT_REQUEST: ProjectRequest = {
  project_name: "invoice-ingest",
  ownership: { portfolio_id: "pf-payments", product_id: "pr-invoicing", data_classification: "confidential" },
  resilience: { mode: "single", primary_region: "us-east-1", secondary_region: null },
  environments: ["dev"],
  resources: [{ id: "uploads", type: "s3.bucket" },
    { id: "processor", type: "lambda.function", config: { memory_mb: 512 } }],
  connections: [{ kind: "event.notify", source: "uploads", target: "processor", prefix: "incoming/" }],
  network: { attach_compute: true, selections: {} },
};

export const PROJECT_READ_BACK: ProjectReadBack = {
  verified: true, commit_sha: "abcdef1234567890abcdef1234567890abcdef12", findings: [],
  design: { kind: "project", id: "invoice-ingest", revision: 1 }, request: PROJECT_REQUEST,
};

export const CHANGE_PREVIEW: ProjectChangePreview = {
  files: { "template.yaml": "Resources: {}\n" }, tags: {}, targets: {}, lint: [],
  summary: { added_services: ["bucket"], removed_services: [], changed_services: ["processor"], added_environments: [],
    changed_files: ["infra.json", "template.yaml"] },
};

export function projectChange(overrides: Partial<ProjectChange> = {}): ProjectChange {
  return {
    id: "chg-1", project_name: "invoice-ingest", revision: 2, state: "queued",
    base_commit: "abcdef1234567890abcdef1234567890abcdef12", branch: "cloudinfra/change-2", pull_request: null,
    summary: CHANGE_PREVIEW.summary, created_by: "sam", merge_commit: null, job_id: "job-1",
    created_at: "2026-10-04T10:00:00", ...overrides,
  };
}

export function release(overrides: Partial<Release> = {}): Release {
  return {
    id: "rel-1", project_name: "invoice-ingest", environment: "stage", commit_sha: "4f78c64a1b2c",
    artifact_digest: "sha256:aaaa", risk: "medium", state: "awaiting_approval", requested_by: "jordan",
    changes: [
      { action: "Add", logical_id: "ArchiveBucket", resource_type: "AWS::S3::Bucket", replacement: false, risk: "low" },
      { action: "Modify", logical_id: "ProcessorRole", resource_type: "AWS::IAM::Role", replacement: false,
        risk: "medium" },
    ],
    evidence: { tests_passed: true, critical_vulnerabilities: 0, high_vulnerabilities: 0, signed: true },
    gate_findings: [], execution_detail: null, created_at: "2026-10-03T20:00:00", decisions: [],
    ...overrides,
  };
}

export function pipeline(stageRelease: Release | null = release()): PipelineStage[] {
  return [
    { environment: "dev", name: "DEV", requires_approval: false, release: release({ id: "rel-0", environment: "dev",
      state: "deployed" }) },
    { environment: "stage", name: "QA/STAGE", requires_approval: true, release: stageRelease },
    { environment: "prod", name: "PROD", requires_approval: true, release: null },
  ];
}

export function network(overrides: Partial<NetworkInfo> = {}): NetworkInfo {
  return {
    id: "net-prod-use1", provider: "aws", name: "Org shared VPC", account_id: "555555555555", region: "us-east-1",
    network_ref: "vpc-0aaa1111bbbb22223", cidr: "10.5.0.0/16", subnet_refs: ["subnet-0a1111", "subnet-0b2222"],
    firewall_refs: ["sg-0c3333"], is_default: true, ...overrides,
  };
}

export const GCP_NETWORK: NetworkInfo = {
  id: "net-cloudinfra-payments-dev-us-east1", provider: "gcp", name: "Shared VPC", account_id: "cloudinfra-payments-dev",
  region: "us-east1", network_ref: "projects/cloudinfra-net-host/global/networks/shared-vpc", cidr: "10.128.0.0/16",
  subnet_refs: ["projects/cloudinfra-net-host/regions/us-east1/subnetworks/payments-dev"],
  firewall_refs: ["cloudinfra-payments-dev"], is_default: true,
};

export const NETWORK_OPTIONS: NetworkOption[] = [
  { environment: "dev", region: "us-east-1", account_id: "222222222222",
    networks: [network({ id: "net-dev-use1", account_id: "222222222222", cidr: "10.3.0.0/16" })],
    default_network_id: "net-dev-use1" },
  { environment: "prod", region: "us-east-1", account_id: "555555555555",
    networks: [network(), network({ id: "net-prod-alt", name: "Isolated VPC", is_default: false, cidr: "10.9.0.0/16" })],
    default_network_id: "net-prod-use1" },
  { environment: "prod", region: "us-east-2", account_id: "555555555555", networks: [], default_network_id: null },
];

export function job(state: string, steps: JobStatus["steps"] = [], error: string | null = null): JobStatus {
  return { id: "job-1", project_name: "demo-app", state, error, steps };
}

const ou = (key: string, name: string, kind: string, extra: Partial<OuInfo> = {}): OuInfo => ({
  key, name, kind, environment: null, tier: null, created_by_service: false, custom: false, domain: null,
  allowed_edits: [], blocked_edits: {}, accounts: [], controls: [], children: [], ...extra,
});

const ROOT_USER = { id: "5kvme4m5d2b4d7if2fs5yg2ui", name: "Disallow actions as a root user", behavior: "PREVENTIVE" as const,
  severity: "HIGH" };
const ROOT_MFA = { id: "24izmu4k16gv9tvd7sexnyrfy", name: "Detect whether MFA for the root user is enabled",
  behavior: "DETECTIVE" as const, severity: "HIGH" };

const account = (name: string, extra: Partial<AccountInfo> = {}): AccountInfo => ({
  name, enabled: true, added: false, allowed_edits: ["move", "disable"], ...extra,
});
const fixed = (name: string) => account(name, { allowed_edits: [] });
const CONTAINER: OuInfo["allowed_edits"] = ["add_child", "add_account"];

export const OU_TREE: OuInfo[] = [
  ou("security", "Security", "security", { created_by_service: true,
    accounts: [fixed("acme-log-archive"), fixed("acme-audit")] }),
  ou("infrastructure", "Infrastructure", "infrastructure", { domain: "infrastructure", allowed_edits: CONTAINER,
    accounts: [fixed("acme-network")] }),
  ou("prod", "PROD", "environment", { environment: "prod", tier: "prod", domain: "prod", allowed_edits: CONTAINER,
    controls: [{ ...ROOT_USER, packs: ["foundation"] }, { ...ROOT_MFA, packs: ["foundation"] }],
    accounts: [account("acme-payments-prod")], children: [
      ou("custom_payments", "Payments", "custom", { custom: true, domain: "prod",
        allowed_edits: [...CONTAINER, "rename", "move", "remove"] }),
      ou("custom_cards", "Cards", "custom", { custom: true, domain: "prod", allowed_edits: [...CONTAINER, "rename", "move"],
        controls: [{ ...ROOT_MFA, packs: ["foundation"] }],
        blocked_edits: { remove: "Move its accounts and child OUs to another OU first." },
        accounts: [account("acme-cards-prod", { added: true, allowed_edits: ["move", "disable", "remove"] })] }),
    ] }),
  ou("parent_nonprod", "NonProd", "parent", { children: [ou("dev", "DEV", "environment", { environment: "dev",
    domain: "dev", allowed_edits: CONTAINER,
    accounts: [account("acme-retail-dev", { enabled: false, allowed_edits: ["move", "enable"] })] })] }),
];

const DIAGRAM = { svg: '<svg xmlns="http://www.w3.org/2000/svg"><text>PROD OU</text></svg>', mermaid: "flowchart TD" };

export const PROPOSAL: LandingZoneProposal = {
  ous: OU_TREE, problems: [], warnings: [], diagram: DIAGRAM,
  files: { "stacks/lz-structure.yaml": "Resources: {}\n", "README.md": "# acme landing zone\n" },
};

export function landingZoneDesign(overrides: Partial<LandingZoneDesign> = {}): LandingZoneDesign {
  return {
    id: "lz-1", version: 1, status: "pending_approval", organization_name: "acme",
    answers: LandingZoneDraft.initial().withOrganization("acme", "aws@acme.example").toAnswers(), edits: [],
    created_by: "alex", submitted_by: "alex", decided_by: null, decision_comment: null, repository: null,
    commit_sha: null, accounts: {}, created_at: "2026-10-04T08:00:00", ...overrides,
  };
}

export function landingZoneDetail(overrides: Partial<LandingZoneDesign> = {}): LandingZoneDesignDetail {
  return { ...landingZoneDesign(overrides), ous: OU_TREE, problems: [], warnings: [], diagram: DIAGRAM };
}

const catalogControl = (control: Omit<CatalogControlInfo, "implementation" | "frameworks">,
  implementation: string): CatalogControlInfo => ({
  ...control, implementation, frameworks: [] });

export const PACK_CATALOG: ControlPackCatalog = {
  mappings_refreshed: null,
  profiles: { baseline: ["foundation"], recommended: ["foundation", "data-protection"],
    regulated: ["foundation", "data-protection", "pci-cde"] },
  packs: [
    { id: "foundation", version: 1, name: "Foundation", description: "Root user and MFA basics.", selectors: ["workloads"],
      optional: false, controls: [catalogControl(ROOT_USER, "SCP"), catalogControl(ROOT_MFA, "CONFIG_RULE")] },
    { id: "data-protection", version: 1, name: "Data protection", description: "Encryption.", selectors: ["workloads"],
      optional: false, controls: [catalogControl(ROOT_MFA, "CONFIG_RULE")] },
    { id: "pci-cde", version: 1, name: "PCI cardholder data environment", description: "PCI OUs.",
      selectors: ["compliance:PCI"], optional: true, controls: [{ ...catalogControl(ROOT_USER, "SCP"),
        frameworks: ["PCI-DSS-v4.0"] }] },
  ],
};

/** Google Cloud's implementation of the packs: Org Policy constraints and SCC detectors, nothing proactive. */
export const GCP_PACK_CATALOG: ControlPackCatalog = {
  ...PACK_CATALOG,
  packs: [{ id: "foundation", version: 1, name: "Foundation", description: "Root user and MFA basics.", selectors: ["workloads"],
    optional: false, controls: [
      { id: "constraints/iam.disableServiceAccountKeyCreation", name: "Disable service account key creation",
        behavior: "PREVENTIVE", severity: "HIGH", implementation: "ORG_POLICY", frameworks: [] },
      { id: "MFA_NOT_ENFORCED", name: "2-step verification not enforced", behavior: "DETECTIVE", severity: "HIGH",
        implementation: "SCC_DETECTOR", frameworks: [] }] }],
};

const SAAS_SUMMARY: TemplateSummary = {
  id: "saas", version: 1, name: "SaaS & technology", industry: "Software and technology companies",
  description: "Account-per-tenant SaaS.", frameworks: ["SSAE-18-SOC-2-Oct-2023", "CIS-v8.0"], frameworks_verified: false,
  environments: ["Sandbox", "DEV", "STAGE", "PROD"], packs: ["foundation", "data-protection"], ou_count: 9,
  control_counts: { PREVENTIVE: 12, DETECTIVE: 30, PROACTIVE: 8 }, enabled_controls: 130,
};

export const TEMPLATES: TemplateSummary[] = [
  { ...SAAS_SUMMARY, id: "financial-services", name: "Financial services", industry: "Banking, payments and insurance",
    frameworks: ["PCI-DSS-v4.0"], frameworks_verified: true, packs: ["foundation", "data-protection", "pci-cde"] },
  SAAS_SUMMARY,
];

export const SAAS_TEMPLATE: IndustryTemplate = {
  ...SAAS_SUMMARY,
  answers: { environment_ids: ["sandbox", "dev", "stage", "prod"], account_model: "product",
    control_packs: ["foundation", "data-protection"] },
  edits: [{ op: "add_ou", parent: "prod", name: "Tenants" }],
};

export const READ_BACK: LandingZoneReadBack = {
  verified: true, commit_sha: "abcdef1234567890abcdef1234567890abcdef12", findings: [],
  design: { kind: "landing-zone", id: "lz-3", revision: 3 },
  request: LandingZoneDraft.initial().withOrganization("acme", "aws@acme.example").with({ log_retention_days: 730 })
    .withEdit({ op: "add_ou", parent: "prod", name: "Tenants" }).toRequest(),
};

export function fakeApi(overrides: Partial<PlatformApiPort> = {}): PlatformApiPort {
  return {
    orgRegistry: vi.fn().mockResolvedValue(PORTFOLIOS),
    environments: vi.fn().mockResolvedValue(ENVIRONMENTS),
    regions: vi.fn().mockImplementation(async (provider?: string) => [...REGIONS, ...GCP_REGIONS, ...AZURE_REGIONS].filter(
      (region) => provider === undefined || region.provider === provider)),
    setRegionEnabled: vi.fn().mockImplementation(async (provider: string, id: string, enabled: boolean) => ({
      ...[...REGIONS, ...GCP_REGIONS, ...AZURE_REGIONS].find((region) => region.provider === provider && region.id === id)!, enabled })),
    catalog: vi.fn().mockImplementation(async (provider: string) => (
      { gcp: GCP_CATALOG, azure: AZURE_CATALOG }[provider] ?? CATALOG)),
    searchTypes: vi.fn().mockImplementation(async (provider: string) => (provider === "gcp"
      ? [{ type: "google_pubsub_schema", service: "pubsub", required: ["name"] }]
      : [{ type: "AWS::SNS::Topic", service: "SNS", required: [] },
        { type: "AWS::SNS::Subscription", service: "SNS", required: ["Protocol", "TopicArn"] }])),
    costCenters: vi.fn().mockResolvedValue(COST_CENTERS),
    updateCostCenters: vi.fn().mockResolvedValue(COST_CENTERS),
    preview: vi.fn().mockResolvedValue(PREVIEW),
    createProject: vi.fn().mockResolvedValue({ job_id: "job-1" }),
    projects: vi.fn().mockResolvedValue(PROJECTS),
    job: vi.fn().mockResolvedValue(job("succeeded")),
    projectReadBack: vi.fn().mockResolvedValue(PROJECT_READ_BACK),
    previewTeardown: vi.fn().mockResolvedValue(TEARDOWN_PREVIEW),
    requestTeardown: vi.fn().mockResolvedValue(teardown()),
    teardowns: vi.fn().mockResolvedValue([teardown()]),
    providers: vi.fn().mockResolvedValue(PROVIDERS),
    decideTeardownEnvironment: vi.fn().mockResolvedValue(teardown()),
    restoreTeardown: vi.fn().mockResolvedValue(teardown()),
    previewChange: vi.fn().mockResolvedValue(CHANGE_PREVIEW),
    createChange: vi.fn().mockResolvedValue(projectChange()),
    projectChange: vi.fn().mockResolvedValue(projectChange({ state: "open",
      pull_request: { number: 1, url: "https://github.com/acme-platform/invoice-ingest-infra/pull/1" } })),
    mergeChange: vi.fn().mockResolvedValue(projectChange({ state: "merged", merge_commit: "f".repeat(40) })),
    closeChange: vi.fn().mockResolvedValue(projectChange({ state: "closed" })),
    setActor: vi.fn(),
    landingZoneTemplates: vi.fn().mockResolvedValue(TEMPLATES),
    landingZoneTemplate: vi.fn().mockResolvedValue(SAAS_TEMPLATE),
    controlPacks: vi.fn().mockResolvedValue(PACK_CATALOG),
    landingZoneReadBack: vi.fn().mockResolvedValue(READ_BACK),
    proposeLandingZone: vi.fn().mockResolvedValue(PROPOSAL),
    createLandingZoneDesign: vi.fn().mockResolvedValue(landingZoneDesign({ status: "draft", submitted_by: null })),
    landingZoneDesigns: vi.fn().mockResolvedValue([landingZoneDesign()]),
    landingZoneDesign: vi.fn().mockImplementation(async (id: string) => landingZoneDetail({ id })),
    submitLandingZoneDesign: vi.fn().mockResolvedValue(landingZoneDesign()),
    approveLandingZoneDesign: vi.fn().mockResolvedValue(landingZoneDesign({
      status: "applied", decided_by: "riley", repository: "acme-platform/landing-zone-infra",
      commit_sha: "a".repeat(40), accounts: { "acme-payments-prod": "123456789012" } })),
    rejectLandingZoneDesign: vi.fn().mockResolvedValue(landingZoneDesign({ status: "rejected", decided_by: "riley" })),
    networks: vi.fn().mockImplementation(async (provider: string) => (provider === "gcp" ? [GCP_NETWORK]
      : [network(), network({ id: "net-dev-use1", account_id: "222222222222", is_default: false })])),
    createNetwork: vi.fn().mockImplementation(async (input) => ({ id: "net-new", ...input })),
    updateNetwork: vi.fn().mockImplementation(async (id, input) => ({ id, ...input })),
    networkSettings: vi.fn().mockResolvedValue({ attach_compute_by_default: true }),
    updateNetworkSettings: vi.fn().mockImplementation(async (settings) => settings),
    networkOptions: vi.fn().mockImplementation(async (_portfolio: string, provider: string) => (provider === "gcp"
      ? [{ environment: "dev", region: "us-east1", account_id: GCP_NETWORK.account_id, networks: [GCP_NETWORK],
        default_network_id: GCP_NETWORK.id }]
      : NETWORK_OPTIONS)),
    pipeline: vi.fn().mockResolvedValue(pipeline()),
    inbox: vi.fn().mockResolvedValue([release()]),
    simulateRelease: vi.fn().mockResolvedValue(release({ id: "rel-2" })),
    approveRelease: vi.fn().mockResolvedValue(release({ state: "deployed",
      execution_detail: "Release executor applied change set cs-4f78c64a1b2c in stage.",
      decisions: [{ actor: "sam", kind: "approve", comment: "ok", created_at: "2026-10-03T20:05:00" }] })),
    rejectRelease: vi.fn().mockResolvedValue(release({ state: "rejected" })),
    approveOverride: vi.fn().mockResolvedValue(release({ state: "awaiting_approval" })),
    ...overrides,
  };
}
