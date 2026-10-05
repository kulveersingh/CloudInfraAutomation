import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { PlatformApiPort } from "../../api/types";
import { CHANGE_PREVIEW, fakeApi, job, PROJECT_READ_BACK, PROJECT_REQUEST, projectChange } from "../../test/fakes";
import { renderWithApi } from "../../test/render";
import { ChangeProjectPage } from "./ChangeProjectPage";

const user = () => userEvent.setup();
const REMOVAL_PREVIEW = { ...CHANGE_PREVIEW, summary: { ...CHANGE_PREVIEW.summary,
  removed_services: [{ id: "processor", type: "lambda.function", retained: false, removal: "deleted" },
    { id: "uploads", type: "s3.bucket", retained: true, removal: "retained" },
    { id: "files", type: "storage.bucket", retained: false, removal: "deleted only if empty" }] } };

function renderChange(api: PlatformApiPort = fakeApi()) {
  return renderWithApi(<ChangeProjectPage projectName="invoice-ingest" pollMs={1} />, api);
}

async function goTo(step: string) {
  await user().click(within(await screen.findByRole("navigation", { name: "Wizard steps" })).getByRole("button", { name: step }));
}

async function previewChange() {
  await goTo("Preview");
  await user().click(screen.getByRole("button", { name: "Preview change" }));
}

