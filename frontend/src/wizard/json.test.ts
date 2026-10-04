import { describe, expect, it } from "vitest";
import { parseJsonObject } from "./json";

describe("parseJsonObject", () => {
  it("parses an object", () => {
    expect(parseJsonObject('{"DisplayName":"Alerts"}')).toEqual({ DisplayName: "Alerts" });
  });

  it("treats empty text as no properties", () => {
    expect(parseJsonObject("  ")).toEqual({});
  });

  it.each(["[1]", "1", "null", "{not json"])("rejects %s", (text) => {
    expect(parseJsonObject(text)).toBeUndefined();
  });
});
