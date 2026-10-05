import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { PlatformApiPort } from "../../api/types";
import { fakeApi, GCP_PREVIEW, PROJECT_READ_BACK } from "../../test/fakes";
import { renderWithApi } from "../../test/render";
import { ChangeProjectPage } from "./ChangeProjectPage";
import { NewProjectPage } from "./NewProjectPage";

const user = () => userEvent.setup();

function renderWizard(api: PlatformApiPort = fakeApi()) {
  return renderWithApi(<NewProjectPage newKey={() => "key-123"} pollMs={1} />, api);
}

async function goTo(step: string) {
  await user().click(within(screen.getByRole("navigation", { name: "Wizard steps" })).getByRole("button", { name: step }));
}

async function chooseGoogleCloud() {
  await user().selectOptions(await screen.findByLabelText("Cloud"), "gcp");
}

const options = (label: string) => within(screen.getByLabelText(label)).getAllByRole("option").map((o) => o.textContent);

describe("choosing the cloud", () => {
  it("offers every cloud the platform supports, AWS first", async () => {
    renderWizard();
    await screen.findByLabelText("Cloud");
    expect([options("Cloud"), screen.getByLabelText("Cloud")]).toEqual(
      [["Amazon Web Services", "Google Cloud"], expect.objectContaining({ value: "aws" })]);
  });

  it("uses the chosen cloud's enabled regions and default pair", async () => {
    renderWizard();
    await chooseGoogleCloud();
    await goTo("Resilience");
    expect([options("Primary region"), screen.getByLabelText("Primary region"), screen.getByText(/default us-east1 \/ us-east4/)])
      .toEqual([["europe-west1 · Belgium", "us-east1 · South Carolina", "us-east4 · Northern Virginia"],
        expect.objectContaining({ value: "us-east1" }), expect.anything()]);
  });

  it("lists the chosen cloud's curated services", async () => {
    renderWizard();
    await chooseGoogleCloud();
    await goTo("Services");
    expect([screen.getByRole("button", { name: "Add Cloud Storage bucket" }),
      screen.queryByRole("button", { name: "Add S3 bucket" })]).toEqual([expect.anything(), null]);
  });

  it("searches the chosen cloud's resource types and edits their properties", async () => {
    const api = fakeApi();
    renderWizard(api);
    await chooseGoogleCloud();
    await goTo("Services");
    await user().type(screen.getByLabelText("Search all Google Cloud resource types"), "pubsub");
    await user().click(screen.getByRole("button", { name: "Search" }));
    await user().click(await screen.findByRole("button", { name: "Add google_pubsub_schema" }));
    expect([vi.mocked(api.searchTypes).mock.calls[0], screen.getByLabelText("Properties for schema")]).toEqual(
      [["gcp", "pubsub"], expect.anything()]);
  });

  it("switching the cloud clears the services chosen for the other one", async () => {
    renderWizard();
    await screen.findByLabelText("Cloud");
    await goTo("Services");
    await user().click(await screen.findByRole("button", { name: "Add S3 bucket" }));
    await goTo("Ownership");
    await chooseGoogleCloud();
    await goTo("Services");
    expect(screen.getByText("Nothing selected yet.")).toBeInTheDocument();
  });

  it("speaks the chosen cloud's words and loads its networks", async () => {
    const api = fakeApi();
    renderWizard(api);
    await chooseGoogleCloud();
    await user().selectOptions(screen.getByLabelText("Portfolio"), "pf-payments");
    await goTo("Environments");
    await user().click(screen.getByLabelText("DEV"));
    await goTo("Network");
    expect([screen.getByText("Attach compute to the organization Shared VPC"),
      await screen.findByLabelText("Network for dev in us-east1")]).toHaveLength(2);
    expect(vi.mocked(api.networkOptions).mock.calls[0]).toEqual(["pf-payments", "gcp"]);
  });

  it("previews the chosen cloud's configuration with its notes", async () => {
    const api = fakeApi({ preview: vi.fn().mockResolvedValue(GCP_PREVIEW) });
    renderWizard(api);
    await chooseGoogleCloud();
    await user().selectOptions(screen.getByLabelText("Portfolio"), "pf-payments");
    await user().selectOptions(screen.getByLabelText("Product / Platform"), "pr-invoicing");
    await user().type(screen.getByLabelText("Project name"), "demo-app");
    await goTo("Services");
    await user().click(screen.getByRole("button", { name: "Add Cloud Storage bucket" }));
    await goTo("Environments");
    await user().click(screen.getByLabelText("DEV"));
    await goTo("Preview");
    await user().click(screen.getByRole("button", { name: "Generate preview" }));
    expect([await screen.findByText("main.tf.json"), screen.getByText(/Eventarc cannot filter by object prefix/),
      screen.getByText("Target projects"), vi.mocked(api.preview).mock.calls[0][0].provider]).toEqual(
      [expect.anything(), expect.anything(), expect.anything(), "gcp"]);
  });

  it("a change keeps the project's cloud", async () => {
    const request = { ...PROJECT_READ_BACK.request!, provider: "gcp",
      resilience: { mode: "single" as const, primary_region: "us-east1", secondary_region: null },
      resources: [{ id: "uploads", type: "storage.bucket" }], connections: [] };
    renderWithApi(<ChangeProjectPage projectName="invoice-ingest" pollMs={1} />,
      fakeApi({ projectReadBack: vi.fn().mockResolvedValue({ ...PROJECT_READ_BACK, request }) }));
    const cloud = await screen.findByLabelText("Cloud");
    expect([cloud, (cloud as HTMLSelectElement).disabled]).toEqual([expect.objectContaining({ value: "gcp" }), true]);
  });
});
