import { useState } from "react";
import { useApi } from "../../../api/ApiContext";
import type { CloudFormationType } from "../../../api/types";
import { ErrorAlert } from "../../../components/Notices";
import { parseJsonObject } from "../../../wizard/json";
import type { DraftResource } from "../../../wizard/ProjectDraft";
import type { StepProps } from "./StepProps";

const CLOUDFORMATION_PREFIX = "AWS::";

export function ServicesStep({ draft, onChange, reference }: StepProps) {
  return (
    <>
      <h2>Services</h2>
      <div className="split">
        <div className="stack">
          <span className="label">Curated services</span>
          <div className="cat">
            {reference.catalog.map((entry) => (
              <div key={entry.type} className="svc">
                <b>{entry.name}</b>
                <span className="hint">{entry.category} · multi-region: {entry.multi_region}</span>
                <button className="btn ghost" aria-label={`Add ${entry.name}`} onClick={() => onChange(draft.withResource(entry.type))}>
                  Add
                </button>
              </div>
            ))}
          </div>
          <CloudFormationSearch onAdd={(type) => onChange(draft.withResource(type))} />
        </div>
        <SelectedResources draft={draft} onChange={onChange} />
      </div>
    </>
  );
}

function CloudFormationSearch({ onAdd }: { onAdd: (type: string) => void }) {
  const api = useApi();
  const [text, setText] = useState("");
  const [results, setResults] = useState<CloudFormationType[]>([]);
  const [error, setError] = useState<string>();

  const search = async () => {
    try {
      setResults(await api.searchCloudFormation(text));
      setError(undefined);
    } catch (failure) {
      setError((failure as Error).message);
    }
  };

  return (
    <div className="stack">
      <label htmlFor="cfn-search" className="label">Search all CloudFormation types</label>
      <div className="row">
        <input id="cfn-search" value={text} placeholder="e.g. sns, rds, eventbridge" onChange={(event) => setText(event.target.value)} />
        <button className="btn" onClick={search}>Search</button>
      </div>
      <ErrorAlert message={error} />
      <ul className="results">
        {results.map((result) => (
          <li key={result.type}>
            <span className="mono">{result.type}</span>
            <span className="hint">{result.required.length > 0 ? `Required: ${result.required.join(", ")}` : "No required properties."}</span>
            <button className="btn ghost" aria-label={`Add ${result.type}`} onClick={() => onAdd(result.type)}>Add</button>
          </li>
        ))}
      </ul>
    </div>
  );
}

function SelectedResources({ draft, onChange }: Pick<StepProps, "draft" | "onChange">) {
  const { resources } = draft.values;
  return (
    <div className="panel">
      <div className="panel-h"><h3>Selected ({resources.length})</h3></div>
      <div className="panel-b">
        {resources.length === 0 && <p className="empty">Nothing selected yet.</p>}
        {resources.map((resource) => (
          <div key={resource.id} className="selected">
            <div className="row">
              <b className="mono">{resource.id}</b>
              <span className="muted">{resource.type}</span>
              <span className="spacer" />
              <button className="btn ghost" aria-label={`Remove ${resource.id}`} onClick={() => onChange(draft.withoutResource(resource.id))}>
                Remove
              </button>
            </div>
            {resource.type.startsWith(CLOUDFORMATION_PREFIX) && (
              <PropertiesEditor resource={resource} onProperties={(properties) => onChange(draft.withResourceProperties(resource.id, properties))} />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function PropertiesEditor({ resource, onProperties }: { resource: DraftResource; onProperties: (p: Record<string, unknown>) => void }) {
  const [invalid, setInvalid] = useState(false);
  const update = (text: string) => {
    const properties = parseJsonObject(text);
    setInvalid(properties === undefined);
    if (properties !== undefined) onProperties(properties);
  };
  return (
    <div className="field">
      <textarea aria-label={`Properties for ${resource.id}`} rows={3} placeholder='{"Property": "value"}'
                onChange={(event) => update(event.target.value)} />
      {invalid && <span className="err">Properties must be a JSON object.</span>}
    </div>
  );
}
