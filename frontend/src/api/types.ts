export type ResilienceMode = "single" | "dr" | "ha";
export type Classification = "public" | "internal" | "confidential" | "restricted";
export type AccessLevel = "read" | "write" | "readwrite";

export interface CostCenterValue {
  value: string;
  source: string;
}

export interface Product {
  id: string;
  name: string;
  kind: string;
  classification_ceiling: Classification;
  cost_center: CostCenterValue;
}

export interface Portfolio {
  id: string;
  name: string;
  cost_center: CostCenterValue;
  products: Product[];
}

export interface EnvironmentInfo {
  id: string;
  name: string;
  tier: string;
  position: number;
  requires_approval: boolean;
}

export interface RegionInfo {
  id: string;
  name: string;
  enabled: boolean;
}

export interface CatalogEntry {
  type: string;
  name: string;
  category: string;
  multi_region: string;
}

export interface CloudFormationType {
  type: string;
  service: string;
  required: string[];
}

export interface CostCenterProduct {
  id: string;
  name: string;
  cost_center: string | null;
  effective: CostCenterValue;
}

export interface CostCenterPortfolio {
  id: string;
  name: string;
  cost_center: string | null;
  effective: CostCenterValue;
  products: CostCenterProduct[];
}

export interface CostCenterSettings {
  default: string;
  pattern: string;
  portfolios: CostCenterPortfolio[];
}

export interface CostCenterChange {
  default?: string;
  portfolios?: Record<string, string | null>;
  products?: Record<string, string | null>;
}

export interface ResourceRequest {
  id: string;
  type: string;
  config?: Record<string, unknown>;
}

export interface ConnectionRequest {
  kind: string;
  source: string;
  target: string;
  access?: AccessLevel;
  prefix?: string;
}

export interface ProjectRequest {
  project_name: string;
  ownership: { portfolio_id: string; product_id: string; data_classification: Classification };
  resilience: { mode: ResilienceMode; primary_region: string; secondary_region: string | null };
  environments: string[];
  resources: ResourceRequest[];
  connections: ConnectionRequest[];
  network: { attach_compute: boolean; selections: Record<string, string> };
}

export interface NetworkInfo {
  id: string;
  name: string;
  account_id: string;
  region: string;
  vpc_id: string;
  cidr: string;
  private_subnet_ids: string[];
  security_group_ids: string[];
  is_default: boolean;
}

export type NetworkInput = Omit<NetworkInfo, "id">;

export interface NetworkOption {
  environment: string;
  region: string;
  account_id: string;
  networks: NetworkInfo[];
  default_network_id: string | null;
}

export interface NetworkSettings {
  attach_compute_by_default: boolean;
}

export interface PreviewResult {
  files: Record<string, string>;
  tags: Record<string, string>;
  targets: Record<string, { account_id: string; regions: string[];
    networks: Record<string, { network_id: string; vpc_id: string; subnet_ids: string[] }> }>;
  lint: string[];
}

export interface ProjectSummary {
  name: string;
  portfolio_id: string;
  product_id: string;
  resilience_mode: ResilienceMode;
  status: string;
}

export interface JobStep {
  sequence: number;
  name: string;
  state: string;
  detail: string;
}

export interface JobStatus {
  id: string;
  project_name: string;
  state: string;
  error: string | null;
  steps: JobStep[];
}

export interface ReleaseChange {
  action: "Add" | "Modify" | "Remove";
  logical_id: string;
  resource_type: string;
  replacement: boolean;
  risk: "low" | "medium" | "high";
}

export interface ReleaseDecision {
  actor: string;
  kind: string;
  comment: string;
  created_at: string;
}

export interface Release {
  id: string;
  project_name: string;
  environment: string;
  commit_sha: string;
  artifact_digest: string;
  risk: "low" | "medium" | "high";
  changes: ReleaseChange[];
  evidence: { tests_passed: boolean; critical_vulnerabilities: number; high_vulnerabilities: number; signed: boolean };
  gate_findings: string[];
  state: string;
  requested_by: string;
  execution_detail: string | null;
  created_at: string;
  decisions: ReleaseDecision[];
}

export interface PipelineStage {
  environment: string;
  name: string;
  requires_approval: boolean;
  release: Release | null;
}

export type EnvironmentCount = 4 | 5 | 6;

export interface FlowException {
  source: string;
  destination: string;
  protocol: "tcp" | "udp";
  port: number;
  reason: string;
}

export interface LandingZoneAnswers {
  organization_name: string;
  management_email: string;
  home_region: string;
  governed_regions: string[];
  environment_count: EnvironmentCount;
  environment_names: Record<string, string>;
  grouping: "separate" | "prod_nonprod";
  account_model: "environment" | "portfolio" | "product";
  compliance: string[];
  security_tooling: boolean;
  log_retention_days: number;
  infrastructure: string[];
  network: {
    hub: boolean;
    egress: "central" | "local";
    inspection: boolean;
    on_premises: "none" | "vpn" | "direct_connect";
    cidr: string;
    flows: FlowException[];
  };
  sandbox: { model: "team" | "developer"; monthly_budget_usd: number; expiry_days: number };
  optional_ous: string[];
  controls_profile: "baseline" | "recommended" | "regulated";
}

