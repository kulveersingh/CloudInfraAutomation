import { describe, expect, it, vi } from "vitest";
import { PlatformApi } from "./PlatformApi";

function respond(body: unknown = {}) {
  return vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => body } as Response);
}

describe("PlatformApi releases", () => {
  it("reads a project's pipeline", async () => {
    const fetcher = respond([]);
    await new PlatformApi("", fetcher).pipeline("invoice-ingest");
    expect(fetcher.mock.calls[0][0]).toBe("/v1/projects/invoice-ingest/pipeline");
  });

  it("reads the approvals inbox", async () => {
    const fetcher = respond([]);
    await new PlatformApi("", fetcher).inbox();
    expect(fetcher.mock.calls[0][0]).toBe("/v1/approvals/inbox");
  });

  it("simulates a pipeline plan", async () => {
    const fetcher = respond();
    await new PlatformApi("", fetcher).simulateRelease("invoice-ingest", "stage", true);
    expect(fetcher).toHaveBeenCalledWith("/v1/projects/invoice-ingest/releases:simulate", expect.objectContaining({
      method: "POST", body: JSON.stringify({ environment: "stage", high_risk: true }) }));
  });

  it("approves a release with a comment", async () => {
    const fetcher = respond();
    await new PlatformApi("", fetcher).approveRelease("rel-1", "ok");
    expect(fetcher).toHaveBeenCalledWith("/v1/releases/rel-1:approve", expect.objectContaining({
      method: "POST", body: JSON.stringify({ comment: "ok" }) }));
  });

  it("rejects a release", async () => {
    const fetcher = respond();
    await new PlatformApi("", fetcher).rejectRelease("rel-1", "no");
    expect(fetcher.mock.calls[0][0]).toBe("/v1/releases/rel-1:reject");
  });

  it("approves an override", async () => {
    const fetcher = respond();
    await new PlatformApi("", fetcher).approveOverride("rel-1", "cache only");
    expect(fetcher.mock.calls[0][0]).toBe("/v1/releases/rel-1:approve-override");
  });

  it("sends the acting identity as headers", async () => {
    const fetcher = respond([]);
    const api = new PlatformApi("", fetcher);
    api.setActor({ name: "sam", label: "Sam Patel", roles: ["reviewer", "developer"] });
    await api.inbox();
    expect(fetcher.mock.calls[0][1].headers).toMatchObject({ "X-Actor": "sam", "X-Roles": "reviewer,developer" });
  });

  it("sends no identity headers until an actor is set", async () => {
    const fetcher = respond([]);
    await new PlatformApi("", fetcher).inbox();
    expect(fetcher.mock.calls[0][1].headers).not.toHaveProperty("X-Actor");
  });
});
