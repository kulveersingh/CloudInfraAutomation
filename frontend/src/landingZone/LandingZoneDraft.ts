import { cloudText } from "./cloudText";
import type {
  CloudProviderInfo, ControlsProfile, EnvironmentPreset, FlowException, IndustryTemplate, LandingZoneAnswers, LandingZoneRequest, TreeEdit,
} from "../api/types";

const ORGANIZATION_NAME_PATTERN = /^[a-z][a-z0-9-]{1,30}$/;
const MINIMUM_GOVERNED_REGIONS = 2;

export type EnvironmentTier = "sandbox" | "nonprod" | "prod";
export type ListAnswer = "compliance" | "infrastructure" | "optional_ous";

export interface LandingZoneEnvironment {
  id: string;
  name: string;
  tier: EnvironmentTier;
}

/** Mirrors the platform's environment catalog, in pipeline order. STAGE and PROD are always included. */
const ENVIRONMENT_CATALOG: LandingZoneEnvironment[] = [
  { id: "sandbox", name: "Sandbox", tier: "sandbox" }, { id: "dev", name: "DEV", tier: "nonprod" },
  { id: "qa", name: "QA", tier: "nonprod" }, { id: "test", name: "TEST", tier: "nonprod" },
  { id: "uat", name: "UAT", tier: "nonprod" }, { id: "perf", name: "PERF", tier: "nonprod" },
  { id: "stage", name: "STAGE", tier: "prod" }, { id: "prod", name: "PROD", tier: "prod" },
];
export const REQUIRED_ENVIRONMENTS = ["stage", "prod"];

/** One-click combinations: 4 folds testing into DEV, 5 is recommended, 6 adds UAT. */
export const ENVIRONMENT_PRESETS: Record<EnvironmentPreset, string[]> = {
  4: ["sandbox", "dev", "stage", "prod"],
  5: ["sandbox", "dev", "test", "stage", "prod"],
  6: ["sandbox", "dev", "test", "uat", "stage", "prod"],
};

/** The answers compared with a template, labelled as the questionnaire shows them; identity fields are left out. */
const COMPARED_ANSWERS: Array<[keyof LandingZoneAnswers, string]> = [
  ["home_region", "Home region"], ["governed_regions", "Governed regions"], ["environment_ids", "Environments"],
  ["environment_names", "Environment names"], ["grouping", "OU grouping"], ["account_model", "Accounts per environment"],
  ["compliance", "Compliance scopes"], ["security_tooling", "Security Tooling account"],
  ["log_retention_days", "Log retention"], ["infrastructure", "Shared infrastructure"], ["network", "Network"],
  ["sandbox", "Sandbox"], ["optional_ous", "Other OUs"], ["controls_profile", "Controls profile"],
  ["control_packs", "Control packs"], ["pack_parameters", "Pack parameters"],
];

/**
 * Immutable model of the landing zone questionnaire plus the OU tree editor's changes, in order.
 * Defaults are the platform's recommendations; the edits survive answer changes and are replayed by the platform.
 */
export class LandingZoneDraft {
  private constructor(private readonly answers: LandingZoneAnswers, private readonly treeEdits: TreeEdit[],
                      readonly provider: string = "aws") {}

  static initial(): LandingZoneDraft {
    return new LandingZoneDraft({
      organization_name: "", provider_answers: { management_email: "" }, home_region: "us-east-1", governed_regions: ["us-east-1", "us-east-2"],
      template: null, environment_ids: [...ENVIRONMENT_PRESETS[5]], environment_names: {}, grouping: "separate",
      account_model: "portfolio", compliance: [],
      security_tooling: true, log_retention_days: 365,
      infrastructure: ["network", "shared_services", "identity", "backup", "monitoring"],
      network: { hub: true, egress: "central", inspection: true, on_premises: "none", cidr: "10.0.0.0/8", flows: [] },
      sandbox: { model: "team", monthly_budget_usd: 500, expiry_days: 30 },
      optional_ous: ["exceptions", "suspended"], controls_profile: "recommended", control_packs: null, pack_parameters: {},
    }, []);
  }

  /** A design read back from the repository; answers it predates take the recommendations. */
  static fromRequest(request: LandingZoneRequest): LandingZoneDraft {
    return new LandingZoneDraft({ ...LandingZoneDraft.initial().answers, ...request.answers }, request.edits,
      request.provider ?? "aws");
  }

  static environmentCatalog(): LandingZoneEnvironment[] {
    return ENVIRONMENT_CATALOG;
  }

  /** The template's answers and OU edits on top of the recommendations, keeping the organization already entered. */
  withTemplate(template: IndustryTemplate): LandingZoneDraft {
    const { answers } = LandingZoneDraft.initial().keepingOrganization(this);
    return new LandingZoneDraft({ ...answers, ...template.answers, template: { id: template.id, version: template.version } },
      template.edits, this.provider);
  }

  /** Another cloud: its own answers (empty) and default regions; the organization name and the rest carry over. */
  withProvider(provider: CloudProviderInfo): LandingZoneDraft {
    if (provider.id === this.provider) return this;
    const { primary, secondary } = provider.default_regions;
    return new LandingZoneDraft({ ...this.answers, provider_answers: { ...cloudText(provider.id).emptyAnswers },
      home_region: primary, governed_regions: [primary, secondary] }, this.treeEdits, provider.id);
  }

