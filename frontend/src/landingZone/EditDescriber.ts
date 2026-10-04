import type { TreeEdit } from "../api/types";
import type { OuTreeIndex } from "./OuTreeIndex";

type Name = (key: string) => string;
type Describers = { [Op in TreeEdit["op"]]: (edit: Extract<TreeEdit, { op: Op }>, name: Name) => string };

/** One sentence per kind of edit; a new edit kind adds an entry. */
const DESCRIBERS: Describers = {
  add_ou: (edit, name) => (edit.parent === null
    ? `Added OU ${edit.name} at the root` : `Added OU ${edit.name} under ${name(edit.parent)}`),
  rename_ou: (edit, name) => `Renamed ${name(edit.ou)} to ${edit.name}`,
  move_ou: (edit, name) => `Moved ${name(edit.ou)} under ${name(edit.parent)}`,
  remove_ou: (edit, name) => `Removed OU ${name(edit.ou)}`,
  add_account: (edit, name) => `Added account ${edit.suffix} to ${name(edit.ou)}`,
  disable_account: (edit) => `Disabled ${edit.account}`,
  enable_account: (edit) => `Enabled ${edit.account}`,
  remove_account: (edit) => `Removed ${edit.account}`,
  move_account: (edit, name) => `Moved ${edit.account} to ${name(edit.ou)}`,
};

/** Mirrors the platform's key for an OU added in the editor ("Data Lab" → "custom_data_lab"). */
function customKey(name: string): string {
  return `custom_${name.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "")}`;
}

/** The name an earlier edit gave the OU, if any: its latest rename, else the add that created it. */
function nameFromEdits(key: string, earlier: TreeEdit[]): string | undefined {
  for (const edit of [...earlier].reverse()) {
    if (edit.op === "rename_ou" && edit.ou === key) return edit.name;
    if (edit.op === "add_ou" && customKey(edit.name) === key) return edit.name;
  }
  return undefined;
}

export class EditDescriber {
  constructor(private readonly index: OuTreeIndex) {}

  /** Each change names OUs as they were at that point, so a later rename doesn't rewrite earlier changes. */
  describeAll(edits: TreeEdit[]): string[] {
    return edits.map((edit, position) => {
      const describer = DESCRIBERS[edit.op] as (edit: TreeEdit, name: Name) => string;
      const earlier = edits.slice(0, position);
      return describer(edit, (key) => nameFromEdits(key, earlier) ?? this.index.name(key));
    });
  }
}
