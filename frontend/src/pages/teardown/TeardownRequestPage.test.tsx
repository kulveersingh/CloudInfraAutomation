import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { PlatformApiPort } from "../../api/types";
import { fakeApi, PROJECTS, TEARDOWN_PREVIEW } from "../../test/fakes";
import { renderWithApi } from "../../test/render";
import { TeardownRequestPage } from "./TeardownRequestPage";

const user = () => userEvent.setup();

function renderRequest(api: PlatformApiPort = fakeApi(), scope: "environment" | "project" = "environment") {
  return renderWithApi(<TeardownRequestPage projectName="invoice-ingest" scope={scope} />, api);
}

async function previewIt() {
  await user().click(await screen.findByRole("button", { name: "Preview teardown" }));
}

async function confirm(text = "invoice-ingest") {
  await user().type(await screen.findByLabelText("Type invoice-ingest to confirm"), text);
}

describe("TeardownRequestPage", () => {
  it("titles an environment teardown and a decommission", async () => {
    renderRequest(fakeApi(), "project");
    expect(await screen.findByRole("heading", { name: "Decommission invoice-ingest" })).toBeInTheDocument();
  });

  it("offers the project's environments", async () => {
    renderRequest();
    expect([...(await screen.findByLabelText("Environment to tear down") as HTMLSelectElement).options].map(
      (option) => option.value)).toEqual(["dev", "prod"]);
  });

  it("previews the chosen environment", async () => {
    const api = fakeApi();
    renderRequest(api);
    await user().selectOptions(await screen.findByLabelText("Environment to tear down"), "prod");
    await previewIt();
    expect(vi.mocked(api.previewTeardown).mock.calls[0]).toEqual(["invoice-ingest", { scope: "environment", environments: ["prod"] }]);
  });

  it("previews every environment for a decommission", async () => {
    const api = fakeApi();
    renderRequest(api, "project");
    await previewIt();
    expect([vi.mocked(api.previewTeardown).mock.calls[0][1], screen.queryByLabelText("Environment to tear down")]).toEqual(
      [{ scope: "project", environments: [] }, null]);
  });

  it("explains backups, approval and what is not backed up", async () => {
    renderRequest();
    await previewIt();
    expect([await screen.findByText(/locked vault in account 999999999999 and cannot be deleted for 60 days/),
      screen.getByText("Needs approval from a reviewer"),
      screen.getByText("uploads (AWS::S3::Bucket) in us-east-1: backed up, then deleted"),
      screen.getByText("ledger (AWS::RDS::DBCluster) in us-east-1: backed up, then deleted with the stack"),
      screen.getByText("CloudWatch Logs: not supported by AWS Backup")]).toHaveLength(5);
  });

  it("says when a platform admin must approve", async () => {
    renderRequest(fakeApi({ previewTeardown: vi.fn().mockResolvedValue({ ...TEARDOWN_PREVIEW, environments: [
      { ...TEARDOWN_PREVIEW.environments[0], approver_role: "platform-admin" }] }) }));
    await previewIt();
    expect(await screen.findByText("Needs approval from a platform admin")).toBeInTheDocument();
  });

  it("requests the teardown once confirmed", async () => {
    const api = fakeApi();
    renderRequest(api);
    await previewIt();
    await confirm();
    await user().click(screen.getByRole("button", { name: "Request teardown" }));
    expect([vi.mocked(api.requestTeardown).mock.calls[0], await screen.findByText(/Each environment needs its own approval/)]).toEqual(
      [["invoice-ingest", { scope: "environment", environments: ["dev"], confirmation: "invoice-ingest" }], expect.anything()]);
  });

  it("needs the typed project name", async () => {
    renderRequest();
    await previewIt();
    await confirm("invoice");
    expect((screen.getByRole("button", { name: "Request teardown" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("needs a preview first", async () => {
    renderRequest();
    expect((await screen.findByRole("button", { name: "Request teardown" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("shows blockers and refuses to continue", async () => {
    renderRequest(fakeApi({ previewTeardown: vi.fn().mockResolvedValue({ ...TEARDOWN_PREVIEW,
      blockers: ["Change revision 2 is still open: merge or close it first."] }) }));
    await previewIt();
    await confirm();
    expect([await screen.findByText("Change revision 2 is still open: merge or close it first."),
      (screen.getByRole("button", { name: "Request teardown" }) as HTMLButtonElement).disabled]).toEqual([expect.anything(), true]);
  });

  it("shows errors", async () => {
    renderRequest(fakeApi({ previewTeardown: vi.fn().mockRejectedValue(new Error("Unknown project")) }));
    await previewIt();
    expect(await screen.findByRole("alert")).toHaveTextContent("Unknown project");
  });

  it("shows project loading errors", async () => {
    renderRequest(fakeApi({ projects: vi.fn().mockRejectedValue(new Error("API down")) }));
    expect(await screen.findByRole("alert")).toHaveTextContent("API down");
  });

  it("speaks the project's cloud", async () => {
    const preview = { ...TEARDOWN_PREVIEW, backup_account: "cloudinfra-vault", environments: [{
      ...TEARDOWN_PREVIEW.environments[0], account_id: "cloudinfra-payments-dev", regions: ["us-east1"],
      stacks: ["cloudinfra-invoice-ingest-us-east1", "cloudinfra-bootstrap-invoice-ingest"],
      data_stores: [{ service_id: "uploads", resource_type: "google_storage_bucket", physical_name: "invoice-ingest-uploads-1",
        region: "us-east1", retained: false }] }] };
    renderRequest(fakeApi({ projects: vi.fn().mockResolvedValue([{ ...PROJECTS[0], provider: "gcp" }]),
      previewTeardown: vi.fn().mockResolvedValue(preview) }));
    await previewIt();
    expect([await screen.findByText("dev · project cloudinfra-payments-dev · us-east1"),
      screen.getByText(/locked vault in project cloudinfra-vault/),
      screen.getByText("Infrastructure Manager deployments: cloudinfra-invoice-ingest-us-east1, cloudinfra-bootstrap-invoice-ingest"),
      screen.getByText("uploads (google_storage_bucket) in us-east1: backed up, then deleted with the Infrastructure Manager deployment")])
      .toHaveLength(4);
  });
});
