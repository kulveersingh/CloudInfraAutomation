import { vi } from "vitest";
import type {
  CatalogEntry, CostCenterSettings, EnvironmentInfo, JobStatus, PlatformApiPort, Portfolio, PreviewResult,
  ProjectSummary, RegionInfo,
} from "../api/types";

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
  targets: { prod: { account_id: "555555555555", regions: ["us-east-1", "us-east-2"] } },
  lint: [],
};

export const PROJECTS: ProjectSummary[] = [
  { name: "invoice-ingest", portfolio_id: "pf-payments", product_id: "pr-invoicing", resilience_mode: "dr",
    status: "active" },
];

export function job(state: string, steps: JobStatus["steps"] = [], error: string | null = null): JobStatus {
  return { id: "job-1", project_name: "demo-app", state, error, steps };
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
    ...overrides,
  };
}
