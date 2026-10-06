import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { Identity, PlatformApiPort } from "../../api/types";
import { cloudText } from "../../landingZone/cloudText";
import { LandingZoneDraft } from "../../landingZone/LandingZoneDraft";
import { fakeApi, GCP_PACK_CATALOG, GCP_PROVIDER, READ_BACK } from "../../test/fakes";
import { renderWithApi } from "../../test/render";
import { LandingZonePage } from "./LandingZonePage";

const ADMIN: Identity = { name: "riley", label: "Riley", roles: ["platform-admin"] };
const user = () => userEvent.setup();

function renderPage(api: PlatformApiPort = fakeApi()) {
  return renderWithApi(<LandingZonePage identity={ADMIN} />, api);
}

async function goTo(step: string) {
  await user().click(within(screen.getByRole("navigation", { name: "Questionnaire steps" })).getByRole("button", { name: step }));
}

async function chooseGoogleCloud() {
  await user().selectOptions(await screen.findByLabelText("Cloud"), "gcp");
}

async function fillGoogleCloud() {
  await chooseGoogleCloud();
  await goTo("Organization");
  await user().type(screen.getByLabelText("Organization name"), "acme");
  await user().type(screen.getByLabelText("Organization id"), "123456789012");
  await user().type(screen.getByLabelText("Billing account"), "01ABCD-23EF45-67GH89");
  await user().type(screen.getByLabelText("Domain"), "acme.example");
}

const lastRequest = (api: PlatformApiPort) => vi.mocked(api.proposeLandingZone).mock.calls.at(-1)![0];

