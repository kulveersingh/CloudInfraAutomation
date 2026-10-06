import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { Identity, PlatformApiPort, TreeEdit } from "../../api/types";
import { fakeApi, landingZoneDesign, landingZoneDetail, OTHER_CLOUD, PACK_CATALOG, PROPOSAL, READ_BACK } from "../../test/fakes";
import { renderWithApi } from "../../test/render";
import { LandingZonePage } from "./LandingZonePage";

const ADMIN: Identity = { name: "riley", label: "Riley", roles: ["platform-admin"] };
const REVIEWER: Identity = { name: "sam", label: "Sam", roles: ["reviewer"] };
const user = () => userEvent.setup();

function renderPage(api: PlatformApiPort = fakeApi(), identity: Identity = ADMIN) {
  return renderWithApi(<LandingZonePage identity={identity} />, api);
}

async function goTo(step: string) {
  await user().click(within(screen.getByRole("navigation", { name: "Questionnaire steps" })).getByRole("button", { name: step }));
}

async function fillOrganization() {
  await screen.findByRole("heading", { name: "Start from a template" });
  await goTo("Organization");
  await user().type(await screen.findByLabelText("Organization name"), "acme");
  await user().type(screen.getByLabelText("Management account email"), "aws@acme.example");
}

function lastRequest(api: PlatformApiPort) {
  return vi.mocked(api.proposeLandingZone).mock.calls.at(-1)![0];
}

function lastAnswers(api: PlatformApiPort) {
  return lastRequest(api).answers;
}

async function propose(api: PlatformApiPort) {
  await goTo("Review");
  await user().click(screen.getByRole("button", { name: "Propose structure" }));
  return lastAnswers(api);
}

