import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "../../api/PlatformApi";
import type { Identity, PlatformApiPort } from "../../api/types";
import { fakeApi, pipeline, release } from "../../test/fakes";
import { renderWithApi } from "../../test/render";
import { ReleaseConsolePage } from "./ReleaseConsolePage";

const SAM: Identity = { name: "sam", label: "Sam Patel · Reviewer", roles: ["reviewer"] };
const JORDAN: Identity = { name: "jordan", label: "Jordan Lee · Developer", roles: ["developer"] };
const JORDAN_REVIEWER: Identity = { name: "jordan", label: "Jordan", roles: ["reviewer"] };
const ALEX: Identity = { name: "alex", label: "Alex Kim · Platform admin", roles: ["platform-admin", "reviewer"] };
const user = () => userEvent.setup();

function renderConsole(identity: Identity = SAM, api: PlatformApiPort = fakeApi()) {
  return renderWithApi(<ReleaseConsolePage identity={identity} />, api);
}

async function openInboxItem() {
  await user().click(await screen.findByRole("button", { name: "Open release rel-1" }));
}

describe("ReleaseConsolePage", () => {
  it("shows the pipeline of the first project", async () => {
    const { api } = renderConsole();
    expect(await screen.findByRole("group", { name: "QA/STAGE" })).toBeInTheDocument();
    expect(api.pipeline).toHaveBeenCalledWith("invoice-ingest");
  });

  it("shows each environment's release state", async () => {
    renderConsole();
    const stage = await screen.findByRole("group", { name: "QA/STAGE" });
    expect(within(stage).getByText("Awaiting approval")).toBeInTheDocument();
  });

  it("marks environments that need approval", async () => {
    renderConsole();
    const stage = await screen.findByRole("group", { name: "QA/STAGE" });
    expect(within(stage).getByText("approval")).toBeInTheDocument();
  });

  it("shows empty environments", async () => {
    renderConsole();
    const prod = await screen.findByRole("group", { name: "PROD" });
    expect(within(prod).getByText("No release yet")).toBeInTheDocument();
  });

  it("explains a failed gate in the pipeline", async () => {
    const api = fakeApi({ pipeline: vi.fn().mockResolvedValue(pipeline(release({ state: "gate_failed",
      gate_findings: ["Tests did not pass."] }))) });
    renderConsole(SAM, api);
    expect(await screen.findByText("Tests did not pass.")).toBeInTheDocument();
  });

  it("explains when there are no projects", async () => {
    renderConsole(SAM, fakeApi({ projects: vi.fn().mockResolvedValue([]) }));
    expect(await screen.findByText(/Create a project first/)).toBeInTheDocument();
  });

  it("switches project", async () => {
    const projects = [{ name: "invoice-ingest", portfolio_id: "pf", product_id: "pr", resilience_mode: "dr",
      status: "active" }, { name: "ledger-api", portfolio_id: "pf", product_id: "pr", resilience_mode: "ha",
      status: "active" }];
    const { api } = renderConsole(SAM, fakeApi({ projects: vi.fn().mockResolvedValue(projects) }));
    await user().selectOptions(await screen.findByLabelText("Project"), "ledger-api");
    expect(api.pipeline).toHaveBeenLastCalledWith("ledger-api");
  });

  it("lists the approval inbox", async () => {
    renderConsole();
    expect(await screen.findByRole("button", { name: "Open release rel-1" })).toBeInTheDocument();
  });

  it("shows an empty inbox", async () => {
    renderConsole(SAM, fakeApi({ inbox: vi.fn().mockResolvedValue([]) }));
    expect(await screen.findByText("Nothing is waiting for you.")).toBeInTheDocument();
  });

  it("shows loading errors", async () => {
    renderConsole(SAM, fakeApi({ projects: vi.fn().mockRejectedValue(new Error("API down")) }));
    expect(await screen.findByRole("alert")).toHaveTextContent("API down");
  });

  it("simulates a plan for an environment", async () => {
    const { api } = renderConsole();
    await user().selectOptions(await screen.findByLabelText("Environment"), "prod");
    await user().click(screen.getByLabelText("High-risk change"));
    await user().click(screen.getByRole("button", { name: "Simulate pipeline plan" }));
    expect(api.simulateRelease).toHaveBeenCalledWith("invoice-ingest", "prod", true);
  });

  it("opens the simulated release", async () => {
    renderConsole();
    await screen.findByLabelText("Environment");
    await user().click(screen.getByRole("button", { name: "Simulate pipeline plan" }));
    expect(await screen.findByRole("heading", { name: /Release rel-2/ })).toBeInTheDocument();
  });

  it("shows simulation errors", async () => {
    renderConsole(SAM, fakeApi({ simulateRelease: vi.fn().mockRejectedValue(new ApiError(422, "not enabled")) }));
    await screen.findByLabelText("Environment");
    await user().click(screen.getByRole("button", { name: "Simulate pipeline plan" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("not enabled");
  });

  it("opens a release from the pipeline", async () => {
    renderConsole();
    await user().click(await screen.findByRole("button", { name: "Open DEV release" }));
    expect(screen.getByRole("heading", { name: /Release rel-0/ })).toBeInTheDocument();
  });

  it("shows the change set with risk", async () => {
    renderConsole();
    await openInboxItem();
    const changes = screen.getByRole("table", { name: "Change set" });
    expect(within(changes).getByText("ProcessorRole")).toBeInTheDocument();
  });

  it("marks replacements", async () => {
    const risky = release({ risk: "high", state: "override_requested", changes: [{ action: "Modify",
      logical_id: "UploadsBucket", resource_type: "AWS::S3::Bucket", replacement: true, risk: "high" }] });
    renderConsole(ALEX, fakeApi({ inbox: vi.fn().mockResolvedValue([risky]) }));
    await openInboxItem();
    expect(screen.getByText("replacement")).toBeInTheDocument();
  });

  it("shows the evidence", async () => {
    renderConsole();
    await openInboxItem();
    expect(screen.getByText("Tests passed · signed · 0 critical / 0 high vulnerabilities")).toBeInTheDocument();
  });

  it("shows failing evidence", async () => {
    const failing = release({ evidence: { tests_passed: false, critical_vulnerabilities: 1, high_vulnerabilities: 2,
      signed: false } });
    renderConsole(SAM, fakeApi({ inbox: vi.fn().mockResolvedValue([failing]) }));
    await openInboxItem();
    expect(screen.getByText("Tests failed · unsigned · 1 critical / 2 high vulnerabilities")).toBeInTheDocument();
  });

  it("lets a reviewer approve and shows the result", async () => {
    const { api } = renderConsole();
    await openInboxItem();
    await user().type(screen.getByLabelText("Comment"), "ok");
    await user().click(screen.getByRole("button", { name: "Approve and release" }));
    expect(api.approveRelease).toHaveBeenCalledWith("rel-1", "ok");
    expect(await screen.findByText(/applied change set cs-4f78c64a1b2c/)).toBeInTheDocument();
  });

  it("shows the decision history", async () => {
    renderConsole();
    await openInboxItem();
    await user().click(screen.getByRole("button", { name: "Approve and release" }));
    expect(await screen.findByText("sam · approve · ok")).toBeInTheDocument();
  });

  it("lets a reviewer reject", async () => {
    const { api } = renderConsole();
    await openInboxItem();
    await user().click(screen.getByRole("button", { name: "Reject" }));
    expect(api.rejectRelease).toHaveBeenCalledWith("rel-1", "");
  });

  it("disables decisions for non-reviewers and explains why", async () => {
    renderConsole(JORDAN);
    await openInboxItem();
    expect([screen.getByRole("button", { name: "Approve and release" }).hasAttribute("disabled"),
      screen.getByText(/Only reviewers can approve/) !== null]).toEqual([true, true]);
  });

  it("does not let requesters decide on their own release", async () => {
    renderConsole(JORDAN_REVIEWER);
    await openInboxItem();
    expect(screen.getByText(/You requested this release/)).toBeInTheDocument();
  });

  it("asks a platform admin for overrides", async () => {
    const risky = release({ risk: "high", state: "override_requested" });
    const { api } = renderConsole(ALEX, fakeApi({ inbox: vi.fn().mockResolvedValue([risky]) }));
    await openInboxItem();
    await user().click(screen.getByRole("button", { name: "Approve override" }));
    expect(api.approveOverride).toHaveBeenCalledWith("rel-1", "");
  });

  it("explains that overrides need a platform admin", async () => {
    renderConsole(SAM, fakeApi({ inbox: vi.fn().mockResolvedValue([release({ state: "override_requested" })]) }));
    await openInboxItem();
    expect(screen.getByText(/Only a platform admin can approve an override/)).toBeInTheDocument();
  });

  it("shows no decisions for finished releases", async () => {
    renderConsole();
    await user().click(await screen.findByRole("button", { name: "Open DEV release" }));
    expect(screen.queryByRole("button", { name: "Approve and release" })).toBeNull();
  });

  it("shows decision errors from the server", async () => {
    renderConsole(SAM, fakeApi({ approveRelease: vi.fn().mockRejectedValue(new ApiError(409, "already decided")) }));
    await openInboxItem();
    await user().click(screen.getByRole("button", { name: "Approve and release" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("already decided");
  });

  it("closes the detail panel", async () => {
    renderConsole();
    await openInboxItem();
    await user().click(screen.getByRole("button", { name: "Close" }));
    expect(screen.queryByRole("heading", { name: /Release rel-1/ })).toBeNull();
  });
});
