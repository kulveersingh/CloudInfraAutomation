import type {
  CatalogEntry, CloudFormationType, CostCenterChange, CostCenterSettings, EnvironmentInfo, JobStatus,
  PlatformApiPort, Portfolio, PreviewResult, ProjectRequest, ProjectSummary, RegionInfo,
} from "./types";

type Fetcher = (input: string, init: RequestInit) => Promise<Response>;

export class ApiError extends Error {
  constructor(readonly status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

/** HTTP client for the platform API. Errors carry the server's message so the UI can show it as-is. */
export class PlatformApi implements PlatformApiPort {
  constructor(
    private readonly baseUrl = "",
    private readonly fetcher: Fetcher = (input, init) => globalThis.fetch(input, init),
  ) {}

  orgRegistry() { return this.send<Portfolio[]>("GET", "/v1/org-registry"); }

  environments() { return this.send<EnvironmentInfo[]>("GET", "/v1/environments"); }

  regions() { return this.send<RegionInfo[]>("GET", "/v1/admin/regions"); }

  setRegionEnabled(regionId: string, enabled: boolean) {
    return this.send<RegionInfo>("PUT", `/v1/admin/regions/${regionId}`, { enabled });
  }

  catalog() { return this.send<CatalogEntry[]>("GET", "/v1/catalog"); }

  searchCloudFormation(text: string) {
    return this.send<CloudFormationType[]>("GET", `/v1/catalog/cloudformation?search=${encodeURIComponent(text)}`);
  }

  costCenters() { return this.send<CostCenterSettings>("GET", "/v1/admin/cost-centers"); }

  updateCostCenters(change: CostCenterChange) {
    return this.send<CostCenterSettings>("PUT", "/v1/admin/cost-centers", change);
  }

  preview(request: ProjectRequest) { return this.send<PreviewResult>("POST", "/v1/projects:preview", request); }

  createProject(request: ProjectRequest, idempotencyKey: string) {
    return this.send<{ job_id: string }>("POST", "/v1/projects", request, { "Idempotency-Key": idempotencyKey });
  }

  projects() { return this.send<ProjectSummary[]>("GET", "/v1/projects"); }

  job(jobId: string) { return this.send<JobStatus>("GET", `/v1/jobs/${jobId}`); }

  private async send<T>(method: string, path: string, body?: unknown, headers: Record<string, string> = {}) {
    const response = await this.fetcher(`${this.baseUrl}${path}`, {
      method,
      headers: { "Content-Type": "application/json", ...headers },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new ApiError(response.status, describeFailure(payload, response.status));
    }
    return payload as T;
  }
}

function describeFailure(payload: { detail?: unknown }, status: number): string {
  const { detail } = payload;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((item: { msg: string }) => item.msg).join("; ");
  return `Request failed with status ${status}`;
}