describe("the landing zone's cloud", () => {
  it("starts on AWS and offers only the clouds that have a landing zone", async () => {
    renderPage();
    const cloud = await screen.findByLabelText("Cloud");
    expect([cloud, within(cloud).getAllByRole("option").map((option) => option.textContent)]).toEqual(
      [expect.objectContaining({ value: "aws" }), ["Amazon Web Services", "Google Cloud"]]);
  });

  it("loads the chosen cloud's templates", async () => {
    const api = fakeApi();
    renderPage(api);
    await chooseGoogleCloud();
    expect(vi.mocked(api.landingZoneTemplates).mock.calls.at(-1)).toEqual(["gcp"]);
  });

  it("asks Google Cloud's questions and offers its regions", async () => {
    renderPage();
    await chooseGoogleCloud();
    await goTo("Organization");
    expect([screen.queryByLabelText("Management account email"), screen.getByLabelText("Security Command Center tier"),
      screen.getByLabelText("Home region"), screen.getByLabelText("Govern europe-west1"),
      screen.getByText(/new folders, projects and policies under an existing Google Cloud organization/)]).toEqual([
      null, expect.anything(), expect.objectContaining({ value: "us-east1" }), expect.anything(), expect.anything()]);
  });

  it("checks Google Cloud's answers before proposing", async () => {
    renderPage();
    await chooseGoogleCloud();
    await goTo("Review");
    expect([screen.getByText("Enter the organization id: digits only."),
      screen.getByText("Enter the billing account: XXXXXX-XXXXXX-XXXXXX."),
      screen.getByText("Enter the organization's domain.")]).toHaveLength(3);
  });

  it("proposes with Google Cloud's provider answers", async () => {
    const api = fakeApi();
    renderPage(api);
    await fillGoogleCloud();
    await user().selectOptions(screen.getByLabelText("Security Command Center tier"), "standard");
    await goTo("Review");
    await user().click(screen.getByRole("button", { name: "Propose structure" }));
    expect([lastRequest(api).provider, lastRequest(api).answers.provider_answers, lastRequest(api).answers.governed_regions])
      .toEqual(["gcp", { organization_id: "123456789012", billing_account: "01ABCD-23EF45-67GH89", domain: "acme.example",
        scc_tier: "standard" }, ["us-east1", "us-east4"]]);
  });

  it("says how Google Cloud creates projects and what the review generates", async () => {
    renderPage();
    await chooseGoogleCloud();
    await goTo("Projects");
    const accounts = screen.getByText(/created by the platform's Terraform/);
    await goTo("Review");
    expect([accounts, screen.getByText(/proposes the folder structure from your answers and generates the Terraform /),
      screen.queryByText(/Control Tower Account Factory|CloudFormation/)]).toEqual([expect.anything(), expect.anything(), null]);
  });

  it("speaks of folders and projects", async () => {
    renderPage();
    await chooseGoogleCloud();
    const steps = within(screen.getByRole("navigation", { name: "Questionnaire steps" }));
    expect([steps.getByRole("button", { name: "Projects" }), steps.getByRole("button", { name: "Sandbox & other folders" })])
      .toHaveLength(2);
  });

  it("describes Google Cloud's shared projects, without an Identity project", async () => {
    renderPage();
    await chooseGoogleCloud();
    await goTo("Shared infrastructure");
    expect([screen.getByText(/Network Connectivity Center hub/), screen.queryByLabelText("Identity"),
      screen.getByText(/locked buckets and Backup and DR vaults/)]).toEqual([expect.anything(), null, expect.anything()]);
  });

  it("offers Google Cloud's network options", async () => {
    renderPage();
    await chooseGoogleCloud();
    await goTo("Network");
    const egress = within(screen.getByLabelText("Internet egress")).getAllByRole("option").map((option) => option.textContent);
    expect([egress, screen.getByRole("option", { name: "Cloud Interconnect" }),
      screen.getByLabelText("Inspect traffic with Cloud NGFW"), screen.getByText("Hub and spoke (Network Connectivity Center)")])
      .toEqual([["Cloud NAT in each environment's VPC"], expect.anything(), expect.anything(), expect.anything()]);
  });

  it("describes Google Cloud's Security folder", async () => {
    renderPage();
    await chooseGoogleCloud();
    await goTo("Security & compliance");
    expect(screen.getByText(/exactly one Security folder/)).toBeInTheDocument();
  });

  it("lists Google Cloud's controls and their gaps", async () => {
    const api = fakeApi({ controlPacks: vi.fn().mockResolvedValue(GCP_PACK_CATALOG) });
    renderPage(api);
    await chooseGoogleCloud();
    await goTo("Organization");
    await user().selectOptions(screen.getByLabelText("Security Command Center tier"), "standard");
    await goTo("Controls");
    expect([await screen.findByText(/Google Cloud has no proactive controls/),
      screen.getByText(/Detective controls are not deployed: Security Command Center Standard/),
      vi.mocked(api.controlPacks).mock.calls.at(-1)]).toEqual([expect.anything(), expect.anything(), ["gcp"]]);
  });

  it("reads back the chosen cloud's landing zone", async () => {
    const api = fakeApi({ landingZoneReadBack: vi.fn().mockResolvedValue({ ...READ_BACK,
      request: { ...READ_BACK.request!, provider: "gcp" } }) });
    renderPage(api);
    await chooseGoogleCloud();
    await user().click(screen.getByRole("button", { name: /Edit the current landing zone/ }));
    expect([vi.mocked(api.landingZoneReadBack).mock.calls[0], await screen.findByText(/from landing-zone-gcp-infra/)])
      .toEqual([["gcp"], expect.anything()]);
  });

  it("keeps the organization name when switching clouds, and takes the new cloud's regions", () => {
    const draft = LandingZoneDraft.initial().withOrganization("acme", "aws@acme.example").withProvider(GCP_PROVIDER);
    expect([draft.provider, draft.toAnswers().organization_name, draft.toAnswers().home_region,
      draft.toAnswers().provider_answers]).toEqual(["gcp", "acme", "us-east1",
      { organization_id: "", billing_account: "", domain: "", scc_tier: "premium" }]);
  });

  it("choosing the same cloud keeps the draft", () => {
    const draft = LandingZoneDraft.initial();
    expect(draft.withProvider({ ...GCP_PROVIDER, id: "aws" })).toBe(draft);
  });

  it("deploys detective controls on Premium", async () => {
    renderPage(fakeApi({ controlPacks: vi.fn().mockResolvedValue(GCP_PACK_CATALOG) }));
    await chooseGoogleCloud();
    await goTo("Controls");
    expect([await screen.findByText(/Google Cloud has no proactive controls/),
      screen.queryByText(/Detective controls are not deployed/)]).toEqual([expect.anything(), null]);
  });

  it("reads back a design saved before designs named their cloud as AWS's", async () => {
    const { provider: _provider, ...older } = READ_BACK.request!;
    renderPage(fakeApi({ landingZoneReadBack: vi.fn().mockResolvedValue({ ...READ_BACK, request: older }) }));
    await user().click(await screen.findByRole("button", { name: /Edit the current landing zone/ }));
    expect(await screen.findByText(/from landing-zone-infra at/)).toBeInTheDocument();
  });

  it("an answer the cloud hasn't been given is empty", () => {
    expect(LandingZoneDraft.initial().providerAnswer("organization_id")).toBe("");
  });

  it("a cloud without its own wording uses AWS's", () => {
    expect(cloudText("azure").repository).toBe("landing-zone-infra");
  });
});
