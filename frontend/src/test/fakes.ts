import { vi } from "vitest";
import type {
  AccountInfo, CatalogEntry, CostCenterSettings, EnvironmentInfo, JobStatus, LandingZoneDesign, LandingZoneDesignDetail,
  LandingZoneProposal, NetworkInfo, NetworkOption, OuInfo, PipelineStage, PlatformApiPort, Portfolio, PreviewResult,
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
  { id: "us-east-1", name: "US East (N. Virginia)", enabled: true },
  { id: "us-east-2", name: "US East (Ohio)", enabled: true },
  { id: "ap-southeast-2", name: "Asia Pacific (Sydney)", enabled: false },
];

export const CATALOG: CatalogEntry[] = [
  { type: "lambda.function", name: "Lambda function", category: "Compute", multi_region: "replicated" },
  { type: "s3.bucket", name: "S3 bucket", category: "Storage", multi_region: "replicated" },
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
    "us-east-1": { network_id: "net-prod-use1", vpc_id: "vpc-0aaa1111bbbb22223", subnet_ids: ["subnet-0a", "subnet-0b"] },
  } } },
  lint: [],
};

export const PROJECTS: ProjectSummary[] = [
  { name: "invoice-ingest", portfolio_id: "pf-payments", product_id: "pr-invoicing", resilience_mode: "dr",
    status: "active" },
];

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
    id: "net-prod-use1", name: "Org shared VPC", account_id: "555555555555", region: "us-east-1",
    vpc_id: "vpc-0aaa1111bbbb22223", cidr: "10.5.0.0/16", private_subnet_ids: ["subnet-0a1111", "subnet-0b2222"],
    security_group_ids: ["sg-0c3333"], is_default: true, ...overrides,
  };
}

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
  key, name, kind, environment: null, tier: null, created_by_control_tower: false, custom: false, domain: null,
  allowed_edits: [], blocked_edits: {}, accounts: [], children: [], ...extra,
});

const account = (name: string, extra: Partial<AccountInfo> = {}): AccountInfo => ({
  name, enabled: true, added: false, allowed_edits: ["move", "disable"], ...extra,
});
const fixed = (name: string) => account(name, { allowed_edits: [] });
const CONTAINER: OuInfo["allowed_edits"] = ["add_child", "add_account"];

export const OU_TREE: OuInfo[] = [
  ou("security", "Security", "security", { created_by_control_tower: true,
    accounts: [fixed("acme-log-archive"), fixed("acme-audit")] }),
  ou("infrastructure", "Infrastructure", "infrastructure", { domain: "infrastructure", allowed_edits: CONTAINER,
    accounts: [fixed("acme-network")] }),
  ou("prod", "PROD", "environment", { environment: "prod", tier: "prod", domain: "prod", allowed_edits: CONTAINER,
    accounts: [account("acme-payments-prod")], children: [
      ou("custom_payments", "Payments", "custom", { custom: true, domain: "prod",
        allowed_edits: [...CONTAINER, "rename", "move", "remove"] }),
      ou("custom_cards", "Cards", "custom", { custom: true, domain: "prod", allowed_edits: [...CONTAINER, "rename", "move"],
        blocked_edits: { remove: "Move its accounts and child OUs to another OU first." },
        accounts: [account("acme-cards-prod", { added: true, allowed_edits: ["move", "disable", "remove"] })] }),
    ] }),
  ou("parent_nonprod", "NonProd", "parent", { children: [ou("dev", "DEV", "environment", { environment: "dev",
    domain: "dev", allowed_edits: CONTAINER,
    accounts: [account("acme-retail-dev", { enabled: false, allowed_edits: ["move", "enable"] })] })] }),
];

const DIAGRAM = { svg: '<svg xmlns="http://www.w3.org/2000/svg"><text>PROD OU</text></svg>', mermaid: "flowchart TD" };

export const PROPOSAL: LandingZoneProposal = {
  ous: OU_TREE, problems: [], diagram: DIAGRAM,
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
  return { ...landingZoneDesign(overrides), ous: OU_TREE, problems: [], diagram: DIAGRAM };
}

export function fakeApi(overrides: Partial<PlatformApiPort> = {}): PlatformApiPort {
  return {
    orgRegistry: vi.fn().mockResolvedValue(PORTFOLIOS),
    environments: vi.fn().mockResolvedValue(ENVIRONMENTS),
    regions: vi.fn().mockResolvedValue(REGIONS),
    setRegionEnabled: vi.fn().mockImplementation(async (id: string, enabled: boolean) => ({
      ...REGIONS.find((region) => region.id === id)!, enabled })),
    catalog: vi.fn().mockResolvedValue(CATALOG),
    searchCloudFormation: vi.fn().mockResolvedValue([
      { type: "AWS::SNS::Topic", service: "SNS", required: [] },
      { type: "AWS::SNS::Subscription", service: "SNS", required: ["Protocol", "TopicArn"] },
    ]),
    costCenters: vi.fn().mockResolvedValue(COST_CENTERS),
    updateCostCenters: vi.fn().mockResolvedValue(COST_CENTERS),
    preview: vi.fn().mockResolvedValue(PREVIEW),
    createProject: vi.fn().mockResolvedValue({ job_id: "job-1" }),
    projects: vi.fn().mockResolvedValue(PROJECTS),
    job: vi.fn().mockResolvedValue(job("succeeded")),
    setActor: vi.fn(),
    proposeLandingZone: vi.fn().mockResolvedValue(PROPOSAL),
    createLandingZoneDesign: vi.fn().mockResolvedValue(landingZoneDesign({ status: "draft", submitted_by: null })),
    landingZoneDesigns: vi.fn().mockResolvedValue([landingZoneDesign()]),
    landingZoneDesign: vi.fn().mockImplementation(async (id: string) => landingZoneDetail({ id })),
    submitLandingZoneDesign: vi.fn().mockResolvedValue(landingZoneDesign()),
    approveLandingZoneDesign: vi.fn().mockResolvedValue(landingZoneDesign({
      status: "applied", decided_by: "riley", repository: "acme-platform/landing-zone-infra",
      commit_sha: "a".repeat(40), accounts: { "acme-payments-prod": "123456789012" } })),
    rejectLandingZoneDesign: vi.fn().mockResolvedValue(landingZoneDesign({ status: "rejected", decided_by: "riley" })),
    networks: vi.fn().mockResolvedValue([network(), network({ id: "net-dev-use1", account_id: "222222222222",
      is_default: false })]),
    createNetwork: vi.fn().mockImplementation(async (input) => ({ id: "net-new", ...input })),
    updateNetwork: vi.fn().mockImplementation(async (id, input) => ({ id, ...input })),
    networkSettings: vi.fn().mockResolvedValue({ attach_compute_by_default: true }),
    updateNetworkSettings: vi.fn().mockImplementation(async (settings) => settings),
    networkOptions: vi.fn().mockResolvedValue(NETWORK_OPTIONS),
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
