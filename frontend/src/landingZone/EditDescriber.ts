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

export class EditDescriber {
  constructor(private readonly index: OuTreeIndex) {}

  describe(edit: TreeEdit): string {
    const describer = DESCRIBERS[edit.op] as (edit: TreeEdit, name: Name) => string;
    return describer(edit, (key) => this.index.name(key));
  }
}
