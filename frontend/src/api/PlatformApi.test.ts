import { describe, expect, it, vi } from "vitest";
import { ApiError, PlatformApi } from "./PlatformApi";
import type { ProjectRequest } from "./types";

function respond(body: unknown, status = 200) {
  return vi.fn().mockResolvedValue({
    ok: status < 400, status, json: async () => body,
  } as Response);
}

const REQUEST = { project_name: "demo-app" } as ProjectRequest;

describe("PlatformApi", () => {
  it("reads the org registry", async () => {
    const fetcher = respond([{ id: "pf-payments" }]);
    await new PlatformApi("", fetcher).orgRegistry();
    expect(fetcher).toHaveBeenCalledWith("/v1/org-registry", expect.objectContaining({ method: "GET" }));
  });

  it("returns parsed JSON", async () => {
    expect(await new PlatformApi("", respond([{ id: "dev" }])).environments()).toEqual([{ id: "dev" }]);
  });

  it("prefixes the base URL", async () => {
    const fetcher = respond([]);
    await new PlatformApi("http://api", fetcher).regions();
    expect(fetcher.mock.calls[0][0]).toBe("http://api/v1/admin/regions");
  });

  it("updates a region with PUT and a JSON body", async () => {
    const fetcher = respond({ id: "us-west-2", enabled: true });
    await new PlatformApi("", fetcher).setRegionEnabled("us-west-2", true);
    expect(fetcher).toHaveBeenCalledWith("/v1/admin/regions/us-west-2", expect.objectContaining({
      method: "PUT", body: JSON.stringify({ enabled: true }) }));
  });

  it("reads the curated catalog", async () => {
    const fetcher = respond([]);
    await new PlatformApi("", fetcher).catalog();
    expect(fetcher.mock.calls[0][0]).toBe("/v1/catalog");
  });

  it("searches CloudFormation types with an encoded query", async () => {
    const fetcher = respond([]);
    await new PlatformApi("", fetcher).searchCloudFormation("sns topic");
    expect(fetcher.mock.calls[0][0]).toBe("/v1/catalog/cloudformation?search=sns%20topic");
  });

  it("reads cost centers", async () => {
    const fetcher = respond({ default: "CC-1000" });
    await new PlatformApi("", fetcher).costCenters();
    expect(fetcher.mock.calls[0][0]).toBe("/v1/admin/cost-centers");
  });

  it("updates cost centers", async () => {
    const fetcher = respond({ default: "CC-2000" });
    await new PlatformApi("", fetcher).updateCostCenters({ default: "CC-2000" });
    expect(fetcher.mock.calls[0][1]).toMatchObject({ method: "PUT", body: '{"default":"CC-2000"}' });
  });

  it("posts a preview", async () => {
    const fetcher = respond({ files: {} });
    await new PlatformApi("", fetcher).preview(REQUEST);
    expect(fetcher).toHaveBeenCalledWith("/v1/projects:preview", expect.objectContaining({ method: "POST" }));
  });

  it("creates a project with an idempotency key", async () => {
    const fetcher = respond({ job_id: "j1" });
    await new PlatformApi("", fetcher).createProject(REQUEST, "key-1");
    expect(fetcher.mock.calls[0][1].headers).toMatchObject({ "Idempotency-Key": "key-1" });
  });

  it("lists projects", async () => {
    const fetcher = respond([]);
    await new PlatformApi("", fetcher).projects();
    expect(fetcher.mock.calls[0][0]).toBe("/v1/projects");
  });

  it("reads a job", async () => {
    const fetcher = respond({ id: "j1" });
    await new PlatformApi("", fetcher).job("j1");
    expect(fetcher.mock.calls[0][0]).toBe("/v1/jobs/j1");
  });

  it("raises the server's detail as an ApiError", async () => {
    const api = new PlatformApi("", respond({ detail: "Unknown environment 'qa9'." }, 422));
    await expect(api.environments()).rejects.toEqual(new ApiError(422, "Unknown environment 'qa9'."));
  });

  it("formats validation details from the framework", async () => {
    const api = new PlatformApi("", respond({ detail: [{ msg: "String should match pattern" }] }, 422));
    await expect(api.preview(REQUEST)).rejects.toThrow("String should match pattern");
  });

  it("falls back to the status when there is no detail", async () => {
    const api = new PlatformApi("", respond({}, 500));
    await expect(api.projects()).rejects.toThrow("Request failed with status 500");
  });

  it("uses the global fetch by default", async () => {
    const original = globalThis.fetch;
    globalThis.fetch = respond([]);
    await new PlatformApi().projects();
    expect(globalThis.fetch).toHaveBeenCalled();
    globalThis.fetch = original;
  });
});