export type TreeEdit =
  | { op: "add_ou"; parent: string | null; name: string }
  | { op: "rename_ou"; ou: string; name: string }
  | { op: "move_ou"; ou: string; parent: string }
  | { op: "remove_ou"; ou: string }
  | { op: "add_account"; ou: string; suffix: string }
  | { op: "disable_account"; account: string }
  | { op: "enable_account"; account: string }
  | { op: "remove_account"; account: string }
  | { op: "move_account"; account: string; ou: string };

export type OuEdit = "add_child" | "add_account" | "rename" | "move" | "remove";
export type AccountEdit = "move" | "disable" | "enable" | "remove";

export interface AccountInfo {
  name: string;
  enabled: boolean;
  added: boolean;
  allowed_edits: AccountEdit[];
}

export interface OuInfo {
  key: string;
  name: string;
  kind: string;
  environment: string | null;
  tier: string | null;
  created_by_control_tower: boolean;
  custom: boolean;
  domain: string | null;
  allowed_edits: OuEdit[];
  blocked_edits: Partial<Record<OuEdit, string>>;
  accounts: AccountInfo[];
  children: OuInfo[];
}

export interface LandingZoneRequest {
  answers: LandingZoneAnswers;
  edits: TreeEdit[];
}

export interface LandingZoneExplanation {
  ous: OuInfo[];
  problems: string[];
  diagram: { svg: string; mermaid: string };
}

export interface LandingZoneProposal extends LandingZoneExplanation {
  files: Record<string, string>;
}

export type LandingZoneStatus = "draft" | "pending_approval" | "applied" | "rejected";

export interface LandingZoneDesign {
  id: string;
  version: number;
  status: LandingZoneStatus;
  organization_name: string;
  answers: LandingZoneAnswers;
  edits: TreeEdit[];
  created_by: string;
  submitted_by: string | null;
  decided_by: string | null;
  decision_comment: string | null;
  repository: string | null;
  commit_sha: string | null;
  accounts: Record<string, string>;
  created_at: string;
}

export type LandingZoneDesignDetail = LandingZoneDesign & LandingZoneExplanation;

export interface Identity {
  name: string;
  label: string;
  roles: string[];
}

export interface PlatformApiPort {
  proposeLandingZone(request: LandingZoneRequest): Promise<LandingZoneProposal>;
  createLandingZoneDesign(request: LandingZoneRequest): Promise<LandingZoneDesign>;
  landingZoneDesigns(): Promise<LandingZoneDesign[]>;
  landingZoneDesign(designId: string): Promise<LandingZoneDesignDetail>;
  submitLandingZoneDesign(designId: string): Promise<LandingZoneDesign>;
  approveLandingZoneDesign(designId: string, comment: string): Promise<LandingZoneDesign>;
  rejectLandingZoneDesign(designId: string, comment: string): Promise<LandingZoneDesign>;
  networks(): Promise<NetworkInfo[]>;
  createNetwork(network: NetworkInput): Promise<NetworkInfo>;
  updateNetwork(networkId: string, network: NetworkInput): Promise<NetworkInfo>;
  networkSettings(): Promise<NetworkSettings>;
  updateNetworkSettings(settings: NetworkSettings): Promise<NetworkSettings>;
  networkOptions(portfolioId: string): Promise<NetworkOption[]>;
  setActor(identity: Identity): void;
  pipeline(projectName: string): Promise<PipelineStage[]>;
  inbox(): Promise<Release[]>;
  simulateRelease(projectName: string, environment: string, highRisk: boolean): Promise<Release>;
  approveRelease(releaseId: string, comment: string): Promise<Release>;
  rejectRelease(releaseId: string, comment: string): Promise<Release>;
  approveOverride(releaseId: string, comment: string): Promise<Release>;
  orgRegistry(): Promise<Portfolio[]>;
  environments(): Promise<EnvironmentInfo[]>;
  regions(): Promise<RegionInfo[]>;
  setRegionEnabled(regionId: string, enabled: boolean): Promise<RegionInfo>;
  catalog(): Promise<CatalogEntry[]>;
  searchCloudFormation(text: string): Promise<CloudFormationType[]>;
  costCenters(): Promise<CostCenterSettings>;
  updateCostCenters(change: CostCenterChange): Promise<CostCenterSettings>;
  preview(request: ProjectRequest): Promise<PreviewResult>;
  createProject(request: ProjectRequest, idempotencyKey: string): Promise<{ job_id: string }>;
  projects(): Promise<ProjectSummary[]>;
  job(jobId: string): Promise<JobStatus>;
}
