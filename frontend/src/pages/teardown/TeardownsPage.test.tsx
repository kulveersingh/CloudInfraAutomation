import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { PlatformApiPort, Teardown } from "../../api/types";
import { fakeApi, teardown } from "../../test/fakes";
import { renderWithApi } from "../../test/render";
import { TeardownsPage } from "./TeardownsPage";

const user = () => userEvent.setup();
const POINT = { service_id: "uploads", resource_type: "AWS::S3::Bucket", physical_name: "invoice-ingest--uploads",
  region: "us-east-1", account_id: "999999999999",
  recovery_point_arn: "arn:aws:backup:us-east-1:999999999999:recovery-point:rp-1", vault: "cloudinfra-teardown-us-east-1",
  completed_at: "2026-10-04T10:05:00+00:00", locked_until: "2026-12-03T10:05:00+00:00" };
const COMPLETED = teardown({ state: "completed", environments: [{ ...teardown().environments[0], state: "completed",
  decided_by: "sam", revision: 2, recovery_points: [POINT] }] });

function renderTeardowns(items: Teardown[] = [teardown()], overrides: Partial<PlatformApiPort> = {}) {
  const api = fakeApi({ teardowns: vi.fn().mockResolvedValue(items), ...overrides });
  renderWithApi(<TeardownsPage />, api);
  return api;
}

describe("TeardownsPage", () => {
  it("lists teardowns with their environments", async () => {
    renderTeardowns();
    const panel = await screen.findByRole("region", { name: "invoice-ingest · environment teardown" });
    expect([within(panel).getByText("dev"), within(panel).getByText("pending_approval"),
      within(panel).getByText("Requested by jordan")]).toHaveLength(3);
  });

  it("shows an empty state", async () => {
    renderTeardowns([]);
    expect(await screen.findByText("No teardowns yet.")).toBeInTheDocument();
  });

  it.each([["Approve", "approve"], ["Reject", "reject"]] as const)("%s an environment with a comment", async (label, decision) => {
    const api = renderTeardowns();
    await user().type(await screen.findByLabelText("Comment for dev of invoice-ingest"), "checked");
    await user().click(screen.getByRole("button", { name: `${label} tearing down dev of invoice-ingest` }));
    expect([vi.mocked(api.decideTeardownEnvironment).mock.calls[0], vi.mocked(api.teardowns).mock.calls.length]).toEqual(
      [["invoice-ingest", "td-1", "dev", decision, "checked"], 2]);
  });

  it("retries a failed environment and shows the error", async () => {
    const failed = teardown({ environments: [{ ...teardown().environments[0], state: "failed_needs_attention",
      error: "Backup of uploads failed." }] });
    const api = renderTeardowns([failed]);
    await user().click(await screen.findByRole("button", { name: "Retry dev of invoice-ingest" }));
    expect([screen.getByText("Backup of uploads failed."), vi.mocked(api.decideTeardownEnvironment).mock.calls[0]]).toEqual(
      [expect.anything(), ["invoice-ingest", "td-1", "dev", "retry", ""]]);
  });

  it("lists the backups with their lock date", async () => {
    renderTeardowns([COMPLETED]);
    expect([await screen.findByText("uploads · us-east-1 · locked until 2026-12-03"),
      screen.getByText(POINT.recovery_point_arn)]).toHaveLength(2);
  });

  it("requests a restore of a completed teardown", async () => {
    const api = renderTeardowns([COMPLETED]);
    await user().click(await screen.findByRole("button", { name: "Request restore of invoice-ingest" }));
    expect(vi.mocked(api.restoreTeardown).mock.calls[0]).toEqual(["invoice-ingest", "td-1", "restore", ""]);
  });

  it("does not offer a restore before anything was torn down", async () => {
    renderTeardowns();
    await screen.findByText("dev");
    expect(screen.queryByRole("button", { name: /Request restore/ })).toBeNull();
  });

  it.each([["Approve", "approve-restore"], ["Reject", "reject-restore"]] as const)("%s a requested restore", async (label, decision) => {
    const api = renderTeardowns([{ ...COMPLETED, restore: { state: "requested", requested_by: "jordan", decided_by: null, job_id: null } }]);
    await user().click(await screen.findByRole("button", { name: `${label} restore of invoice-ingest` }));
    expect(vi.mocked(api.restoreTeardown).mock.calls[0]).toEqual(["invoice-ingest", "td-1", decision, ""]);
  });

  it("shows the restore state", async () => {
    renderTeardowns([{ ...COMPLETED, scope: "project", restore: { state: "restored", requested_by: "jordan", decided_by: "alex", job_id: "job-9" } }]);
    expect([await screen.findByText("Restore restored (requested by jordan, decided by alex)"),
      screen.getByRole("region", { name: "invoice-ingest · decommission" })]).toHaveLength(2);
  });

  it("offers a new restore after one was rejected", async () => {
    renderTeardowns([{ ...COMPLETED, restore: { state: "rejected", requested_by: "jordan", decided_by: "sam", job_id: null } }]);
    expect(await screen.findByRole("button", { name: "Request restore of invoice-ingest" })).toBeInTheDocument();
  });

  it("shows action errors", async () => {
    renderTeardowns([teardown()], { decideTeardownEnvironment: vi.fn().mockRejectedValue(new Error("forbidden")) });
    await user().click(await screen.findByRole("button", { name: "Approve tearing down dev of invoice-ingest" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("forbidden");
  });

  it("shows loading errors", async () => {
    renderTeardowns([], { teardowns: vi.fn().mockRejectedValue(new Error("API down")) });
    expect(await screen.findByRole("alert")).toHaveTextContent("API down");
  });
});
