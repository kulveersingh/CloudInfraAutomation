import { describe, expect, it } from "vitest";
import { RegionPairs } from "./RegionPairs";

describe("RegionPairs", () => {
  it("has no pairs until the cloud has loaded", () => {
    const pairs = new RegionPairs();
    expect([pairs.secondaryFor("eastus2", "westus2"), pairs.hint("dr", "eastus2"), pairs.problem("dr", "eastus2", "westus2", true)])
      .toEqual(["westus2", undefined, undefined]);
  });

  it("keeps the secondary when the primary's pair is not enabled", () => {
    expect(new RegionPairs({ eastus2: "centralus" }, ["eastus2"]).secondaryFor("eastus2", "westus2")).toBe("westus2");
  });
});