describe("LandingZonePage", () => {
  it("is only for platform admins", () => {
    renderPage(fakeApi(), REVIEWER);
    expect(screen.getByText("Only platform admins can design the landing zone.")).toBeInTheDocument();
  });

  it("opens on the Start step", async () => {
    renderPage();
    expect(await screen.findByRole("heading", { name: "Start from a template" })).toBeInTheDocument();
  });

  it("moves through the steps with Continue and Back", async () => {
    renderPage();
    await screen.findByRole("heading", { name: "Start from a template" });
    await user().click(screen.getByRole("button", { name: "Continue" }));
    expect(screen.getByRole("heading", { name: "1. Organization" })).toBeInTheDocument();
    await user().click(screen.getByRole("button", { name: "Back" }));
    expect(screen.getByRole("heading", { name: "Start from a template" })).toBeInTheDocument();
  });

  it("governs any region and picks the home region", async () => {
    const api = fakeApi();
    renderPage(api);
    await fillOrganization();
    await user().click(screen.getByLabelText("Govern ap-southeast-2"));
    await user().selectOptions(screen.getByLabelText("Home region"), "us-east-2");
    const answers = await propose(api);
    expect([answers.governed_regions, answers.home_region]).toEqual([["us-east-1", "us-east-2", "ap-southeast-2"], "us-east-2"]);
  });

  it("recommends five environments kept separate", async () => {
    renderPage();
    await goTo("Environments");
    expect([screen.getByRole("button", { name: /5 environments/ }), screen.getByRole("button", { name: /Keep every environment separate/ })]
      .map((button) => [button.getAttribute("aria-pressed"), button.textContent?.includes("Recommended")])).toEqual(
      [["true", true], ["true", true]]);
  });

  it("chooses six environments and renames one", async () => {
    const api = fakeApi();
    renderPage(api);
    await fillOrganization();
    await goTo("Environments");
    await user().click(screen.getByRole("button", { name: /6 environments/ }));
    await user().clear(screen.getByLabelText("Name for uat"));
    await user().type(screen.getByLabelText("Name for uat"), "ACCEPT");
    const answers = await propose(api);
    expect([answers.environment_ids, answers.environment_names]).toEqual(
      [["sandbox", "dev", "test", "uat", "stage", "prod"], { uat: "ACCEPT" }]);
  });

  it("warns when Prod and NonProd parents are chosen", async () => {
    renderPage();
    await goTo("Environments");
    await user().click(screen.getByRole("button", { name: /Two parents: Prod and NonProd/ }));
    expect(screen.getByText(/Not recommended/)).toBeInTheDocument();
  });

  it("chooses the account model", async () => {
    const api = fakeApi();
    renderPage(api);
    await fillOrganization();
    await goTo("Accounts");
    await user().click(screen.getByRole("button", { name: /One per product per environment/ }));
    expect((await propose(api)).account_model).toBe("product");
  });

  it("answers security and compliance questions", async () => {
    const api = fakeApi();
    renderPage(api);
    await fillOrganization();
    await goTo("Security & compliance");
    await user().click(screen.getByLabelText("Add a Security Tooling account"));
    await user().selectOptions(screen.getByLabelText("Central log retention"), "2555");
    await user().click(screen.getByLabelText("PCI"));
    const answers = await propose(api);
    expect([answers.security_tooling, answers.log_retention_days, answers.compliance]).toEqual([false, 2555, ["PCI"]]);
  });

  it("chooses shared infrastructure accounts", async () => {
    const api = fakeApi();
    renderPage(api);
    await fillOrganization();
    await goTo("Shared infrastructure");
    await user().click(screen.getByLabelText("CI/CD Automations"));
    await user().click(screen.getByLabelText("Monitoring"));
    expect((await propose(api)).infrastructure).toEqual(["network", "shared_services", "identity", "backup", "cicd"]);
  });

  it("answers the network questions", async () => {
    const api = fakeApi();
    renderPage(api);
    await fillOrganization();
    await goTo("Network");
    await user().click(screen.getByRole("button", { name: /Isolated VPCs only/ }));
    await user().clear(screen.getByLabelText("Organization CIDR"));
    await user().type(screen.getByLabelText("Organization CIDR"), "172.16.0.0/12");
    await user().selectOptions(screen.getByLabelText("Internet egress"), "local");
    await user().selectOptions(screen.getByLabelText("On-premises connection"), "vpn");
    await user().click(screen.getByLabelText("Inspect traffic with AWS Network Firewall"));
    const { network } = await propose(api);
    expect([network.hub, network.cidr, network.egress, network.on_premises, network.inspection]).toEqual(
      [false, "172.16.0.0/12", "local", "vpn", false]);
  });

  it("adds and removes a cross-environment exception", async () => {
    const api = fakeApi();
    renderPage(api);
    await fillOrganization();
    await goTo("Network");
    await user().selectOptions(screen.getByLabelText("Flow source"), "dev");
    await user().selectOptions(screen.getByLabelText("Flow destination"), "test");
    await user().selectOptions(screen.getByLabelText("Flow protocol"), "udp");
    await user().clear(screen.getByLabelText("Flow port"));
    await user().type(screen.getByLabelText("Flow port"), "514");
    await user().type(screen.getByLabelText("Flow reason"), "Syslog");
    await user().click(screen.getByRole("button", { name: "Add exception" }));
    await user().click(screen.getByRole("button", { name: "Add exception" }));
    await user().click(screen.getByRole("button", { name: "Remove flow 2" }));
    expect((await propose(api)).network.flows).toEqual([
      { source: "dev", destination: "test", protocol: "udp", port: 514, reason: "Syslog" }]);
  });

  it("offers only non-sandbox environments for flows", async () => {
    renderPage();
    await goTo("Network");
    expect(within(screen.getByLabelText("Flow source")).queryByRole("option", { name: "Sandbox" })).toBeNull();
  });

  it("answers the sandbox and optional OU questions", async () => {
    const api = fakeApi();
    renderPage(api);
    await fillOrganization();
    await goTo("Sandbox & other OUs");
    await user().selectOptions(screen.getByLabelText("Sandbox accounts"), "developer");
    await user().clear(screen.getByLabelText("Monthly budget per account (USD)"));
    await user().type(screen.getByLabelText("Monthly budget per account (USD)"), "250");
    await user().clear(screen.getByLabelText("Resource expiry (days)"));
    await user().type(screen.getByLabelText("Resource expiry (days)"), "14");
    await user().click(screen.getByLabelText("Individual Business Users"));
    const answers = await propose(api);
    expect([answers.sandbox, answers.optional_ous]).toEqual([
      { model: "developer", monthly_budget_usd: 250, expiry_days: 14 },
      ["exceptions", "suspended", "individual_business_users"]]);
  });

  it("chooses the controls profile", async () => {
    const api = fakeApi();
    renderPage(api);
    await fillOrganization();
    await goTo("Controls");
    await user().click(screen.getByRole("button", { name: /Regulated/ }));
    expect((await propose(api)).controls_profile).toBe("regulated");
  });

  it("lists answer problems instead of proposing", async () => {
    renderPage();
    await goTo("Review");
    expect([screen.getByText("Enter the management account email."),
      screen.getByRole("button", { name: "Propose structure" })]).toEqual([expect.anything(), expect.toBeDisabled()]);
  });

  it("shows the proposed OU structure with accounts", async () => {
    const api = fakeApi();
    renderPage(api);
    await fillOrganization();
    await propose(api);
    const tree = screen.getByRole("tree", { name: "Proposed OU structure" });
    expect([within(tree).getByText("PROD OU"), within(tree).getByText("acme-payments-prod"), within(tree).getByText("DEV OU")])
      .toHaveLength(3);
  });

  it("shows the proposed diagram", async () => {
    const api = fakeApi();
    renderPage(api);
    await fillOrganization();
    await propose(api);
    expect(screen.getByRole("img", { name: "Proposed OU structure diagram" }).getAttribute("src")).toMatch(/^data:image\/svg\+xml/);
  });

  it("opens a generated file", async () => {
    const api = fakeApi();
    renderPage(api);
    await fillOrganization();
    await propose(api);
    await user().click(screen.getByRole("button", { name: "stacks/lz-structure.yaml" }));
    expect(screen.getByLabelText("File content")).toHaveTextContent("Resources: {}");
  });

  it("shows problems the platform found", async () => {
    const api = fakeApi({ proposeLandingZone: vi.fn().mockResolvedValue({ ...PROPOSAL, problems: ["OU 'PROD' would have 6 SCPs."] }) });
    renderPage(api);
    await fillOrganization();
    await propose(api);
    expect([screen.getByText("OU 'PROD' would have 6 SCPs."), screen.getByRole("button", { name: "Request approval" })])
      .toEqual([expect.anything(), expect.toBeDisabled()]);
  });

  it("shows propose errors", async () => {
    const api = fakeApi({ proposeLandingZone: vi.fn().mockRejectedValue(new Error("Hub-and-spoke networking needs the Network account.")) });
    renderPage(api);
    await fillOrganization();
    await propose(api);
    expect(screen.getByRole("alert")).toHaveTextContent("needs the Network account");
  });

  it("requests approval: saves, submits and opens the approvals tab", async () => {
    const api = fakeApi();
    renderPage(api);
    await fillOrganization();
    await propose(api);
    await user().click(screen.getByRole("button", { name: "Request approval" }));
    expect([vi.mocked(api.submitLandingZoneDesign).mock.calls[0][0], screen.getByRole("status").textContent,
      screen.getByRole("tab", { name: "Approvals" }).getAttribute("aria-selected")]).toEqual(
      ["lz-1", "Design v1 submitted. A different platform admin must approve it.", "true"]);
  });

  it("shows request errors", async () => {
    const api = fakeApi({ createLandingZoneDesign: vi.fn().mockRejectedValue(new Error("forbidden")) });
    renderPage(api);
    await fillOrganization();
    await propose(api);
    await user().click(screen.getByRole("button", { name: "Request approval" }));
    expect(screen.getByRole("alert")).toHaveTextContent("forbidden");
  });

  describe("industry templates", () => {
    async function chooseTemplate(name: string) {
      await user().click(await screen.findByRole("button", { name: new RegExp(name) }));
    }

    it("lists the templates with their frameworks, environments and control counts", async () => {
      renderPage();
      const saas = await screen.findByRole("button", { name: /SaaS & technology/ });
      expect([saas.textContent?.includes("SSAE-18-SOC-2-Oct-2023"), saas.textContent?.includes("Sandbox · DEV · STAGE · PROD"),
        saas.textContent?.includes("50 controls (130 enablements)"),
        saas.textContent?.includes("intended alignment (unverified)")]).toEqual([true, true, true, true]);
    });

    it("marks frameworks verified once the catalog is refreshed", async () => {
      renderPage();
      expect((await screen.findByRole("button", { name: /Financial services/ })).textContent).not.toContain("unverified");
    });

    it("recommends starting from scratch when no template fits", async () => {
      renderPage();
      expect(await screen.findByRole("button", { name: /Start from scratch/ })).toHaveAttribute("aria-pressed", "true");
    });

    it("fills in the questionnaire and OU edits from the chosen template", async () => {
      const api = fakeApi();
      renderPage(api);
      await chooseTemplate("SaaS & technology");
      await fillOrganization();
      await propose(api);
      const request = lastRequest(api);
      expect([vi.mocked(api.landingZoneTemplate).mock.calls[0][0], request.answers.template, request.answers.environment_ids,
        request.edits]).toEqual(["saas", { id: "saas", version: 1 }, ["sandbox", "dev", "stage", "prod"],
        [{ op: "add_ou", parent: "prod", name: "Tenants" }]]);
    });

    it("goes back to starting from scratch", async () => {
      const api = fakeApi();
      renderPage(api);
      await chooseTemplate("SaaS & technology");
      await screen.findByRole("button", { name: /SaaS & technology/, pressed: true });
      await user().click(screen.getByRole("button", { name: /Start from scratch/ }));
      await fillOrganization();
      expect((await propose(api)).template).toBeNull();
    });

    it("shows the template and what changed from it on the Review step", async () => {
      const api = fakeApi();
      renderPage(api);
      await chooseTemplate("SaaS & technology");
      await fillOrganization();
      await goTo("Environments");
      await user().click(screen.getByLabelText("Include QA"));
      await goTo("Review");
      expect([screen.getByText("Based on SaaS & technology v1"), screen.getByText("Changed: Environments")]).toHaveLength(2);
    });

    it("resets to the template", async () => {
      const api = fakeApi();
      renderPage(api);
      await chooseTemplate("SaaS & technology");
      await fillOrganization();
      await goTo("Environments");
      await user().click(screen.getByLabelText("Include QA"));
      await goTo("Review");
      await user().click(screen.getByRole("button", { name: "Reset to template" }));
      expect([screen.queryByText(/^Changed:/), (await propose(api)).organization_name]).toEqual([null, "acme"]);
    });

    it("shows template loading errors", async () => {
      renderPage(fakeApi({ landingZoneTemplates: vi.fn().mockRejectedValue(new Error("catalog down")) }));
      expect(await screen.findByRole("alert")).toHaveTextContent("catalog down");
    });

    it("shows template errors", async () => {
      renderPage(fakeApi({ landingZoneTemplate: vi.fn().mockRejectedValue(new Error("gone")) }));
      await chooseTemplate("SaaS & technology");
      expect(await screen.findByRole("alert")).toHaveTextContent("gone");
    });
  });

  describe("environment combinations", () => {
    it("adds environments from the catalog", async () => {
      const api = fakeApi();
      renderPage(api);
      await fillOrganization();
      await goTo("Environments");
      await user().click(screen.getByLabelText("Include QA"));
      await user().click(screen.getByLabelText("Include PERF"));
      expect((await propose(api)).environment_ids).toEqual(["sandbox", "dev", "qa", "test", "perf", "stage", "prod"]);
    });

    it("always includes STAGE and PROD", async () => {
      renderPage();
      await screen.findByRole("heading", { name: "Start from a template" });
      await goTo("Environments");
      expect([screen.getByLabelText("Include STAGE"), screen.getByLabelText("Include PROD")]).toEqual(
        [expect.toBeDisabled(), expect.toBeDisabled()]);
    });

    it("shows no preset as chosen for a custom combination", async () => {
      renderPage();
      await screen.findByRole("heading", { name: "Start from a template" });
      await goTo("Environments");
      await user().click(screen.getByLabelText("Include QA"));
      expect(screen.queryAllByRole("button", { name: /environments/, pressed: true })).toHaveLength(0);
    });
  });

  describe("control packs", () => {
    async function openControls(api: PlatformApiPort = fakeApi()) {
      renderPage(api);
      await fillOrganization();
      await goTo("Controls");
      await screen.findByLabelText("Use Foundation");
      return api;
    }

    it("shows the profile's packs as chosen", async () => {
      await openControls();
      expect([screen.getByLabelText("Use Foundation"), screen.getByLabelText("Use PCI cardholder data environment")])
        .toEqual([expect.toBeChecked(), expect.not.toBeChecked()]);
    });

    it("describes each pack's targets, controls and frameworks", async () => {
      await openControls();
      const pci = screen.getByRole("group", { name: "PCI cardholder data environment" });
      expect([within(pci).getByText("Targets: compliance:PCI"), within(pci).getByText("1 preventive · 0 detective · 0 proactive"),
        within(pci).getByText("Frameworks: PCI-DSS-v4.0")]).toHaveLength(3);
    });

    it("says when framework mappings have not been refreshed", async () => {
      await openControls();
      const foundation = screen.getByRole("group", { name: "Foundation" });
      expect(within(foundation).getByText("Frameworks: not refreshed yet")).toBeInTheDocument();
    });

    it("says when a refreshed pack maps to no framework", async () => {
      await openControls(fakeApi({ controlPacks: vi.fn().mockResolvedValue({ ...PACK_CATALOG, mappings_refreshed: "2026-10-04" }) }));
      expect(within(screen.getByRole("group", { name: "Foundation" })).getByText("Frameworks: none mapped")).toBeInTheDocument();
    });

    it("lists a pack's controls", async () => {
      await openControls();
      const foundation = screen.getByRole("group", { name: "Foundation" });
      expect(within(foundation).getByText("Disallow actions as a root user")).toBeInTheDocument();
    });

    it("adds and removes packs", async () => {
      const api = await openControls();
      await user().click(screen.getByLabelText("Use PCI cardholder data environment"));
      await user().click(screen.getByLabelText("Use Foundation"));
      expect((await propose(api)).control_packs).toEqual(["data-protection", "pci-cde"]);
    });

    it("goes back to a profile's packs when a profile is chosen", async () => {
      const api = await openControls();
      await user().click(screen.getByLabelText("Use Foundation"));
      await user().click(screen.getByRole("button", { name: /Regulated/ }));
      expect([screen.getByLabelText("Use PCI cardholder data environment"), (await propose(api)).control_packs])
        .toEqual([expect.toBeChecked(), null]);
    });

    it("warns when a template's pack is turned off", async () => {
      renderPage();
      await user().click(await screen.findByRole("button", { name: /SaaS & technology/ }));
      await screen.findByRole("button", { name: /SaaS & technology/, pressed: true });
      await goTo("Controls");
      await user().click(await screen.findByLabelText("Use Foundation"));
      expect(screen.getByText(/Foundation is part of the SaaS & technology template/)).toHaveTextContent(
        "aligned with SSAE-18-SOC-2-Oct-2023, CIS-v8.0");
    });

    it("shows pack loading errors", async () => {
      renderPage(fakeApi({ controlPacks: vi.fn().mockRejectedValue(new Error("no packs")) }));
      await screen.findByRole("heading", { name: "Start from a template" });
      await goTo("Controls");
      expect(await screen.findByRole("alert")).toHaveTextContent("no packs");
    });
  });

  describe("controls and warnings on the proposal", () => {
    it("counts the controls on each OU", async () => {
      const api = fakeApi();
      renderPage(api);
      await fillOrganization();
      await propose(api);
      expect([within(screen.getByRole("tree")).getByText("2 controls"), within(screen.getByRole("tree")).getByText("1 control")])
        .toHaveLength(2);
    });

    it("shows warnings without blocking approval", async () => {
      const api = fakeApi({ proposeLandingZone: vi.fn().mockResolvedValue({ ...PROPOSAL, warnings: ["Refresh the catalog."] }) });
      renderPage(api);
      await fillOrganization();
      await propose(api);
      expect([screen.getByText("Refresh the catalog."), screen.getByRole("button", { name: "Request approval" })]).toEqual(
        [expect.anything(), expect.not.toBeDisabled()]);
    });
  });

  describe("OU tree editor", () => {
    async function proposed(api: PlatformApiPort = fakeApi()) {
      renderPage(api);
      await fillOrganization();
      await propose(api);
      return api;
    }

    async function lastEdits(api: PlatformApiPort) {
      await vi.waitFor(() => expect(api.proposeLandingZone).toHaveBeenCalledTimes(2));
      return lastRequest(api).edits;
    }

    const button = (name: string) => screen.getByRole("button", { name });

    it("adds an OU under an environment and proposes again", async () => {
      const api = await proposed();
      await user().click(button("Add OU under PROD"));
      await user().type(screen.getByLabelText("New OU name"), "Data");
      await user().click(button("Add OU"));
      expect(await lastEdits(api)).toEqual([{ op: "add_ou", parent: "prod", name: "Data" }]);
    });

    it("adds an OU at the root", async () => {
      const api = await proposed();
      await user().click(button("Add OU at the root"));
      await user().type(screen.getByLabelText("New OU name"), "Data Lab");
      await user().click(button("Add OU"));
      expect(await lastEdits(api)).toEqual([{ op: "add_ou", parent: null, name: "Data Lab" }]);
    });

    it("adds an account", async () => {
      const api = await proposed();
      await user().click(button("Add account to PROD"));
      await user().type(screen.getByLabelText("Account suffix"), "billing-prod");
      await user().click(button("Add account"));
      expect(await lastEdits(api)).toEqual([{ op: "add_account", ou: "prod", suffix: "billing-prod" }]);
    });

    it("renames a custom OU", async () => {
      const api = await proposed();
      await user().click(button("Rename Payments"));
      await user().clear(screen.getByLabelText("New name for Payments"));
      await user().type(screen.getByLabelText("New name for Payments"), "Billing");
      await user().click(button("Save name"));
      expect(await lastEdits(api)).toEqual([{ op: "rename_ou", ou: "custom_payments", name: "Billing" }]);
    });

    it("moves a custom OU only within its isolation domain", async () => {
      const api = await proposed();
      await user().click(button("Move Payments"));
      const targets = within(screen.getByLabelText("Move Payments to")).getAllByRole("option").map((option) => option.textContent);
      await user().click(button("Move"));
      expect([targets, await lastEdits(api)]).toEqual([["Cards"], [{ op: "move_ou", ou: "custom_payments", parent: "custom_cards" }]]);
    });

    it("removes an empty custom OU", async () => {
      const api = await proposed();
      await user().click(button("Remove Payments"));
      expect(await lastEdits(api)).toEqual([{ op: "remove_ou", ou: "custom_payments" }]);
    });

    it("asks to move accounts out before an OU can be removed", async () => {
      await proposed();
      expect([button("Remove Cards"), screen.getByText("Move its accounts and child OUs to another OU first.")]).toEqual(
        [expect.toBeDisabled(), expect.anything()]);
    });

    it("offers only the edits each OU and account allows", async () => {
      await proposed();
      expect(["Add OU under Security", "Rename PROD", "Remove PROD", "Disable acme-audit", "Move acme-network"]
        .map((name) => screen.queryByRole("button", { name }))).toEqual([null, null, null, null, null]);
    });

    it("disables a generated workload account instead of removing it", async () => {
      const api = await proposed();
      expect(screen.queryByRole("button", { name: "Remove acme-payments-prod" })).toBeNull();
      await user().click(button("Disable acme-payments-prod"));
      expect(await lastEdits(api)).toEqual([{ op: "disable_account", account: "acme-payments-prod" }]);
    });

    it("marks and re-enables a disabled account", async () => {
      const api = await proposed();
      expect(within(screen.getByRole("tree")).getByText("Disabled")).toBeInTheDocument();
      await user().click(button("Enable acme-retail-dev"));
      expect(await lastEdits(api)).toEqual([{ op: "enable_account", account: "acme-retail-dev" }]);
    });

    it("removes an account added in the editor", async () => {
      const api = await proposed();
      await user().click(button("Remove acme-cards-prod"));
      expect(await lastEdits(api)).toEqual([{ op: "remove_account", account: "acme-cards-prod" }]);
    });

    it("moves an account within its environment", async () => {
      const api = await proposed();
      await user().click(button("Move acme-payments-prod"));
      await user().selectOptions(screen.getByLabelText("Move acme-payments-prod to"), "custom_cards");
      await user().click(button("Move"));
      expect(await lastEdits(api)).toEqual([{ op: "move_account", account: "acme-payments-prod", ou: "custom_cards" }]);
    });

    it("hides Move when there is nowhere in the domain to go", async () => {
      await proposed();
      expect(screen.queryByRole("button", { name: "Move acme-retail-dev" })).toBeNull();
    });

    it("lists the manual changes in plain words", async () => {
      const api = await proposed();
      await user().click(button("Add OU under PROD"));
      await user().type(screen.getByLabelText("New OU name"), "Data");
      await user().click(button("Add OU"));
      await lastEdits(api);
      const changes = screen.getByRole("list", { name: "Manual changes" });
      expect([screen.getByText("Manual changes (1)"), within(changes).getByText("Added OU Data under PROD")])
        .toHaveLength(2);
    });

    it("undoes a manual change and proposes again", async () => {
      const api = await proposed();
      await user().click(button("Disable acme-payments-prod"));
      await lastEdits(api);
      await user().click(button("Undo change 1"));
      await vi.waitFor(() => expect(api.proposeLandingZone).toHaveBeenCalledTimes(3));
      expect(lastRequest(api).edits).toEqual([]);
    });

    it("keeps the edits when the questionnaire is revisited", async () => {
      const api = await proposed();
      await user().click(button("Disable acme-payments-prod"));
      await lastEdits(api);
      await goTo("Controls");
      expect(await propose(api)).toBeDefined();
      expect(lastRequest(api).edits).toEqual([{ op: "disable_account", account: "acme-payments-prod" }]);
    });

    it("requests approval with the edits", async () => {
      const api = await proposed();
      await user().click(button("Disable acme-payments-prod"));
      await lastEdits(api);
      await user().click(button("Request approval"));
      expect(vi.mocked(api.createLandingZoneDesign).mock.calls[0][0].edits).toEqual(
        [{ op: "disable_account", account: "acme-payments-prod" }]);
    });

    it("describes every kind of change", async () => {
      const edits: TreeEdit[] = [
        { op: "add_ou", parent: null, name: "Data Lab" }, { op: "rename_ou", ou: "custom_payments", name: "Billing" },
        { op: "move_ou", ou: "custom_payments", parent: "custom_cards" }, { op: "remove_ou", ou: "custom_old" },
        { op: "add_account", ou: "prod", suffix: "billing-prod" }, { op: "enable_account", account: "acme-retail-dev" },
        { op: "remove_account", account: "acme-cards-prod" },
        { op: "move_account", account: "acme-payments-prod", ou: "custom_cards" }];
      const api = fakeApi({ landingZoneDesign: vi.fn().mockResolvedValue(landingZoneDetail({ edits })) });
      renderPage(api);
      await user().click(await screen.findByRole("tab", { name: "Approvals" }));
      await user().click(await screen.findByRole("button", { name: "View v1" }));
      const changes = await screen.findByRole("list", { name: "Manual changes" });
      expect(within(changes).getAllByRole("listitem").map((item) => item.textContent)).toEqual([
        "Added OU Data Lab at the root", "Renamed Payments to Billing", "Moved Billing under Cards",
        "Removed OU custom_old", "Added account billing-prod to PROD", "Enabled acme-retail-dev",
        "Removed acme-cards-prod", "Moved acme-payments-prod to Cards"]);
    });
  });

  describe("approvals", () => {
    async function openApprovals(api: PlatformApiPort = fakeApi()) {
      renderPage(api);
      await user().click(await screen.findByRole("tab", { name: "Approvals" }));
      await screen.findByText("acme");
      return api;
    }

    it("lists designs with their status", async () => {
      await openApprovals();
      expect(screen.getByText("Awaiting second admin")).toBeInTheDocument();
    });

    it("approves with a comment and shows the approved structure", async () => {
      const api = await openApprovals();
      await user().type(screen.getByLabelText("Comment for v1"), "Looks right");
      await user().click(screen.getByRole("button", { name: "Approve v1" }));
      expect([vi.mocked(api.approveLandingZoneDesign).mock.calls[0], screen.getByRole("status").textContent]).toEqual(
        [["lz-1", "Looks right"], "Design v1 applied. Committed to acme-platform/landing-zone-infra."]);
      expect(await screen.findByRole("img", { name: "Approved OU structure diagram" })).toBeInTheDocument();
    });

    it("rejects with a comment", async () => {
      const api = await openApprovals();
      await user().type(screen.getByLabelText("Comment for v1"), "Add PCI");
      await user().click(screen.getByRole("button", { name: "Reject v1" }));
      expect(vi.mocked(api.rejectLandingZoneDesign).mock.calls[0]).toEqual(["lz-1", "Add PCI"]);
    });

    it("shows the reason an approval was refused", async () => {
      await openApprovals(fakeApi({ approveLandingZoneDesign: vi.fn().mockRejectedValue(
        new Error("You submitted this design, so a different platform admin must decide on it.")) }));
      await user().click(screen.getByRole("button", { name: "Approve v1" }));
      expect(screen.getByRole("alert")).toHaveTextContent("a different platform admin");
    });

    it("views an applied design with its diagram, repository and accounts", async () => {
      const applied = { status: "applied" as const, repository: "acme-platform/landing-zone-infra",
        accounts: { a: "111111111111", b: "222222222222" }, decided_by: "riley" };
      const api = fakeApi({ landingZoneDesigns: vi.fn().mockResolvedValue([landingZoneDesign(applied)]),
        landingZoneDesign: vi.fn().mockResolvedValue(landingZoneDetail(applied)) });
      await openApprovals(api);
      await user().click(screen.getByRole("button", { name: "View v1" }));
      expect([await screen.findByRole("img", { name: "Approved OU structure diagram" }),
        screen.getByText("acme-platform/landing-zone-infra"), screen.getByText("2 accounts")]).toHaveLength(3);
    });

    it("views a pending design as proposed", async () => {
      await openApprovals();
      await user().click(screen.getByRole("button", { name: "View v1" }));
      expect(await screen.findByRole("img", { name: "Proposed OU structure diagram" })).toBeInTheDocument();
    });

    it("hides decisions for designs that are no longer pending", async () => {
      await openApprovals(fakeApi({ landingZoneDesigns: vi.fn().mockResolvedValue([landingZoneDesign({ status: "rejected" })]) }));
      expect(screen.queryByRole("button", { name: "Approve v1" })).toBeNull();
    });

    it("shows view errors", async () => {
      await openApprovals(fakeApi({ landingZoneDesign: vi.fn().mockRejectedValue(new Error("gone")) }));
      await user().click(screen.getByRole("button", { name: "View v1" }));
      expect(await screen.findByRole("alert")).toHaveTextContent("gone");
    });

    it("shows loading errors", async () => {
      renderPage(fakeApi({ landingZoneDesigns: vi.fn().mockRejectedValue(new Error("down")) }));
      await user().click(await screen.findByRole("tab", { name: "Approvals" }));
      expect(await screen.findByRole("alert")).toHaveTextContent("down");
    });

    it("says when there are no designs yet", async () => {
      renderPage(fakeApi({ landingZoneDesigns: vi.fn().mockResolvedValue([]) }));
      await user().click(await screen.findByRole("tab", { name: "Approvals" }));
      expect(await screen.findByText("No landing zone designs yet.")).toBeInTheDocument();
    });
  });

  describe("editing the current landing zone", () => {
    const HAND_EDITED = {
      ...READ_BACK, verified: false, request: null,
      findings: [{ check: "integrity", severity: "blocking" as const,
        message: "Files were edited outside the platform. Revert them in GitHub, or change the design here.",
        files: [{ path: "stacks/lz-structure.yaml", diff: "--- generated/stacks/lz-structure.yaml\n+# tweaked\n" },
          { path: "design.json", diff: null }] }],
    };

    async function editCurrent() {
      await user().click(await screen.findByRole("button", { name: /Edit the current landing zone/ }));
    }

    it("loads the committed design into the questionnaire and opens Review", async () => {
      const api = fakeApi();
      renderPage(api);
      await editCurrent();
      expect(await screen.findByRole("heading", { name: "9. Review the proposed structure" })).toBeInTheDocument();
      await user().click(screen.getByRole("button", { name: "Propose structure" }));
      expect(lastRequest(api)).toEqual(READ_BACK.request);
    });

    it("says which version and commit it loaded", async () => {
      renderPage();
      await editCurrent();
      expect(await screen.findByText("Loaded design v3 from landing-zone-infra at abcdef1.")).toBeInTheDocument();
    });

    it("shows warnings about the repository", async () => {
      renderPage(fakeApi({ landingZoneReadBack: vi.fn().mockResolvedValue({ ...READ_BACK, findings: [
        { check: "head", severity: "warning", message: "The repository has commits the platform did not make.", files: [] }] }) }));
      await editCurrent();
      expect(await screen.findByText("The repository has commits the platform did not make.")).toBeInTheDocument();
    });

    it("refuses a hand-edited repository and shows the changes", async () => {
      const api = fakeApi({ landingZoneReadBack: vi.fn().mockResolvedValue(HAND_EDITED) });
      renderPage(api);
      await editCurrent();
      const panel = await screen.findByRole("region", { name: "The landing zone repository can't be loaded" });
      expect([within(panel).getByText(/Files were edited outside the platform/), within(panel).getByText("stacks/lz-structure.yaml"),
        within(panel).getByText(/\+# tweaked/), within(panel).getByText("design.json"),
        screen.getByRole("heading", { name: "Start from a template" })]).toHaveLength(5);
    });

    it("keeps the draft when the repository is refused", async () => {
      const api = fakeApi({ landingZoneReadBack: vi.fn().mockResolvedValue(HAND_EDITED) });
      renderPage(api);
      await editCurrent();
      await screen.findByRole("region", { name: "The landing zone repository can't be loaded" });
      await fillOrganization();
      expect((await propose(api)).log_retention_days).toBe(365);
    });

    it("shows read-back errors", async () => {
      renderPage(fakeApi({ landingZoneReadBack: vi.fn().mockRejectedValue(new Error("No landing zone has been applied yet.")) }));
      await editCurrent();
      expect(await screen.findByRole("alert")).toHaveTextContent("No landing zone has been applied yet.");
    });
  });

  describe("in another cloud's words", () => {
    const api = () => fakeApi({ providers: vi.fn().mockResolvedValue(OTHER_CLOUD) });

    it("names the units, structure and IaC as the cloud does", async () => {
      renderPage(api());
      const units = await screen.findByRole("button", { name: "Subscriptions" });
      await goTo("Review");
      expect([units, screen.getByText(/proposes the management group structure from your answers and generates the Bicep file\./)])
        .toEqual([expect.anything(), expect.anything()]);
    });

    it("titles the controls step with the cloud's control catalog", async () => {
      renderPage(api());
      await screen.findByRole("button", { name: "Subscriptions" });
      await goTo("Controls");
      expect(screen.getByRole("heading", { name: "8. Azure Policy initiatives" })).toBeInTheDocument();
    });
  });
});
