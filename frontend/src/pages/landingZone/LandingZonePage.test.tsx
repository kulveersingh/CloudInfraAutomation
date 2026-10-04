import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { Identity, PlatformApiPort } from "../../api/types";
import { fakeApi, landingZoneDesign, landingZoneDetail, PROPOSAL } from "../../test/fakes";
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
  await user().type(await screen.findByLabelText("Organization name"), "acme");
  await user().type(screen.getByLabelText("Management account email"), "aws@acme.example");
}

function lastAnswers(api: PlatformApiPort) {
  return vi.mocked(api.proposeLandingZone).mock.calls.at(-1)![0];
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

  it("opens on the organization step", async () => {
    renderPage();
    expect(await screen.findByRole("heading", { name: "1. Organization" })).toBeInTheDocument();
  });

  it("moves through the steps with Continue and Back", async () => {
    renderPage();
    await screen.findByLabelText("Organization name");
    await user().click(screen.getByRole("button", { name: "Continue" }));
    expect(screen.getByRole("heading", { name: "2. Environments" })).toBeInTheDocument();
    await user().click(screen.getByRole("button", { name: "Back" }));
    expect(screen.getByRole("heading", { name: "1. Organization" })).toBeInTheDocument();
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
    expect([answers.environment_count, answers.environment_names]).toEqual([6, { uat: "ACCEPT" }]);
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
});
