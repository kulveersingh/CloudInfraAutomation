import { describe, expect, it } from "vitest";
import { SAAS_TEMPLATE } from "../test/fakes";
import { LandingZoneDraft } from "./LandingZoneDraft";

const FLOW = { source: "dev", destination: "test", protocol: "tcp" as const, port: 5432, reason: "Data refresh" };
const ADD_OU = { op: "add_ou" as const, parent: "prod", name: "Payments" };
const DISABLE = { op: "disable_account" as const, account: "acme-retail-prod" };
const named = () => LandingZoneDraft.initial().withOrganization("acme", "aws@acme.example");

describe("LandingZoneDraft", () => {
  it("starts with the platform's recommendations", () => {
    const answers = LandingZoneDraft.initial().toAnswers();
    expect([answers.environment_ids.length, answers.grouping, answers.account_model, answers.controls_profile,
      answers.network.egress, answers.governed_regions]).toEqual(
      [5, "separate", "portfolio", "recommended", "central", ["us-east-1", "us-east-2"]]);
  });

  it("is immutable", () => {
    const draft = LandingZoneDraft.initial();
    draft.withOrganization("acme", "aws@acme.example");
    expect(draft.toAnswers().organization_name).toBe("");
  });

  it("lists five environments by default", () => {
    expect(named().environments().map((environment) => environment.name)).toEqual(["Sandbox", "DEV", "TEST", "STAGE", "PROD"]);
  });

  it("folds testing into DEV with four environments", () => {
    expect(named().withEnvironmentPreset(4).environments().map((environment) => environment.id)).toEqual(
      ["sandbox", "dev", "stage", "prod"]);
  });

  it("adds UAT with six environments", () => {
    expect(named().withEnvironmentPreset(6).environments().map((environment) => environment.id)).toContain("uat");
  });

  it("renames an environment", () => {
    expect(named().withEnvironmentName("stage", "QA").environments()[3].name).toBe("QA");
  });

  it("restores the preset name when a rename is cleared", () => {
    const draft = named().withEnvironmentName("stage", "QA").withEnvironmentName("stage", "");
    expect(draft.toAnswers().environment_names).toEqual({});
  });

  it("dropping an environment drops its rename and flows", () => {
    const draft = named().withEnvironmentPreset(6).withEnvironmentName("uat", "ACCEPT")
      .withFlow({ ...FLOW, destination: "uat" }).withFlow(FLOW).withEnvironmentPreset(5);
    expect([draft.toAnswers().environment_names, draft.toAnswers().network.flows]).toEqual([{}, [FLOW]]);
  });

  it("toggles a governed region", () => {
    const draft = named().withRegion("eu-west-1", true).withRegion("us-east-2", false);
    expect(draft.toAnswers().governed_regions).toEqual(["us-east-1", "eu-west-1"]);
  });

  it("toggles list answers", () => {
    const draft = named().withListItem("compliance", "PCI", true).withListItem("optional_ous", "suspended", false);
    expect([draft.toAnswers().compliance, draft.toAnswers().optional_ous]).toEqual([["PCI"], ["exceptions"]]);
  });

  it("toggling an item that is already present keeps one copy", () => {
    expect(named().withListItem("infrastructure", "network", true).toAnswers().infrastructure.filter(
      (item) => item === "network")).toHaveLength(1);
  });

  it("changes a single answer", () => {
    expect(named().with({ grouping: "prod_nonprod" }).toAnswers().grouping).toBe("prod_nonprod");
  });

  it("changes network and sandbox answers", () => {
    const answers = named().withNetwork({ egress: "local" }).withSandbox({ monthly_budget_usd: 900 }).toAnswers();
    expect([answers.network.egress, answers.network.hub, answers.sandbox.monthly_budget_usd]).toEqual(["local", true, 900]);
  });

  it("adds and removes flows", () => {
    const draft = named().withFlow(FLOW).withFlow({ ...FLOW, port: 443 }).withoutFlow(0);
    expect(draft.toAnswers().network.flows.map((flow) => flow.port)).toEqual([443]);
  });

  it("needs an organization name and email", () => {
    expect(LandingZoneDraft.initial().problems()).toEqual([
      "Organization name: 2–31 lowercase letters, digits or hyphens.", "Enter the management account email."]);
  });

  it("needs two governed regions including the home region", () => {
    expect(named().withRegion("us-east-1", false).problems()).toEqual([
      "Choose at least two governed regions.", "The home region must be a governed region."]);
  });

  it("has no problems with valid answers", () => {
    expect(named().problems()).toEqual([]);
  });

  it("starts with no tree edits", () => {
    expect(named().toRequest()).toEqual({ answers: named().toAnswers(), edits: [] });
  });

  it("records tree edits in order", () => {
    const draft = named().withEdit(ADD_OU).withEdit(DISABLE);
    expect(draft.toRequest().edits).toEqual([ADD_OU, DISABLE]);
  });

  it("loads a design read back from the repository", () => {
    const request = named().with({ log_retention_days: 730 }).withEdit(ADD_OU).toRequest();
    expect(LandingZoneDraft.fromRequest(request).toRequest()).toEqual(request);
  });

  it("fills answers a repository design predates with the recommendations", () => {
    const { pack_parameters: _dropped, ...older } = named().toAnswers();
    expect(LandingZoneDraft.fromRequest({ answers: older as never, edits: [] }).toAnswers().pack_parameters).toEqual({});
  });

  it("undoes one tree edit", () => {
    expect(named().withEdit(ADD_OU).withEdit(DISABLE).withoutEdit(0).edits()).toEqual([DISABLE]);
  });

  it("adds any catalog environment in pipeline order", () => {
    expect(named().withEnvironment("qa", true).withEnvironment("perf", true).toAnswers().environment_ids).toEqual(
      ["sandbox", "dev", "qa", "test", "perf", "stage", "prod"]);
  });

  it("removes an environment with its renames and flows", () => {
    const draft = named().withEnvironmentName("test", "INT").withFlow(FLOW).withEnvironment("test", false);
    expect([draft.toAnswers().environment_ids, draft.toAnswers().environment_names, draft.toAnswers().network.flows])
      .toEqual([["sandbox", "dev", "stage", "prod"], {}, []]);
  });

  it("always keeps STAGE and PROD", () => {
    expect(named().withEnvironment("prod", false).toAnswers().environment_ids).toContain("prod");
  });

  it("knows which preset the environments match", () => {
    expect([named().preset(), named().withEnvironmentPreset(4).preset(), named().withEnvironment("qa", true).preset()])
      .toEqual([5, 4, undefined]);
  });

  it("lists the environment catalog", () => {
    expect(LandingZoneDraft.environmentCatalog().map((environment) => environment.id)).toEqual(
      ["sandbox", "dev", "qa", "test", "uat", "perf", "stage", "prod"]);
  });

  it("chooses control packs and goes back to the profile's packs", () => {
    const chosen = named().withControlPacks(["foundation"]);
    expect([chosen.toAnswers().control_packs, chosen.withProfile("regulated").toAnswers()]).toEqual(
      [["foundation"], expect.objectContaining({ control_packs: null, controls_profile: "regulated" })]);
  });

  it("starts from a template, keeping the organization", () => {
    const answers = named().withTemplate(SAAS_TEMPLATE).toRequest();
    expect([answers.answers.organization_name, answers.answers.template, answers.answers.environment_ids,
      answers.answers.grouping, answers.edits]).toEqual(["acme", { id: "saas", version: 1 },
      ["sandbox", "dev", "stage", "prod"], "separate", SAAS_TEMPLATE.edits]);
  });

  it("starts from scratch, keeping the organization", () => {
    const draft = named().withTemplate(SAAS_TEMPLATE).withEdit(ADD_OU).fromScratch();
    expect([draft.toAnswers().organization_name, draft.toAnswers().template, draft.edits(), draft.preset()]).toEqual(
      ["acme", null, [], 5]);
  });

  it("has no differences from the template it just started from", () => {
    expect(named().withTemplate(SAAS_TEMPLATE).differencesFrom(SAAS_TEMPLATE)).toEqual([]);
  });

  it("names what differs from the template", () => {
    const draft = named().withTemplate(SAAS_TEMPLATE).with({ grouping: "prod_nonprod" }).withEnvironment("qa", true)
      .withEdit(DISABLE);
    expect(draft.differencesFrom(SAAS_TEMPLATE)).toEqual(["Environments", "OU grouping", "OU structure"]);
  });

  it("keeps tree edits when an answer changes", () => {
    expect(named().withEdit(ADD_OU).with({ grouping: "prod_nonprod" }).edits()).toEqual([ADD_OU]);
  });
});
