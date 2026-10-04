import { useState } from "react";
import type { AccountEdit, AccountInfo, OuInfo, TreeEdit } from "../../../api/types";
import { MoveForm } from "./forms";
import type { TreeEditor } from "./TreeEditor";

/** One-click account edits; generated workload accounts are disabled, never removed. */
const TOGGLES: Array<{ edit: Exclude<AccountEdit, "move">; text: string; change: (account: string) => TreeEdit }> = [
  { edit: "disable", text: "Disable", change: (account) => ({ op: "disable_account", account }) },
  { edit: "enable", text: "Enable", change: (account) => ({ op: "enable_account", account }) },
  { edit: "remove", text: "Remove", change: (account) => ({ op: "remove_account", account }) },
];

export function AccountActions({ account, ou, editor }: { account: AccountInfo; ou: OuInfo; editor: TreeEditor }) {
  const [moving, setMoving] = useState(false);
  const targets = editor.index.accountTargets(ou);
  const allowed = new Set(account.allowed_edits);
  const move = (target: string) => {
    setMoving(false);
    editor.onEdit({ op: "move_account", account: account.name, ou: target });
  };
  return (
    <span className="row actions">
      {allowed.has("move") && targets.length > 0 && (
        <button className="btn ghost" aria-label={`Move ${account.name}`} onClick={() => setMoving(true)}>Move</button>
      )}
      {TOGGLES.filter(({ edit }) => allowed.has(edit)).map(({ edit, text, change }) => (
        <button key={edit} className="btn ghost" aria-label={`${text} ${account.name}`}
                onClick={() => editor.onEdit(change(account.name))}>{text}</button>
      ))}
      {moving && <MoveForm label={`Move ${account.name} to`} targets={targets} onMove={move} />}
    </span>
  );
}
