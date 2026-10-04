import { describe, expect, it } from "vitest";
import type { OuInfo } from "../api/types";
import { OU_TREE } from "../test/fakes";
import { OuTreeIndex } from "./OuTreeIndex";

const [, , prod] = OU_TREE;
const [payments, cards] = prod.children;
const nested: OuInfo = { ...prod, children: [{ ...payments, children: [cards] }] };

describe("OuTreeIndex", () => {
  it("never offers to move an OU inside its own child OUs", () => {
    expect(new OuTreeIndex([nested]).ouTargets(nested.children[0]).map((ou) => ou.key)).toEqual([]);
  });

  it("offers an OU's siblings in the same domain", () => {
    expect(new OuTreeIndex(OU_TREE).ouTargets(payments).map((ou) => ou.key)).toEqual(["custom_cards"]);
  });

  it("names OUs by key and falls back to the key", () => {
    expect([new OuTreeIndex(OU_TREE).name("prod"), new OuTreeIndex(OU_TREE).name("gone")]).toEqual(["PROD", "gone"]);
  });
});
