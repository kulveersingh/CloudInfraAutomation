import { useState, type ReactNode } from "react";
import type { OuInfo, TreeEdit } from "../../../api/types";
import { MoveForm, TextForm } from "./forms";
import type { TreeEditor } from "./TreeEditor";

type OuForm = "add_child" | "add_account" | "rename" | "move";

interface FormContext {
  ou: OuInfo;
  editor: TreeEditor;
  edit: (change: TreeEdit) => void;
}

/** The OU actions that open an inline form: button text, accessible name and the form it opens. */
const FORMS: Array<{ form: OuForm; text: string; name: (ou: OuInfo) => string; render: (context: FormContext) => ReactNode }> = [
  { form: "add_child", text: "+ OU", name: (ou) => `Add OU under ${ou.name}`,
    render: ({ ou, edit }) => <TextForm label="New OU name" submit="Add OU"
                                        onSubmit={(name) => edit({ op: "add_ou", parent: ou.key, name })} /> },
  { form: "add_account", text: "+ Account", name: (ou) => `Add account to ${ou.name}`,
    render: ({ ou, edit }) => <TextForm label="Account suffix" submit="Add account"
                                        onSubmit={(suffix) => edit({ op: "add_account", ou: ou.key, suffix })} /> },
  { form: "rename", text: "Rename", name: (ou) => `Rename ${ou.name}`,
    render: ({ ou, edit }) => <TextForm label={`New name for ${ou.name}`} submit="Save name" initial={ou.name}
                                        onSubmit={(name) => edit({ op: "rename_ou", ou: ou.key, name })} /> },
  { form: "move", text: "Move", name: (ou) => `Move ${ou.name}`,
    render: ({ ou, editor, edit }) => <MoveForm label={`Move ${ou.name} to`} targets={editor.index.ouTargets(ou)}
                                                onMove={(parent) => edit({ op: "move_ou", ou: ou.key, parent })} /> },
];

/** Only the edits the platform allows for this OU; Move only when its isolation domain has somewhere to go. */
export function OuActions({ ou, editor }: { ou: OuInfo; editor: TreeEditor }) {
  const [open, setOpen] = useState<OuForm>();
  const edit = (change: TreeEdit) => {
    setOpen(undefined);
    editor.onEdit(change);
  };
  const offered = FORMS.filter(({ form }) => ou.allowed_edits.includes(form)
    && (form !== "move" || editor.index.ouTargets(ou).length > 0));
  return (
    <span className="row actions">
      {offered.map(({ form, text, name }) => (
        <button key={form} className="btn ghost" aria-label={name(ou)} onClick={() => setOpen(form)}>{text}</button>
      ))}
      <RemoveOu ou={ou} onRemove={() => edit({ op: "remove_ou", ou: ou.key })} />
      {open && FORMS.find(({ form }) => form === open)!.render({ ou, editor, edit })}
    </span>
  );
}

function RemoveOu({ ou, onRemove }: { ou: OuInfo; onRemove: () => void }) {
  const blocked = ou.blocked_edits.remove;
  if (blocked) {
    return <><button className="btn ghost" aria-label={`Remove ${ou.name}`} disabled>Remove</button><span className="hint">{blocked}</span></>;
  }
  return ou.allowed_edits.includes("remove")
    ? <button className="btn ghost" aria-label={`Remove ${ou.name}`} onClick={onRemove}>Remove</button> : null;
}

/** Adds an OU directly under the organization root; it becomes its own isolation domain. */
export function RootActions({ editor }: { editor: TreeEditor }) {
  const [open, setOpen] = useState(false);
  const add = (name: string) => {
    setOpen(false);
    editor.onEdit({ op: "add_ou", parent: null, name });
  };
  return (
    <div className="row actions">
      <button className="btn" onClick={() => setOpen(true)}>Add OU at the root</button>
      {open && <TextForm label="New OU name" submit="Add OU" onSubmit={add} />}
      <span className="hint">A root-level OU is its own isolation boundary with the workload baseline and controls.</span>
    </div>
  );
}
