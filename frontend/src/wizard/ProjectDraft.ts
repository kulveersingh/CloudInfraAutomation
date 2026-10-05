import type {
  Classification, CloudProviderInfo, ConnectionRequest, ProjectRequest, ResilienceMode, ResourceRequest, SettingValue,
} from "../api/types";

const NAME_PATTERN = /^[a-z][a-z0-9]*(-[a-z0-9]+)*$/;
const NAME_LENGTH = { min: 3, max: 30 };
const ID_LENGTH = 10;
const MULTI_REGION_ENVIRONMENTS = new Set(["stage", "prod"]);

export interface DraftResource {
  id: string;
  type: string;
  properties: Record<string, unknown>;
  /** Curated service settings the user changed; the platform's defaults apply to the rest. */
  settings: Record<string, SettingValue>;
}

export interface DraftValues {
  provider: string;
  name: string;
  portfolioId: string;
  productId: string;
  classification: Classification;
  mode: ResilienceMode;
  primaryRegion: string;
  secondaryRegion: string;
  environments: string[];
  resources: DraftResource[];
  connections: ConnectionRequest[];
  attachCompute: boolean;
  networkSelections: Record<string, string>;
}

/** Immutable model of the wizard: every change returns a new draft; toRequest() builds the API payload. */
export class ProjectDraft {
  constructor(readonly values: DraftValues) {}

  static initial(): ProjectDraft {
    return new ProjectDraft({
      provider: "aws", name: "", portfolioId: "", productId: "", classification: "internal", mode: "single",
      primaryRegion: "us-east-1", secondaryRegion: "us-east-2", environments: [], resources: [], connections: [],
      attachCompute: true, networkSelections: {},
    });
  }

  /** A project read back from its repository (§21.8): settings and CloudFormation properties come apart again. */
  static fromRequest(request: ProjectRequest): ProjectDraft {
    const initial = ProjectDraft.initial().values;
    const { ownership, resilience, network } = request;
    return new ProjectDraft({
      ...initial, provider: request.provider ?? initial.provider, name: request.project_name, portfolioId: ownership.portfolio_id, productId: ownership.product_id,
      classification: ownership.data_classification, mode: resilience.mode, primaryRegion: resilience.primary_region,
      secondaryRegion: resilience.secondary_region ?? initial.secondaryRegion, environments: [...request.environments],
      resources: request.resources.map(fromResourceRequest), connections: [...request.connections],
      attachCompute: network.attach_compute, networkSelections: { ...network.selections },
    });
  }

  /** Another cloud: its default regions, and none of the services, connections or networks chosen for the old one. */
  withProvider(provider: CloudProviderInfo) {
    if (provider.id === this.values.provider) return this;
    return this.with({
      provider: provider.id, primaryRegion: provider.default_regions.primary,
      secondaryRegion: provider.default_regions.secondary, resources: [], connections: [], networkSelections: {},
    });
  }

  withName(name: string) { return this.with({ name }); }

  withOwnership(portfolioId: string, productId: string) { return this.with({ portfolioId, productId }); }

  withClassification(classification: Classification) { return this.with({ classification }); }

  withMode(mode: ResilienceMode) { return this.with({ mode }); }

  withPrimary(primaryRegion: string) { return this.with({ primaryRegion }); }

  withSecondary(secondaryRegion: string) { return this.with({ secondaryRegion }); }

  withEnvironment(environmentId: string, enabled: boolean) {
    const others = this.values.environments.filter((id) => id !== environmentId);
    return this.with({ environments: enabled ? [...others, environmentId] : others });
  }

  withResource(type: string) {
    const resource = { id: this.nextResourceId(type), type, properties: {}, settings: {} };
    return this.with({ resources: [...this.values.resources, resource] });
  }

  withoutResource(resourceId: string) {
    return this.with({
      resources: this.values.resources.filter((resource) => resource.id !== resourceId),
      connections: this.values.connections.filter(
        (connection) => connection.source !== resourceId && connection.target !== resourceId),
    });
  }

