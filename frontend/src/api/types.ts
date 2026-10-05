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

interface SettingBase {
  name: string;
  label: string;
}

/** A `config` key a curated service accepts, as the platform declares it (§6.4.1). */
export type ServiceSetting =
  | (SettingBase & { kind: "choice"; default: string; choices: string[] })
  | (SettingBase & { kind: "integer"; default: number; minimum: number; maximum: number; unit: string })
  | (SettingBase & { kind: "text"; default: string | null; pattern: string; rule: string; optional: boolean });

export type SettingValue = string | number;

export interface CatalogEntry {
  type: string;
  name: string;
  category: string;
  multi_region: string;
  settings: ServiceSetting[];
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

export interface PullRequestLink {
  number: number;
  url: string;
}

/** The change a project has in flight: queued for the worker, or open as a pull request. */
export interface OpenChange {
  id: string;
  revision: number;
  state: "queued" | "open";
  pull_request: PullRequestLink | null;
}

export interface Vocabulary {
  isolation_unit: string;
  hierarchy_node: string;
  iac_document: string;
  deploy_unit: string;
  preventive_policy: string;
  private_network: string;
  landing_zone_service: string;
  control_catalog: string;
}

/** A cloud behind the platform (§22): its words for the neutral concepts and default region pair. */
export interface CloudProviderInfo {
  id: string;
  name: string;
  vocabulary: Vocabulary;
  default_regions: { primary: string; secondary: string };
}

export interface ProjectSummary {
  name: string;
  provider: string;
  portfolio_id: string;
  product_id: string;
  resilience_mode: ResilienceMode;
  status: string;
  revision: number;
  open_change: OpenChange | null;
  environments: string[];
}

export type TeardownScope = "environment" | "project";
export type ApproverRole = "reviewer" | "platform-admin";

export interface DataStoreInfo {
  service_id: string;
  resource_type: string;
  physical_name: string;
  region: string;
  retained: boolean;
}

export interface TeardownPreview {
  scope: TeardownScope;
  backup_account: string | null;
  retention_days: number;
  blockers: string[];
  environments: Array<{
    environment: string; account_id: string; regions: string[]; approver_role: ApproverRole; stacks: string[];
    data_stores: DataStoreInfo[]; not_backed_up: string[];
  }>;
}

export interface RecoveryPointInfo {
  service_id: string;
  resource_type: string;
  physical_name: string;
  region: string;
  account_id: string;
  recovery_point_ref: string;
  vault: string;
  completed_at: string;
  locked_until: string;
}

export interface TeardownEnvironment {
  environment: string;
  state: string;
  approver_role: ApproverRole;
  decided_by: string | null;
  decision_comment: string | null;
  revision: number | null;
  error: string | null;
  job_id: string | null;
  recovery_points: RecoveryPointInfo[];
}

export interface TeardownRestore {
  state: string;
  requested_by: string | null;
  decided_by: string | null;
  job_id: string | null;
}

export interface Teardown {
  id: string;
  project_name: string;
  scope: TeardownScope;
  state: string;
  requested_by: string;
  base_revision: number;
  base_commit: string | null;
  created_at: string;
  environments: TeardownEnvironment[];
  restore: TeardownRestore | null;
}

export interface TeardownRequestBody {
  scope: TeardownScope;
  environments: string[];
  confirmation?: string;
}

export type EnvironmentDecision = "approve" | "reject" | "retry";
export type RestoreAction = "restore" | "approve-restore" | "reject-restore";

export type ChangeState = "queued" | "open" | "merged" | "closed" | "failed";

export interface ChangeSummary {
  added_services: string[];
  removed_services: Array<{ id: string; type: string; retained: boolean }>;
  changed_services: string[];
  added_environments: string[];
  changed_files: string[];
}

export interface ChangeRequestBody {
  request: ProjectRequest;
  base_commit: string;
  confirm_removals?: boolean;
}

export interface ProjectChange {
  id: string;
  project_name: string;
  revision: number;
  state: ChangeState;
  base_commit: string;
  branch: string;
  pull_request: PullRequestLink | null;
  summary: ChangeSummary;
  created_by: string;
  merge_commit: string | null;
  job_id: string | null;
  created_at: string;
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

export type EnvironmentPreset = 4 | 5 | 6;

export interface TemplateReference {
  id: string;
  version: number;
}

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
  template: TemplateReference | null;
  environment_ids: string[];
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
  controls_profile: ControlsProfile;
  control_packs: string[] | null;
  pack_parameters: Record<string, Record<string, string[]>>;
}

export type ControlsProfile = "baseline" | "recommended" | "regulated";
export type ControlBehavior = "PREVENTIVE" | "DETECTIVE" | "PROACTIVE";

export interface OuControl {
  id: string;
  name: string;
  behavior: ControlBehavior;
  severity: string;
  packs: string[];
}

export interface CatalogControlInfo {
  id: string;
  name: string;
  behavior: ControlBehavior;
  severity: string;
  implementation: string;
  frameworks: string[];
}

export interface ControlPackInfo {
  id: string;
  version: number;
  name: string;
  description: string;
  selectors: string[];
  optional: boolean;
  controls: CatalogControlInfo[];
}

export interface ControlPackCatalog {
  mappings_refreshed: string | null;
  profiles: Record<ControlsProfile, string[]>;
  packs: ControlPackInfo[];
}

export interface TemplateSummary {
  id: string;
  version: number;
  name: string;
  industry: string;
  description: string;
  frameworks: string[];
  frameworks_verified: boolean;
  environments: string[];
  packs: string[];
  ou_count: number;
  /** Distinct controls by behavior. */
  control_counts: Record<ControlBehavior, number>;
  /** Controls times the OUs they are enabled on: what Control Tower deploys. */
  enabled_controls: number;
}

export interface IndustryTemplate extends TemplateSummary {
  answers: Partial<LandingZoneAnswers>;
  edits: TreeEdit[];
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
  controls: OuControl[];
  children: OuInfo[];
}

export interface LandingZoneRequest {
  answers: LandingZoneAnswers;
  edits: TreeEdit[];
}

export interface LandingZoneExplanation {
  ous: OuInfo[];
  problems: string[];
  warnings: string[];
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

export interface ReadBackFinding {
  check: string;
  severity: "blocking" | "warning";
  message: string;
  /** Files the finding is about; `diff` shows a hand edit when the platform can rebuild the original. */
  files: Array<{ path: string; diff: string | null }>;
}

/** A design read back from a repository the platform generated; `request` is present only when verified. */
export interface RepositoryReadBack<Request> {
  verified: boolean;
  commit_sha: string | null;
  findings: ReadBackFinding[];
  design: { kind: string; id: string; revision: number };
  request: Request | null;
}

export type LandingZoneReadBack = RepositoryReadBack<LandingZoneRequest>;
export type ProjectReadBack = RepositoryReadBack<ProjectRequest>;

export interface Identity {
  name: string;
  label: string;
  roles: string[];
}

export interface PlatformApiPort {
  landingZoneTemplates(): Promise<TemplateSummary[]>;
  landingZoneTemplate(templateId: string): Promise<IndustryTemplate>;
  controlPacks(): Promise<ControlPackCatalog>;
  landingZoneReadBack(): Promise<LandingZoneReadBack>;
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
  projectReadBack(projectName: string): Promise<ProjectReadBack>;
  previewChange(projectName: string, body: ChangeRequestBody): Promise<ProjectChangePreview>;
  createChange(projectName: string, body: ChangeRequestBody): Promise<ProjectChange>;
  projectChange(projectName: string, changeId: string): Promise<ProjectChange>;
  mergeChange(projectName: string, changeId: string): Promise<ProjectChange>;
  closeChange(projectName: string, changeId: string): Promise<ProjectChange>;
  previewTeardown(projectName: string, body: TeardownRequestBody): Promise<TeardownPreview>;
  requestTeardown(projectName: string, body: TeardownRequestBody): Promise<Teardown>;
  teardowns(): Promise<Teardown[]>;
  providers(): Promise<CloudProviderInfo[]>;
  decideTeardownEnvironment(projectName: string, teardownId: string, environment: string, decision: EnvironmentDecision,
    comment: string): Promise<Teardown>;
  restoreTeardown(projectName: string, teardownId: string, action: RestoreAction, comment: string): Promise<Teardown>;
}

export type ProjectChangePreview = PreviewResult & { summary: ChangeSummary };
