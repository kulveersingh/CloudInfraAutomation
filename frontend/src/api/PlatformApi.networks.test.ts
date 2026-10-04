import { describe, expect, it, vi } from "vitest";
import { PlatformApi } from "./PlatformApi";
import type { NetworkInput } from "./types";

function respond(body: unknown = {}) {
  return vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => body } as Response);
}

const INPUT = { name: "Org VPC" } as NetworkInput;

describe("PlatformApi networks", () => {
  it("lists networks", async () => {
    const fetcher = respond([]);
    await new PlatformApi("", fetcher).networks();
    expect(fetcher.mock.calls[0][0]).toBe("/v1/admin/networks");
  });

  it("creates a network", async () => {
    const fetcher = respond();
    await new PlatformApi("", fetcher).createNetwork(INPUT);
    expect(fetcher).toHaveBeenCalledWith("/v1/admin/networks", expect.objectContaining({ method: "POST" }));
  });

  it("updates a network", async () => {
    const fetcher = respond();
    await new PlatformApi("", fetcher).updateNetwork("net-1", INPUT);
    expect(fetcher).toHaveBeenCalledWith("/v1/admin/networks/net-1", expect.objectContaining({ method: "PUT" }));
  });

  it("reads network settings", async () => {
    const fetcher = respond();
    await new PlatformApi("", fetcher).networkSettings();
    expect(fetcher.mock.calls[0][0]).toBe("/v1/admin/network-settings");
  });

  it("updates network settings", async () => {
    const fetcher = respond();
    await new PlatformApi("", fetcher).updateNetworkSettings({ attach_compute_by_default: false });
    expect(fetcher.mock.calls[0][1]).toMatchObject({ method: "PUT", body: '{"attach_compute_by_default":false}' });
  });

  it("reads wizard network options for a portfolio", async () => {
    const fetcher = respond([]);
    await new PlatformApi("", fetcher).networkOptions("pf-payments");
    expect(fetcher.mock.calls[0][0]).toBe("/v1/networks/options?portfolio_id=pf-payments");
  });
});
