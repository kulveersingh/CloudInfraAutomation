import { useState } from "react";
import type { OuInfo } from "../../../api/types";

interface TextFormProps {
  label: string;
  submit: string;
  initial?: string;
  onSubmit: (text: string) => void;
}

/** A one-field inline form: a new OU name, a rename or an account suffix. The platform validates the text. */
export function TextForm({ label, submit, initial = "", onSubmit }: TextFormProps) {
  const [text, setText] = useState(initial);
  return (
    <span className="row inline-form">
      <input type="text" aria-label={label} value={text} onChange={(event) => setText(event.target.value)} />
      <button className="btn pri" disabled={text.trim() === ""} onClick={() => onSubmit(text.trim())}>{submit}</button>
    </span>
  );
}

interface MoveFormProps {
  label: string;
  targets: OuInfo[];
  onMove: (key: string) => void;
}

export function MoveForm({ label, targets, onMove }: MoveFormProps) {
  const [target, setTarget] = useState(targets[0].key);
  return (
    <span className="row inline-form">
      <select aria-label={label} value={target} onChange={(event) => setTarget(event.target.value)}>
        {targets.map((ou) => <option key={ou.key} value={ou.key}>{ou.name}</option>)}
      </select>
      <button className="btn pri" onClick={() => onMove(target)}>Move</button>
    </span>
  );
}
