import type { TreeEdit } from "../../../api/types";
import type { OuTreeIndex } from "../../../landingZone/OuTreeIndex";

/** Given to the OU tree when it may be edited; a read-only tree gets none. */
export interface TreeEditor {
  index: OuTreeIndex;
  onEdit: (edit: TreeEdit) => void;
}
