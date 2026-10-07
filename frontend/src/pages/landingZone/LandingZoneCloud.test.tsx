import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { Identity, PlatformApiPort } from "../../api/types";
import { cloudText } from "../../landingZone/cloudText";
import { LandingZoneDraft } from "../../landingZone/LandingZoneDraft";
import { AZURE_PROVIDER, fakeApi, GCP_PACK_CATALOG, GCP_PROVIDER, PROVIDERS, READ_BACK } from "../../test/fakes";
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
  it("starts on AWS and offers every cloud that has a landing zone", async () => {
    renderPage();
    const cloud = await screen.findByLabelText("Cloud");
    expect([cloud, within(cloud).getAllByRole("option").map((option) => option.textContent)]).toEqual(
      [expect.objectContaining({ value: "aws" }), ["Amazon Web Services", "Google Cloud", "Azure"]]);
  });

  it("leaves out a cloud whose landing zone is still to come", async () => {
    const later = { ...AZURE_PROVIDER, id: "oracle", name: "Oracle Cloud", landing_zone: false };
    renderPage(fakeApi({ providers: vi.fn().mockResolvedValue([...PROVIDERS, later]) }));
    const cloud = await screen.findByLabelText("Cloud");
    expect(within(cloud).queryByRole("option", { name: "Oracle Cloud" })).toBeNull();
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
      screen.queryAllByText(/Control Tower Account Factory|CloudFormation/).map((element) => element.outerHTML)]).toEqual([expect.anything(), expect.anything(), []]);
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
    expect(cloudText("oracle").repository).toBe("landing-zone-infra");
  });
});

