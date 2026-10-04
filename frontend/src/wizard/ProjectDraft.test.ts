import { describe, expect, it } from "vitest";
import { ProjectDraft } from "./ProjectDraft";

const ready = () => ProjectDraft.initial()
  .withName("demo-app")
  .withOwnership("pf-payments", "pr-invoicing")
  .withEnvironment("dev", true)
  .withResource("s3.bucket");

describe("ProjectDraft", () => {
  it("starts empty with single-region defaults", () => {
    expect(ProjectDraft.initial().values).toMatchObject({
      name: "", mode: "single", primaryRegion: "us-east-1", secondaryRegion: "us-east-2", resources: [] });
  });

  it("is immutable", () => {
    const draft = ProjectDraft.initial();
    draft.withName("demo-app");
    expect(draft.values.name).toBe("");
  });

  it("derives resource ids from the type", () => {
    expect(ready().values.resources[0]).toEqual({ id: "bucket", type: "s3.bucket", properties: {} });
  });

  it("derives resource ids from CloudFormation types", () => {
    expect(ProjectDraft.initial().withResource("AWS::SNS::Topic").values.resources[0].id).toBe("topic");
  });

  it("keeps resource ids unique", () => {
    const ids = ready().withResource("s3.bucket").withResource("s3.bucket").values.resources.map((r) => r.id);
    expect(ids).toEqual(["bucket", "bucket2", "bucket3"]);
  });

  it("removing a resource removes its connections", () => {
    const draft = ready().withResource("lambda.function")
      .withConnection({ kind: "event.notify", source: "bucket", target: "function" })
      .withoutResource("bucket");
    expect([draft.values.resources.length, draft.values.connections.length]).toEqual([1, 0]);
  });

  it("removing a connection target removes the connection but keeps unrelated ones", () => {
    const draft = ready().withResource("lambda.function").withResource("sqs.queue")
      .withConnection({ kind: "iam.access", source: "function", target: "bucket", access: "read" })
      .withConnection({ kind: "iam.access", source: "function", target: "queue", access: "write" })
      .withoutResource("bucket");
    expect(draft.values.connections.map((connection) => connection.target)).toEqual(["queue"]);
  });

  it("setting properties leaves other resources unchanged", () => {
    const draft = ready().withResource("AWS::SNS::Topic").withResourceProperties("topic", { DisplayName: "A" });
    expect(draft.values.resources[0].properties).toEqual({});
  });

  it("stores properties for a resource", () => {
    const draft = ready().withResourceProperties("bucket", { Foo: 1 });
    expect(draft.values.resources[0].properties).toEqual({ Foo: 1 });
  });

  it("removes a connection by position", () => {
    const draft = ready().withConnection({ kind: "iam.access", source: "a", target: "b", access: "read" })
      .withoutConnection(0);
    expect(draft.values.connections).toEqual([]);
  });

  it("toggles environments", () => {
    expect(ready().withEnvironment("prod", true).withEnvironment("dev", false).values.environments)
      .toEqual(["prod"]);
  });

  it("enabling an environment twice keeps one entry", () => {
    expect(ready().withEnvironment("dev", true).values.environments).toEqual(["dev"]);
  });

  it("sets classification, mode and regions", () => {
    const values = ready().withClassification("confidential").withMode("dr").withPrimary("us-west-2")
      .withSecondary("eu-west-1").values;
    expect([values.classification, values.mode, values.primaryRegion, values.secondaryRegion])
      .toEqual(["confidential", "dr", "us-west-2", "eu-west-1"]);
  });

  it("has no problems when complete", () => {
    expect(ready().problems()).toEqual([]);
  });

  it("reports what is missing", () => {
    expect(ProjectDraft.initial().problems()).toEqual([
      "Enter a project name: 3–30 lowercase letters, digits and single hyphens.",
      "Choose a portfolio and product.",
      "Select at least one environment.",
      "Add at least one service.",
    ]);
  });

  it("requires distinct regions for DR and HA", () => {
    expect(ready().withMode("ha").withSecondary("us-east-1").problems())
      .toEqual(["Choose two different regions for the DR/HA pair."]);
  });

  it("builds a single-region request", () => {
    expect(ready().toRequest()).toEqual({
      project_name: "demo-app",
      ownership: { portfolio_id: "pf-payments", product_id: "pr-invoicing", data_classification: "internal" },
      resilience: { mode: "single", primary_region: "us-east-1", secondary_region: null },
      environments: ["dev"],
      resources: [{ id: "bucket", type: "s3.bucket" }],
      connections: [],
      network: { attach_compute: true, selections: {} },
    });
  });

  it("includes the secondary region and properties when set", () => {
    const request = ready().withMode("dr").withResourceProperties("bucket", { Foo: 1 }).toRequest();
    expect([request.resilience.secondary_region, request.resources[0].config]).toEqual([
      "us-east-2", { properties: { Foo: 1 } }]);
  });

  it("can detach compute from the VPC", () => {
    expect(ready().withAttachCompute(false).toRequest().network.attach_compute).toBe(false);
  });

  it("records a network choice per environment and region", () => {
    expect(ready().withNetworkSelection("prod", "us-east-1", "net-9").toRequest().network.selections)
      .toEqual({ "prod:us-east-1": "net-9" });
  });

  it("deploys lower environments to the primary region only", () => {
    expect(ready().withMode("dr").regionsFor("dev")).toEqual(["us-east-1"]);
  });

  it("deploys stage and prod to both regions for DR and HA", () => {
    expect(ready().withMode("ha").regionsFor("prod")).toEqual(["us-east-1", "us-east-2"]);
  });

  it("deploys everything to the primary region for single-region projects", () => {
    expect(ready().regionsFor("prod")).toEqual(["us-east-1"]);
  });
});
