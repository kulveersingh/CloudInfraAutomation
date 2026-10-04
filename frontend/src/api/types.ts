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
}

export interface PreviewResult {
  files: Record<string, string>;
  tags: Record<string, string>;
  targets: Record<string, { account_id: string; regions: string[] }>;
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

export interface PlatformApiPort {
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
