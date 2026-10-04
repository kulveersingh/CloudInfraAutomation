import type { TreeEdit } from "../../../api/types";
import type { EditDescriber } from "../../../landingZone/EditDescriber";

interface ManualChangesProps {
  edits: TreeEdit[];
  describer: EditDescriber;
  onUndo?: (index: number) => void;
}

/** The editor's changes in plain words, so the admin and the approver see what was changed by hand. */
export function ManualChanges({ edits, describer, onUndo }: ManualChangesProps) {
  if (edits.length === 0) return null;
  const descriptions = describer.describeAll(edits);
  return (
    <div className="panel">
      <div className="panel-h"><h3>Manual changes ({edits.length})</h3></div>
      <ul className="panel-b changes" aria-label="Manual changes">
        {descriptions.map((description, index) => (
          <li key={index}>
            {description}
            {onUndo && <button className="btn ghost" aria-label={`Undo change ${index + 1}`} onClick={() => onUndo(index)}>Undo</button>}
          </li>
        ))}
      </ul>
    </div>
  );
}
