import type { EnvironmentCount, FlowException, LandingZoneAnswers, LandingZoneRequest, TreeEdit } from "../api/types";

const ORGANIZATION_NAME_PATTERN = /^[a-z][a-z0-9-]{1,30}$/;
const EMAIL_PATTERN = /^[^@\s+]+@[^@\s]+\.[^@\s]+$/;
const MINIMUM_GOVERNED_REGIONS = 2;

export type EnvironmentTier = "sandbox" | "nonprod" | "prod";
export type ListAnswer = "compliance" | "infrastructure" | "optional_ous";

export interface LandingZoneEnvironment {
  id: string;
  name: string;
  tier: EnvironmentTier;
}

const SANDBOX: LandingZoneEnvironment = { id: "sandbox", name: "Sandbox", tier: "sandbox" };
const DEV: LandingZoneEnvironment = { id: "dev", name: "DEV", tier: "nonprod" };
const TEST: LandingZoneEnvironment = { id: "test", name: "TEST", tier: "nonprod" };
const UAT: LandingZoneEnvironment = { id: "uat", name: "UAT", tier: "nonprod" };
const STAGE: LandingZoneEnvironment = { id: "stage", name: "STAGE", tier: "prod" };
const PROD: LandingZoneEnvironment = { id: "prod", name: "PROD", tier: "prod" };

/** Mirrors the platform's presets: 4 folds testing into DEV, 5 is recommended, 6 adds UAT. */
export const ENVIRONMENT_PRESETS: Record<EnvironmentCount, LandingZoneEnvironment[]> = {
  4: [SANDBOX, DEV, STAGE, PROD],
  5: [SANDBOX, DEV, TEST, STAGE, PROD],
  6: [SANDBOX, DEV, TEST, UAT, STAGE, PROD],
};

/**
 * Immutable model of the landing zone questionnaire plus the OU tree editor's changes, in order.
 * Defaults are the platform's recommendations; the edits survive answer changes and are replayed by the platform.
 */
export class LandingZoneDraft {
  private constructor(private readonly answers: LandingZoneAnswers, private readonly treeEdits: TreeEdit[]) {}

  static initial(): LandingZoneDraft {
    return new LandingZoneDraft({
      organization_name: "", management_email: "", home_region: "us-east-1", governed_regions: ["us-east-1", "us-east-2"],
      environment_count: 5, environment_names: {}, grouping: "separate", account_model: "portfolio", compliance: [],
      security_tooling: true, log_retention_days: 365,
      infrastructure: ["network", "shared_services", "identity", "backup", "monitoring"],
      network: { hub: true, egress: "central", inspection: true, on_premises: "none", cidr: "10.0.0.0/8", flows: [] },
      sandbox: { model: "team", monthly_budget_usd: 500, expiry_days: 30 },
      optional_ous: ["exceptions", "suspended"], controls_profile: "recommended",
    }, []);
  }

  with(change: Partial<LandingZoneAnswers>): LandingZoneDraft {
    return new LandingZoneDraft({ ...this.answers, ...change }, this.treeEdits);
  }

  withEdit(edit: TreeEdit): LandingZoneDraft {
    return new LandingZoneDraft(this.answers, [...this.treeEdits, edit]);
  }

  withoutEdit(index: number): LandingZoneDraft {
    return new LandingZoneDraft(this.answers, this.treeEdits.filter((_, position) => position !== index));
  }

  edits(): TreeEdit[] {
    return this.treeEdits;
  }

  withOrganization(organizationName: string, managementEmail: string) {
    return this.with({ organization_name: organizationName, management_email: managementEmail });
  }

  withRegion(region: string, governed: boolean) {
    return this.with({ governed_regions: toggled(this.answers.governed_regions, region, governed) });
  }

  withEnvironmentCount(count: EnvironmentCount) {
    const known = new Set(ENVIRONMENT_PRESETS[count].map((environment) => environment.id));
    const names = Object.entries(this.answers.environment_names).filter(([id]) => known.has(id));
    const flows = this.answers.network.flows.filter((flow) => known.has(flow.source) && known.has(flow.destination));
    return this.with({ environment_count: count, environment_names: Object.fromEntries(names) })
      .withNetwork({ flows });
  }

  /** An empty name restores the preset name. */
  withEnvironmentName(environmentId: string, name: string) {
    const { [environmentId]: _previous, ...others } = this.answers.environment_names;
    return this.with({ environment_names: name === "" ? others : { ...others, [environmentId]: name } });
  }

  withListItem(answer: ListAnswer, item: string, included: boolean) {
    return this.with({ [answer]: toggled(this.answers[answer], item, included) });
  }

  withNetwork(change: Partial<LandingZoneAnswers["network"]>) {
    return this.with({ network: { ...this.answers.network, ...change } });
  }

  withSandbox(change: Partial<LandingZoneAnswers["sandbox"]>) {
    return this.with({ sandbox: { ...this.answers.sandbox, ...change } });
  }

  withFlow(flow: FlowException) {
    return this.withNetwork({ flows: [...this.answers.network.flows, flow] });
  }

  withoutFlow(index: number) {
    return this.withNetwork({ flows: this.answers.network.flows.filter((_, position) => position !== index) });
  }

  environments(): LandingZoneEnvironment[] {
    const { environment_count, environment_names } = this.answers;
    return ENVIRONMENT_PRESETS[environment_count].map(
      (environment) => ({ ...environment, name: environment_names[environment.id] ?? environment.name }));
  }

  /** Checks the browser can make; the platform validates the rest when it proposes the structure. */
  problems(): string[] {
    const { organization_name, management_email, governed_regions, home_region } = this.answers;
    const checks: Array<[boolean, string]> = [
      [!ORGANIZATION_NAME_PATTERN.test(organization_name), "Organization name: 2–31 lowercase letters, digits or hyphens."],
      [!EMAIL_PATTERN.test(management_email), "Enter the management account email."],
      [governed_regions.length < MINIMUM_GOVERNED_REGIONS, "Choose at least two governed regions."],
      [!governed_regions.includes(home_region), "The home region must be a governed region."],
    ];
    return checks.filter(([failed]) => failed).map(([, message]) => message);
  }

  toAnswers(): LandingZoneAnswers {
    return this.answers;
  }

  toRequest(): LandingZoneRequest {
    return { answers: this.answers, edits: this.treeEdits };
  }
}

function toggled<T extends string>(items: T[], item: string, included: boolean): T[] {
  if (!included) return items.filter((existing) => existing !== item);
  return items.includes(item as T) ? items : [...items, item as T];
}
