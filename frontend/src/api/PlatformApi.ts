import type {
  ChangeRequestBody, CloudProviderInfo, EnvironmentDecision, ProjectChange, ProjectChangePreview, ProjectReadBack, RestoreAction, Teardown,
  TeardownPreview, TeardownRequestBody,
  CatalogEntry, CloudFormationType, CostCenterChange, CostCenterSettings, EnvironmentInfo, Identity, JobStatus,
  ControlPackCatalog, IndustryTemplate, LandingZoneDesign, LandingZoneDesignDetail, LandingZoneProposal, LandingZoneReadBack,
  LandingZoneRequest,
  TemplateSummary, NetworkInfo, NetworkInput,
  NetworkOption, NetworkSettings, PipelineStage, PlatformApiPort, Portfolio, PreviewResult, ProjectRequest, ProjectSummary,
  RegionInfo, Release,
} from "./types";

type Fetcher = (input: string, init: RequestInit) => Promise<Response>;

const LANDING_ZONE_DESIGNS = "/v1/admin/landing-zone/designs";

export class ApiError extends Error {
  constructor(readonly status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

/** HTTP client for the platform API. Errors carry the server's message so the UI can show it as-is. */
export class PlatformApi implements PlatformApiPort {
  private actorHeaders: Record<string, string> = {};

  constructor(
    private readonly baseUrl = "",
    private readonly fetcher: Fetcher = (input, init) => globalThis.fetch(input, init),
  ) {}

  setActor(identity: Identity) {
    this.actorHeaders = { "X-Actor": identity.name, "X-Roles": identity.roles.join(",") };
  }

  landingZoneTemplates() { return this.send<TemplateSummary[]>("GET", "/v1/admin/landing-zone/templates"); }

  landingZoneTemplate(templateId: string) {
    return this.send<IndustryTemplate>("GET", `/v1/admin/landing-zone/templates/${templateId}`);
  }

  controlPacks() { return this.send<ControlPackCatalog>("GET", "/v1/admin/landing-zone/control-packs"); }

  landingZoneReadBack() {
    return this.send<LandingZoneReadBack>("GET", "/v1/admin/landing-zone/repository:read-back");
  }

  proposeLandingZone(request: LandingZoneRequest) {
    return this.send<LandingZoneProposal>("POST", "/v1/admin/landing-zone:propose", request);
  }

  createLandingZoneDesign(request: LandingZoneRequest) {
    return this.send<LandingZoneDesign>("POST", LANDING_ZONE_DESIGNS, request);
  }

  landingZoneDesigns() { return this.send<LandingZoneDesign[]>("GET", LANDING_ZONE_DESIGNS); }

  landingZoneDesign(designId: string) {
    return this.send<LandingZoneDesignDetail>("GET", `${LANDING_ZONE_DESIGNS}/${designId}`);
  }

  submitLandingZoneDesign(designId: string) {
    return this.send<LandingZoneDesign>("POST", `${LANDING_ZONE_DESIGNS}/${designId}:submit`);
  }

  approveLandingZoneDesign(designId: string, comment: string) {
    return this.decideLandingZone(designId, "approve", comment);
  }

  rejectLandingZoneDesign(designId: string, comment: string) {
    return this.decideLandingZone(designId, "reject", comment);
  }

  networks() { return this.send<NetworkInfo[]>("GET", "/v1/admin/networks"); }

  createNetwork(network: NetworkInput) { return this.send<NetworkInfo>("POST", "/v1/admin/networks", network); }

  updateNetwork(networkId: string, network: NetworkInput) {
    return this.send<NetworkInfo>("PUT", `/v1/admin/networks/${networkId}`, network);
  }

  networkSettings() { return this.send<NetworkSettings>("GET", "/v1/admin/network-settings"); }

  updateNetworkSettings(settings: NetworkSettings) {
    return this.send<NetworkSettings>("PUT", "/v1/admin/network-settings", settings);
  }

  networkOptions(portfolioId: string) {
    return this.send<NetworkOption[]>("GET", `/v1/networks/options?portfolio_id=${encodeURIComponent(portfolioId)}`);
  }

  pipeline(projectName: string) { return this.send<PipelineStage[]>("GET", `/v1/projects/${projectName}/pipeline`); }

  inbox() { return this.send<Release[]>("GET", "/v1/approvals/inbox"); }

  simulateRelease(projectName: string, environment: string, highRisk: boolean) {
    return this.send<Release>("POST", `/v1/projects/${projectName}/releases:simulate`,
      { environment, high_risk: highRisk });
  }

  approveRelease(releaseId: string, comment: string) { return this.decide(releaseId, "approve", comment); }

  rejectRelease(releaseId: string, comment: string) { return this.decide(releaseId, "reject", comment); }

  approveOverride(releaseId: string, comment: string) { return this.decide(releaseId, "approve-override", comment); }

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

  projectReadBack(projectName: string) {
    return this.send<ProjectReadBack>("GET", `/v1/projects/${projectName}/repository:read-back`);
  }

  previewChange(projectName: string, body: ChangeRequestBody) {
    return this.send<ProjectChangePreview>("POST", `/v1/projects/${projectName}/changes:preview`, body);
  }

  createChange(projectName: string, body: ChangeRequestBody) {
    return this.send<ProjectChange>("POST", `/v1/projects/${projectName}/changes`, body);
  }

  projectChange(projectName: string, changeId: string) {
    return this.send<ProjectChange>("GET", `/v1/projects/${projectName}/changes/${changeId}`);
  }

  mergeChange(projectName: string, changeId: string) {
    return this.send<ProjectChange>("POST", `/v1/projects/${projectName}/changes/${changeId}:merge`);
  }

  closeChange(projectName: string, changeId: string) {
    return this.send<ProjectChange>("POST", `/v1/projects/${projectName}/changes/${changeId}:close`);
  }

  previewTeardown(projectName: string, body: TeardownRequestBody) {
    return this.send<TeardownPreview>("POST", `/v1/projects/${projectName}/teardowns:preview`, body);
  }

  requestTeardown(projectName: string, body: TeardownRequestBody) {
    return this.send<Teardown>("POST", `/v1/projects/${projectName}/teardowns`, body);
  }

  teardowns() { return this.send<Teardown[]>("GET", "/v1/teardowns"); }

  providers() { return this.send<CloudProviderInfo[]>("GET", "/v1/providers"); }

  decideTeardownEnvironment(projectName: string, teardownId: string, environment: string, decision: EnvironmentDecision,
    comment: string) {
    return this.send<Teardown>("POST",
      `/v1/projects/${projectName}/teardowns/${teardownId}/environments/${environment}:${decision}`, { comment });
  }

  restoreTeardown(projectName: string, teardownId: string, action: RestoreAction, comment: string) {
    return this.send<Teardown>("POST", `/v1/projects/${projectName}/teardowns/${teardownId}:${action}`, { comment });
  }

  private decide(releaseId: string, decision: string, comment: string) {
    return this.send<Release>("POST", `/v1/releases/${releaseId}:${decision}`, { comment });
  }

  private decideLandingZone(designId: string, decision: string, comment: string) {
    return this.send<LandingZoneDesign>("POST", `${LANDING_ZONE_DESIGNS}/${designId}:${decision}`, { comment });
  }

  private async send<T>(method: string, path: string, body?: unknown, headers: Record<string, string> = {}) {
    const response = await this.fetcher(`${this.baseUrl}${path}`, {
      method,
      headers: { "Content-Type": "application/json", ...this.actorHeaders, ...headers },
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
