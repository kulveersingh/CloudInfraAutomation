import { describe, expect, it, vi } from "vitest";
import { LandingZoneDraft } from "../landingZone/LandingZoneDraft";
import { PlatformApi } from "./PlatformApi";

function respond(body: unknown = {}) {
  return vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => body } as Response);
}

const ANSWERS = LandingZoneDraft.initial().toAnswers();

describe("PlatformApi landing zone", () => {
  it("proposes a structure", async () => {
    const fetcher = respond();
    await new PlatformApi("", fetcher).proposeLandingZone(ANSWERS);
    expect(fetcher).toHaveBeenCalledWith("/v1/admin/landing-zone:propose", expect.objectContaining({ method: "POST" }));
  });

  it("saves a design", async () => {
    const fetcher = respond();
    await new PlatformApi("", fetcher).createLandingZoneDesign(ANSWERS);
    expect(fetcher).toHaveBeenCalledWith("/v1/admin/landing-zone/designs", expect.objectContaining({ method: "POST" }));
  });

  it("lists designs", async () => {
    const fetcher = respond([]);
    await new PlatformApi("", fetcher).landingZoneDesigns();
    expect(fetcher.mock.calls[0][0]).toBe("/v1/admin/landing-zone/designs");
  });

  it("reads a design", async () => {
    const fetcher = respond();
    await new PlatformApi("", fetcher).landingZoneDesign("lz-1");
    expect(fetcher.mock.calls[0][0]).toBe("/v1/admin/landing-zone/designs/lz-1");
  });

  it("submits a design", async () => {
    const fetcher = respond();
    await new PlatformApi("", fetcher).submitLandingZoneDesign("lz-1");
    expect(fetcher).toHaveBeenCalledWith("/v1/admin/landing-zone/designs/lz-1:submit", expect.objectContaining({ method: "POST" }));
  });

  it("approves with a comment", async () => {
    const fetcher = respond();
    await new PlatformApi("", fetcher).approveLandingZoneDesign("lz-1", "ok");
    expect(fetcher.mock.calls[0]).toEqual(["/v1/admin/landing-zone/designs/lz-1:approve",
      expect.objectContaining({ body: '{"comment":"ok"}' })]);
  });

  it("rejects with a comment", async () => {
    const fetcher = respond();
    await new PlatformApi("", fetcher).rejectLandingZoneDesign("lz-1", "no");
    expect(fetcher.mock.calls[0][0]).toBe("/v1/admin/landing-zone/designs/lz-1:reject");
  });
});