  withProviderAnswer(name: string, value: string): LandingZoneDraft {
    return this.with({ provider_answers: { ...this.answers.provider_answers, [name]: value } });
  }

  providerAnswer(name: string): string {
    return String(this.answers.provider_answers[name] ?? "");
  }

  fromScratch(): LandingZoneDraft {
    return LandingZoneDraft.initial().keepingOrganization(this);
  }

  /** Labels of the answers, and "OU structure" for the edits, that differ from the template's. */
  differencesFrom(template: IndustryTemplate): string[] {
    const original = this.withTemplate(template);
    const changed = COMPARED_ANSWERS.filter(([key]) => !same(this.answers[key], original.answers[key]))
      .map(([, label]) => label);
    return same(this.treeEdits, original.treeEdits) ? changed : [...changed, "OU structure"];
  }

  with(change: Partial<LandingZoneAnswers>): LandingZoneDraft {
    return new LandingZoneDraft({ ...this.answers, ...change }, this.treeEdits, this.provider);
  }

  withEdit(edit: TreeEdit): LandingZoneDraft {
    return new LandingZoneDraft(this.answers, [...this.treeEdits, edit], this.provider);
  }

  withoutEdit(index: number): LandingZoneDraft {
    return new LandingZoneDraft(this.answers, this.treeEdits.filter((_, position) => position !== index), this.provider);
  }

  edits(): TreeEdit[] {
    return this.treeEdits;
  }

  withOrganization(organizationName: string, managementEmail: string) {
    return this.with({ organization_name: organizationName,
      provider_answers: { ...this.answers.provider_answers, management_email: managementEmail } });
  }

  /** The AWS management account email, among the provider answers. */
  managementEmail(): string {
    return String(this.answers.provider_answers.management_email ?? "");
  }

  withRegion(region: string, governed: boolean) {
    return this.with({ governed_regions: toggled(this.answers.governed_regions, region, governed) });
  }

  withEnvironmentPreset(preset: EnvironmentPreset) {
    return this.withEnvironments(ENVIRONMENT_PRESETS[preset]);
  }

  /** STAGE and PROD stay in every design; removing another environment drops its rename and flows. */
  withEnvironment(environmentId: string, included: boolean) {
    if (REQUIRED_ENVIRONMENTS.includes(environmentId)) return this;
    return this.withEnvironments(toggled(this.answers.environment_ids, environmentId, included));
  }

  /** The preset the chosen environments match, if any. */
  preset(): EnvironmentPreset | undefined {
    const presets = Object.entries(ENVIRONMENT_PRESETS) as unknown as Array<[string, string[]]>;
    const match = presets.find(([, ids]) => same(ids, this.answers.environment_ids));
    return match ? (Number(match[0]) as EnvironmentPreset) : undefined;
  }

  withControlPacks(packs: string[]) {
    return this.with({ control_packs: packs });
  }

  /** A profile brings its own packs, so an explicit pack choice is dropped. */
  withProfile(profile: ControlsProfile) {
    return this.with({ controls_profile: profile, control_packs: null });
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
    const { environment_ids, environment_names } = this.answers;
    return ENVIRONMENT_CATALOG.filter((environment) => environment_ids.includes(environment.id))
      .map((environment) => ({ ...environment, name: environment_names[environment.id] ?? environment.name }));
  }

  /** Checks the browser can make; the platform validates the rest when it proposes the structure. */
  problems(): string[] {
    const { organization_name, governed_regions, home_region, provider_answers } = this.answers;
    const name = ORGANIZATION_NAME_PATTERN.test(organization_name)
      ? [] : ["Organization name: 2–31 lowercase letters, digits or hyphens."];
    const regions: Array<[boolean, string]> = [
      [governed_regions.length < MINIMUM_GOVERNED_REGIONS, "Choose at least two governed regions."],
      [!governed_regions.includes(home_region), "The home region must be a governed region."],
    ];
    return [...name, ...cloudText(this.provider).answerProblems(provider_answers),
      ...regions.filter(([failed]) => failed).map(([, message]) => message)];
  }

  toAnswers(): LandingZoneAnswers {
    return this.answers;
  }

  toRequest(): LandingZoneRequest {
    return { provider: this.provider, answers: this.answers, edits: this.treeEdits };
  }

  private withEnvironments(ids: string[]) {
    const known = new Set(ids);
    const names = Object.entries(this.answers.environment_names).filter(([id]) => known.has(id));
    const flows = this.answers.network.flows.filter((flow) => known.has(flow.source) && known.has(flow.destination));
    const ordered = ENVIRONMENT_CATALOG.map((environment) => environment.id).filter((id) => known.has(id));
    return this.with({ environment_ids: ordered, environment_names: Object.fromEntries(names) }).withNetwork({ flows });
  }

  /** The organization name, the cloud and its answers and regions carry over to a template or a fresh start. */
  private keepingOrganization(source: LandingZoneDraft) {
    const { organization_name, provider_answers, home_region, governed_regions } = source.answers;
    return new LandingZoneDraft({ ...this.answers, organization_name, provider_answers, home_region, governed_regions },
      this.treeEdits, source.provider);
  }
}

function same(left: unknown, right: unknown): boolean {
  return JSON.stringify(left) === JSON.stringify(right);
}

function toggled<T extends string>(items: T[], item: string, included: boolean): T[] {
  if (!included) return items.filter((existing) => existing !== item);
  return items.includes(item as T) ? items : [...items, item as T];
}
