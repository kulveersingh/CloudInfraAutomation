import { describe, expect, it } from "vitest";
import type { OuInfo, TreeEdit } from "../api/types";
import { OU_TREE } from "../test/fakes";
import { EditDescriber } from "./EditDescriber";
import { OuTreeIndex } from "./OuTreeIndex";

const renamed: OuInfo[] = OU_TREE.map((ou) => (ou.key !== "prod" ? ou : {
  ...ou, children: [{ ...ou.children[0], key: "custom_data_lab_2", name: "Billing" }] }));

describe("EditDescriber", () => {
  it("names each OU as it was at the time of the change", () => {
    const edits: TreeEdit[] = [{ op: "add_ou", parent: "prod", name: "Data Lab 2" },
      { op: "move_account", account: "acme-payments-prod", ou: "custom_data_lab_2" },
      { op: "rename_ou", ou: "custom_data_lab_2", name: "Billing" },
      { op: "add_account", ou: "custom_data_lab_2", suffix: "billing-prod" }];
    expect(new EditDescriber(new OuTreeIndex(renamed)).describeAll(edits)).toEqual([
      "Added OU Data Lab 2 under PROD", "Moved acme-payments-prod to Data Lab 2", "Renamed Data Lab 2 to Billing",
      "Added account billing-prod to Billing"]);
  });
});