describe("the Azure landing zone", () => {
  const TENANT = "8f2dd843-51d9-41e0-a23f-09119ffed634";
  const SCOPE = "/providers/Microsoft.Billing/billingAccounts/1234567/enrollmentAccounts/7654321";
  const GROUPS = { platform_admins: "11111111-1111-4111-8111-111111111111",
    network_admins: "22222222-2222-4222-8222-222222222222", security_admins: "33333333-3333-4333-8333-333333333333",
    backup_super_users: "44444444-4444-4444-8444-444444444444" };
  const LABELS: Record<string, string> = { platform_admins: "Platform admins group", network_admins: "Network admins group",
    security_admins: "Security admins group", backup_super_users: "Backup super users group" };

  async function chooseAzure() {
    await user().selectOptions(await screen.findByLabelText("Cloud"), "azure");
  }

  async function fillAzure() {
    await chooseAzure();
    await goTo("Organization");
    await user().type(screen.getByLabelText("Organization name"), "acme");
    await user().type(screen.getByLabelText("Tenant id"), TENANT);
    await user().type(screen.getByLabelText("Billing scope"), SCOPE);
    for (const [role, id] of Object.entries(GROUPS)) await user().type(screen.getByLabelText(LABELS[role]), id);
  }

  it("asks Azure's questions and offers its regions", async () => {
    renderPage();
    await chooseAzure();
    await goTo("Organization");
    expect([screen.queryByLabelText("Management account email"), screen.getByLabelText("Defender for Cloud"),
      screen.getByLabelText("Azure Firewall tier"), screen.getByLabelText("Home region"),
      screen.getByLabelText("Govern westeurope"), screen.getByText(/subscription names and management group ids/),
      screen.getByText(/existing Microsoft Entra tenant/)]).toEqual([null, expect.anything(),
      expect.anything(), expect.objectContaining({ value: "eastus2" }), expect.anything(), expect.anything(), expect.anything()]);
  });

  it("checks Azure's answers before proposing", async () => {
    renderPage();
    await chooseAzure();
    await goTo("Review");
    expect([screen.getByText("Enter the tenant id: a GUID."),
      screen.getByText("Enter the billing scope: an EA enrollment account or an MCA invoice section."),
      screen.getByText("Enter the Platform admins group's object id: a GUID."),
      screen.getByText("Enter the Backup super users group's object id: a GUID.")]).toHaveLength(4);
  });

  it("proposes with Azure's provider answers, groups included", async () => {
    const api = fakeApi();
    renderPage(api);
    await fillAzure();
    await user().selectOptions(screen.getByLabelText("Defender for Cloud"), "standard");
    await user().selectOptions(screen.getByLabelText("Azure Firewall tier"), "premium");
    await goTo("Review");
    await user().click(screen.getByRole("button", { name: "Propose structure" }));
    expect([lastRequest(api).provider, lastRequest(api).answers.provider_answers, lastRequest(api).answers.governed_regions])
      .toEqual(["azure", { tenant_id: TENANT, billing_scope: SCOPE, groups: GROUPS, defender: "standard",
        firewall_tier: "premium" }, ["eastus2", "centralus"]]);
  });

  it("speaks of management groups and subscriptions", async () => {
    renderPage();
    await chooseAzure();
    const steps = within(screen.getByRole("navigation", { name: "Questionnaire steps" }));
    await goTo("Subscriptions");
    const accounts = screen.getByText(/created against your billing scope/);
    await goTo("Review");
    expect([steps.getByRole("button", { name: "Sandbox & other management groups" }), accounts,
      screen.getByText(/proposes the management group structure from your answers and generates the ARM template/)])
      .toHaveLength(3);
  });

  it("describes Azure's shared subscriptions", async () => {
    renderPage();
    await chooseAzure();
    await goTo("Shared infrastructure");
    expect([screen.getByText(/Hubs with Azure Firewall, gateways and private DNS zones/),
      screen.getByText(/Only for AD DS domain controllers/), screen.getByText(/locked Backup vaults/)]).toHaveLength(3);
  });

  it("offers Azure's network options", async () => {
    renderPage();
    await chooseAzure();
    await goTo("Network");
    const egress = within(screen.getByLabelText("Internet egress")).getAllByRole("option").map((option) => option.textContent);
    expect([egress, screen.getByRole("option", { name: "ExpressRoute" }), screen.getByText("Hub and spoke (Azure Firewall)")])
      .toEqual([["Through the hub's Azure Firewall (recommended)", "NAT gateway in each spoke"], expect.anything(),
        expect.anything()]);
  });

  it("describes Azure's Security management group and controls", async () => {
    const api = fakeApi();
    renderPage(api);
    await chooseAzure();
    await goTo("Security & compliance");
    const security = screen.getByText(/exactly one Security management group/);
    await goTo("Organization");
    await user().selectOptions(screen.getByLabelText("Defender for Cloud"), "standard");
    await goTo("Controls");
    expect([security, await screen.findByText(/Azure has no proactive controls/),
      screen.getByText(/Defender plans are billed per subscription/), vi.mocked(api.controlPacks).mock.calls.at(-1)])
      .toEqual([expect.anything(), expect.anything(), expect.anything(), ["azure"]]);
  });

  it("reads back the Azure landing zone", async () => {
    const api = fakeApi({ landingZoneReadBack: vi.fn().mockResolvedValue({ ...READ_BACK,
      request: { ...READ_BACK.request!, provider: "azure" } }) });
    renderPage(api);
    await chooseAzure();
    await user().click(screen.getByRole("button", { name: /Edit the current landing zone/ }));
    expect(await screen.findByText(/from landing-zone-azure-infra/)).toBeInTheDocument();
  });

  it("starts Azure with empty answers and its default regions", () => {
    const draft = LandingZoneDraft.initial().withProvider(AZURE_PROVIDER);
    expect([draft.toAnswers().provider_answers, draft.toAnswers().home_region, draft.group("platform_admins")]).toEqual([
      { tenant_id: "", billing_scope: "", groups: { platform_admins: "", network_admins: "", security_admins: "",
        backup_super_users: "" }, defender: "foundational", firewall_tier: "standard" }, "eastus2", ""]);
  });

  it("a group the cloud hasn't been given is empty", () => {
    expect(LandingZoneDraft.initial().group("platform_admins")).toBe("");
  });
});