  withResourceProperties(resourceId: string, properties: Record<string, unknown>) {
    return this.with({
      resources: this.values.resources.map(
        (resource) => (resource.id === resourceId ? { ...resource, properties } : resource)),
    });
  }

  /** Sets one setting, or clears it back to the service default when the value is undefined. */
  withResourceSetting(resourceId: string, name: string, value: SettingValue | undefined) {
    return this.with({
      resources: this.values.resources.map((resource) => {
        if (resource.id !== resourceId) return resource;
        const { [name]: _previous, ...others } = resource.settings;
        return { ...resource, settings: value === undefined ? others : { ...others, [name]: value } };
      }),
    });
  }

  withConnection(connection: ConnectionRequest) {
    return this.with({ connections: [...this.values.connections, connection] });
  }

  withoutConnection(index: number) {
    return this.with({ connections: this.values.connections.filter((_, position) => position !== index) });
  }

  withAttachCompute(attachCompute: boolean) { return this.with({ attachCompute }); }

  withNetworkSelection(environmentId: string, region: string, networkId: string) {
    return this.with({ networkSelections: { ...this.values.networkSelections, [`${environmentId}:${region}`]: networkId } });
  }

  /** Mirrors the platform topology: DR/HA puts QA/STAGE and PROD in both regions, everything else in the primary. */
  regionsFor(environmentId: string): string[] {
    const { mode, primaryRegion, secondaryRegion } = this.values;
    return mode !== "single" && MULTI_REGION_ENVIRONMENTS.has(environmentId)
      ? [primaryRegion, secondaryRegion] : [primaryRegion];
  }

  problems(): string[] {
    const { productId, environments, resources, mode, primaryRegion, secondaryRegion } = this.values;
    const checks: Array<[boolean, string]> = [
      [!this.hasValidName(), "Enter a project name: 3–30 lowercase letters, digits and single hyphens."],
      [productId === "", "Choose a portfolio and product."],
      [environments.length === 0, "Select at least one environment."],
      [resources.length === 0, "Add at least one service."],
      [mode !== "single" && primaryRegion === secondaryRegion, "Choose two different regions for the DR/HA pair."],
    ];
    return checks.filter(([failed]) => failed).map(([, message]) => message);
  }

  toRequest(): ProjectRequest {
    const values = this.values;
    return {
      provider: values.provider,
      project_name: values.name,
      ownership: {
        portfolio_id: values.portfolioId, product_id: values.productId, data_classification: values.classification,
      },
      resilience: {
        mode: values.mode, primary_region: values.primaryRegion,
        secondary_region: values.mode === "single" ? null : values.secondaryRegion,
      },
      environments: values.environments,
      resources: values.resources.map(toResourceRequest),
      connections: values.connections,
      network: { attach_compute: values.attachCompute, selections: values.networkSelections },
    };
  }

  private hasValidName(): boolean {
    const { name } = this.values;
    return NAME_PATTERN.test(name) && name.length >= NAME_LENGTH.min && name.length <= NAME_LENGTH.max;
  }

  private nextResourceId(type: string): string {
    const base = type.split(/::|[._]/).slice(-1)[0].toLowerCase().replace(/[^a-z]/g, "").slice(0, ID_LENGTH);
    const taken = new Set(this.values.resources.map((resource) => resource.id));
    let candidate = base;
    for (let suffix = 2; taken.has(candidate); suffix += 1) {
      candidate = `${base}${suffix}`;
    }
    return candidate;
  }

  private with(change: Partial<DraftValues>): ProjectDraft {
    return new ProjectDraft({ ...this.values, ...change });
  }
}

function toResourceRequest(resource: DraftResource): ResourceRequest {
  const base = { id: resource.id, type: resource.type };
  const properties = Object.keys(resource.properties).length > 0 ? { properties: resource.properties } : {};
  const config = { ...resource.settings, ...properties };
  return Object.keys(config).length > 0 ? { ...base, config } : base;
}

function fromResourceRequest({ id, type, config = {} }: ResourceRequest): DraftResource {
  const { properties, ...settings } = config as { properties?: Record<string, unknown> } & Record<string, SettingValue>;
  return { id, type, properties: properties ?? {}, settings };
}