describe("ChangeProjectPage", () => {
  it("reads the project back from its repository", async () => {
    const api = fakeApi();
    renderChange(api);
    expect([await screen.findByRole("heading", { name: "Change invoice-ingest" }),
      vi.mocked(api.projectReadBack).mock.calls[0][0]]).toEqual([expect.anything(), "invoice-ingest"]);
  });

  it("says which revision and commit it changes", async () => {
    renderChange();
    expect(await screen.findByText(/Changing revision 1 \(commit abcdef1\)/)).toBeInTheDocument();
  });

  it("refuses a repository that cannot be read back", async () => {
    renderChange(fakeApi({ projectReadBack: vi.fn().mockResolvedValue({ ...PROJECT_READ_BACK, verified: false,
      request: null, findings: [{ check: "integrity", severity: "blocking", message: "Files were edited outside the platform.",
        files: [{ path: "template.yaml", diff: "+edited\n" }] }] }) }));
    const panel = await screen.findByRole("region", { name: "The project repository can't be loaded" });
    expect([within(panel).getByText("Files were edited outside the platform."), within(panel).getByText("template.yaml"),
      screen.queryByRole("navigation", { name: "Wizard steps" })]).toEqual([expect.anything(), expect.anything(), null]);
  });

  it("shows read-back errors", async () => {
    renderChange(fakeApi({ projectReadBack: vi.fn().mockRejectedValue(new Error("Unknown project")) }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Unknown project");
  });

  it("locks the name, ownership and classification", async () => {
    renderChange();
    await screen.findByRole("navigation", { name: "Wizard steps" });
    expect(["Portfolio", "Product / Platform", "Project name", "Data classification"].map(
      (label) => (screen.getByLabelText(label) as HTMLInputElement).disabled)).toEqual([true, true, true, true]);
  });

  it("keeps the loaded values", async () => {
    renderChange();
    expect((await screen.findByLabelText("Project name") as HTMLInputElement).value).toBe("invoice-ingest");
  });

  it("locks the resilience mode and regions", async () => {
    renderChange();
    await goTo("Resilience");
    expect([...screen.getAllByRole("radio"), screen.getByLabelText("Primary region")].every(
      (element) => (element as HTMLInputElement).disabled)).toBe(true);
  });

  it("allows adding environments but not removing them", async () => {
    renderChange();
    await goTo("Environments");
    const [dev, prod] = [screen.getByLabelText("DEV") as HTMLInputElement, screen.getByLabelText("PROD") as HTMLInputElement];
    expect([dev.checked, dev.disabled, prod.checked, prod.disabled]).toEqual([true, true, false, false]);
  });

  it("shows the loaded settings", async () => {
    renderChange();
    await goTo("Services");
    expect((screen.getByLabelText("Memory for processor (MB)") as HTMLInputElement).value).toBe("512");
  });

  it("previews the change against the commit it was loaded at", async () => {
    const api = fakeApi();
    renderChange(api);
    await goTo("Services");
    await user().click(screen.getByRole("button", { name: "Add S3 bucket" }));
    await previewChange();
    const [name, body] = vi.mocked(api.previewChange).mock.calls[0];
    expect([name, body.base_commit, body.request.resources.map((resource) => resource.id)]).toEqual(
      ["invoice-ingest", PROJECT_READ_BACK.commit_sha, ["uploads", "processor", "bucket"]]);
  });

  it("summarises what changes", async () => {
    renderChange();
    await previewChange();
    expect([await screen.findByText("Files that change: infra.json, template.yaml"), screen.getByText("Added: bucket"),
      screen.getByText("Changed: processor")]).toHaveLength(3);
  });

  it("asks to confirm removals that delete resources", async () => {
    renderChange(fakeApi({ previewChange: vi.fn().mockResolvedValue(REMOVAL_PREVIEW) }));
    await previewChange();
    expect([await screen.findByText("processor (lambda.function): deleted"), screen.getByText("uploads (s3.bucket): retained"),
      screen.getByText("files (storage.bucket): deleted only if empty"),
      (screen.getByRole("button", { name: "Open change request" }) as HTMLButtonElement).disabled]).toEqual(
      [expect.anything(), expect.anything(), expect.anything(), true]);
  });

  it("opens the change once removals are confirmed", async () => {
    const api = fakeApi({ previewChange: vi.fn().mockResolvedValue(REMOVAL_PREVIEW) });
    renderChange(api);
    await previewChange();
    await user().click(await screen.findByLabelText("I understand the deleted resources and their data are removed"));
    await user().click(screen.getByRole("button", { name: "Open change request" }));
    expect(vi.mocked(api.createChange).mock.calls[0][1]).toEqual({ request: PROJECT_REQUEST,
      base_commit: PROJECT_READ_BACK.commit_sha, confirm_removals: true });
  });

  it("needs a preview before opening the change", async () => {
    renderChange();
    await goTo("Preview");
    expect((screen.getByRole("button", { name: "Open change request" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("follows the change job and links the pull request", async () => {
    const api = fakeApi();
    renderChange(api);
    await previewChange();
    await user().click(await screen.findByRole("button", { name: "Open change request" }));
    const link = await screen.findByRole("link", { name: "Pull request #1" });
    expect([link.getAttribute("href"), vi.mocked(api.job).mock.calls[0][0], vi.mocked(api.projectChange).mock.calls[0]]).toEqual(
      ["https://github.com/acme-platform/invoice-ingest-infra/pull/1", "job-1", ["invoice-ingest", "chg-1"]]);
  });

  it("keeps polling while the change is queued", async () => {
    const projectChangeCall = vi.fn()
      .mockResolvedValueOnce(projectChange())
      .mockResolvedValue(projectChange({ state: "open", pull_request: { number: 3, url: "https://example/pull/3" } }));
    renderChange(fakeApi({ projectChange: projectChangeCall }));
    await previewChange();
    await user().click(await screen.findByRole("button", { name: "Open change request" }));
    expect(await screen.findByRole("link", { name: "Pull request #3" })).toBeInTheDocument();
  });

  it("reports a failed change job", async () => {
    renderChange(fakeApi({ job: vi.fn().mockResolvedValue(job("failed_rolled_back", [], "GitHub is down")),
      projectChange: vi.fn().mockResolvedValue(projectChange({ state: "failed" })) }));
    await previewChange();
    await user().click(await screen.findByRole("button", { name: "Open change request" }));
    expect(await screen.findByText("The change failed and was undone; see the steps above.")).toBeInTheDocument();
  });

  it("shows change polling errors", async () => {
    renderChange(fakeApi({ projectChange: vi.fn().mockRejectedValue(new Error("lost")) }));
    await previewChange();
    await user().click(await screen.findByRole("button", { name: "Open change request" }));
    expect(await screen.findByText("lost")).toBeInTheDocument();
  });

  it("shows preview and creation errors", async () => {
    renderChange(fakeApi({ previewChange: vi.fn().mockRejectedValue(new Error("Nothing changed.")) }));
    await previewChange();
    expect(await screen.findByRole("alert")).toHaveTextContent("Nothing changed.");
  });
});
