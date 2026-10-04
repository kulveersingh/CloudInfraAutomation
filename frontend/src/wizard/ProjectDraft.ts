import type { Classification, ConnectionRequest, ProjectRequest, ResilienceMode, ResourceRequest } from "../api/types";

const NAME_PATTERN = /^[a-z][a-z0-9]*(-[a-z0-9]+)*$/;
const NAME_LENGTH = { min: 3, max: 30 };
const ID_LENGTH = 10;
const MULTI_REGION_ENVIRONMENTS = new Set(["stage", "prod"]);

export interface DraftResource {
  id: string;
  type: string;
  properties: Record<string, unknown>;
}

export interface DraftValues {
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
      name: "", portfolioId: "", productId: "", classification: "internal", mode: "single",
      primaryRegion: "us-east-1", secondaryRegion: "us-east-2", environments: [], resources: [], connections: [],
      attachCompute: true, networkSelections: {},
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
    const resource = { id: this.nextResourceId(type), type, properties: {} };
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
    const base = type.split(/::|\./).slice(-1)[0].toLowerCase().replace(/[^a-z]/g, "").slice(0, ID_LENGTH);
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
  return Object.keys(resource.properties).length > 0 ? { ...base, config: { properties: resource.properties } } : base;
}
