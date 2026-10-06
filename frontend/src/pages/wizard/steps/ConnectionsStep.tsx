import { useState } from "react";
import type { AccessLevel, ConnectionRequest } from "../../../api/types";
import type { StepProps } from "./StepProps";

const KINDS = ["event.notify", "iam.access"];
const ACCESS_LEVELS: AccessLevel[] = ["read", "write", "readwrite"];

export function ConnectionsStep({ draft, onChange }: Pick<StepProps, "draft" | "onChange">) {
  const ids = draft.values.resources.map((resource) => resource.id);
  const [form, setForm] = useState<Required<ConnectionRequest>>({
    kind: KINDS[0], source: ids[0] ?? "", target: ids[1] ?? "", access: "read", prefix: "",
  });
  const update = (change: Partial<ConnectionRequest>) => setForm((current) => ({ ...current, ...change }));

  return (
    <>
      <h2>Connections</h2>
      <p className="sub">Connections are the only way components get access to each other. Each grants access to exactly
        the target resource, and nothing broader.</p>
      <ConnectionList draft={draft} onChange={onChange} />
      <div className="row">
        <Select label="Kind" value={form.kind} options={KINDS} onSelect={(kind) => update({ kind })} />
        <Select label="From" value={form.source} options={ids} onSelect={(source) => update({ source })} />
        <Select label="To" value={form.target} options={ids} onSelect={(target) => update({ target })} />
        <Select label="Access" value={form.access} options={ACCESS_LEVELS} onSelect={(access) => update({ access: access as AccessLevel })} />
        <div className="field">
          <label htmlFor="connection-prefix">Prefix</label>
          <input id="connection-prefix" value={form.prefix} onChange={(event) => update({ prefix: event.target.value })} />
        </div>
        <button className="btn" disabled={ids.length < 2} onClick={() => onChange(draft.withConnection(form))}>Add connection</button>
      </div>
    </>
  );
}

function ConnectionList({ draft, onChange }: Pick<StepProps, "draft" | "onChange">) {
  const { connections } = draft.values;
  if (connections.length === 0) return <p className="empty">No connections yet.</p>;
  return (
    <ul className="connections">
      {connections.map((connection, index) => (
        <li key={`${connection.kind}-${connection.source}-${connection.target}-${index}`} className="row">
          <span className="mono">{connection.kind}</span>
          <b>{connection.source} → {connection.target}</b>
          <span className="muted">{connection.access} {connection.prefix}</span>
          <button className="btn ghost" aria-label={`Remove connection ${index + 1}`} onClick={() => onChange(draft.withoutConnection(index))}>
            Remove
          </button>
        </li>
      ))}
    </ul>
  );
}

interface SelectProps {
  label: string;
  value: string;
  options: string[];
  onSelect: (value: string) => void;
}

function Select({ label, value, options, onSelect }: SelectProps) {
  const id = `connection-${label.toLowerCase()}`;
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <select id={id} value={value} onChange={(event) => onSelect(event.target.value)}>
        {options.map((option) => <option key={option}>{option}</option>)}
      </select>
    </div>
  );
}
