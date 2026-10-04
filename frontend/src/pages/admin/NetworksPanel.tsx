import { useState } from "react";
import { useApi } from "../../api/ApiContext";
import type { NetworkInfo, NetworkInput } from "../../api/types";
import { ErrorAlert } from "../../components/Notices";
import { useLoad } from "../../hooks/useLoad";

const EMPTY: NetworkInput = {
  name: "", account_id: "", region: "us-east-1", vpc_id: "", cidr: "", private_subnet_ids: [],
  security_group_ids: [], is_default: false,
};

const TEXT_FIELDS: Array<{ key: "name" | "account_id" | "region" | "vpc_id" | "cidr"; label: string }> = [
  { key: "name", label: "Name" }, { key: "account_id", label: "Account ID" }, { key: "region", label: "Region" },
  { key: "vpc_id", label: "VPC ID" }, { key: "cidr", label: "Private CIDR" },
];

const LIST_FIELDS: Array<{ key: "private_subnet_ids" | "security_group_ids"; label: string }> = [
  { key: "private_subnet_ids", label: "Private subnet IDs" }, { key: "security_group_ids", label: "Security group IDs" },
];

type Editing = { id?: string; input: NetworkInput };

function toInput({ id: _id, ...input }: NetworkInfo): NetworkInput {
  return input;
}

const splitIds = (text: string) => text.split(",").map((part) => part.trim()).filter(Boolean);

/** Organization networks per account and region; the default one is pre-selected in the project wizard. */
export function NetworksPanel() {
  const api = useApi();
  const loaded = useLoad(() => Promise.all([api.networks(), api.networkSettings()]));
  const [saved, setSaved] = useState<NetworkInfo[]>();
  const [attach, setAttach] = useState<boolean>();
  const [editing, setEditing] = useState<Editing>();
  const [error, setError] = useState<string>();

  const networks = saved ?? loaded.data?.[0];
  const attachByDefault = attach ?? loaded.data?.[1].attach_compute_by_default;

  const attempt = async (action: () => Promise<void>) => {
    try {
      await action();
      setError(undefined);
    } catch (failure) {
      setError((failure as Error).message);
    }
  };

  const saveSetting = (value: boolean) => attempt(async () => {
    setAttach((await api.updateNetworkSettings({ attach_compute_by_default: value })).attach_compute_by_default);
  });

  const saveNetwork = (current: NetworkInfo[], { id, input }: Editing) => attempt(async () => {
    const result = id ? await api.updateNetwork(id, input) : await api.createNetwork(input);
    setSaved(merge(current, result));
    setEditing(undefined);
  });

  return (
    <div className="stack">
      <ErrorAlert message={loaded.error ?? error} />
      {networks && (
        <>
          <label className="row">
            <input type="checkbox" checked={attachByDefault} onChange={(event) => saveSetting(event.target.checked)} />
            Attach compute to the organization VPC by default
          </label>
          <div className="tbl-wrap">
            <table>
              <thead><tr><th>ID</th><th>Name</th><th>Account</th><th>Region</th><th>VPC</th><th>CIDR</th><th>Subnets</th><th></th></tr></thead>
              <tbody>
                {networks.map((item) => (
                  <tr key={item.id}>
                    <td className="mono">{item.id}</td>
                    <td>{item.name} {item.is_default && <span className="chip ok">Default</span>}</td>
                    <td className="num">{item.account_id}</td>
                    <td className="mono">{item.region}</td>
                    <td className="mono">{item.vpc_id}</td>
                    <td className="mono">{item.cidr}</td>
                    <td className="mono">{item.private_subnet_ids.join(", ")}</td>
                    <td>
                      <button className="btn ghost" aria-label={`Edit ${item.id}`}
                              onClick={() => setEditing({ id: item.id, input: toInput(item) })}>Edit</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {editing
            ? <NetworkForm editing={editing} onChange={setEditing} onSave={() => saveNetwork(networks, editing)}
                           onCancel={() => setEditing(undefined)} />
            : <div><button className="btn" onClick={() => setEditing({ input: EMPTY })}>Add network</button></div>}
        </>
      )}
      <p className="hint">The default network for each account and region is pre-selected in the project wizard.
        Projects can choose another network or keep compute out of the VPC.</p>
    </div>
  );
}

function merge(networks: NetworkInfo[], result: NetworkInfo): NetworkInfo[] {
  const sameScope = (item: NetworkInfo) => item.account_id === result.account_id && item.region === result.region;
  const others = networks.filter((item) => item.id !== result.id)
    .map((item) => (result.is_default && sameScope(item) ? { ...item, is_default: false } : item));
  const exists = networks.some((item) => item.id === result.id);
  return exists ? networks.map((item) => others.find((other) => other.id === item.id) ?? result) : [...others, result];
}

interface NetworkFormProps {
  editing: Editing;
  onChange: (editing: Editing) => void;
  onSave: () => void;
  onCancel: () => void;
}

function NetworkForm({ editing, onChange, onSave, onCancel }: NetworkFormProps) {
  const { input } = editing;
  const update = (change: Partial<NetworkInput>) => onChange({ ...editing, input: { ...input, ...change } });
  return (
    <div className="panel">
      <div className="panel-b">
        <h3>{editing.id ? `Edit ${editing.id}` : "Add network"}</h3>
        <div className="grid3">
          {TEXT_FIELDS.map(({ key, label }) => (
            <div className="field" key={key}>
              <label htmlFor={`net-${key}`}>{label}</label>
              <input id={`net-${key}`} type="text" value={input[key]} onChange={(event) => update({ [key]: event.target.value })} />
            </div>
          ))}
          {LIST_FIELDS.map(({ key, label }) => (
            <div className="field" key={key}>
              <label htmlFor={`net-${key}`}>{label}</label>
              <input id={`net-${key}`} type="text" defaultValue={input[key].join(", ")}
                     onChange={(event) => update({ [key]: splitIds(event.target.value) })} />
              <span className="hint">Comma-separated</span>
            </div>
          ))}
        </div>
        <label className="row">
          <input type="checkbox" checked={input.is_default} onChange={(event) => update({ is_default: event.target.checked })} />
          Default for this account and region
        </label>
        <div className="row">
          <button className="btn pri" onClick={onSave}>Save network</button>
          <button className="btn" onClick={onCancel}>Cancel</button>
        </div>
      </div>
    </div>
  );
}
