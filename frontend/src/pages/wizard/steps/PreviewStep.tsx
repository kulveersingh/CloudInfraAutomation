import { useState } from "react";
import { useApi } from "../../../api/ApiContext";
import type { PreviewResult } from "../../../api/types";
import { ErrorAlert } from "../../../components/Notices";
import { capitalized, useDocumentFile, useVocabulary } from "../../../providers/VocabularyContext";
import type { ProjectDraft } from "../../../wizard/ProjectDraft";

interface PreviewStepProps {
  draft: ProjectDraft;
  newKey: () => string;
  onCreated: (jobId: string) => void;
}

export function PreviewStep({ draft, newKey, onCreated }: PreviewStepProps) {
  const api = useApi();
  const [result, setResult] = useState<PreviewResult>();
  const [error, setError] = useState<string>();
  const problems = draft.problems();

  const run = async (action: () => Promise<void>) => {
    try {
      setError(undefined);
      await action();
    } catch (failure) {
      setError((failure as Error).message);
    }
  };
  const preview = () => run(async () => setResult(await api.preview(draft.toRequest())));
  const create = () => run(async () => onCreated((await api.createProject(draft.toRequest(), newKey())).job_id));

  return (
    <>
      <h2>Preview</h2>
      <DraftProblems problems={problems} />
      <ErrorAlert message={error} />
      <div className="row">
        <button className="btn" disabled={problems.length > 0} onClick={preview}>Generate preview</button>
        <button className="btn pri" disabled={problems.length > 0} onClick={create}>Create repository and deploy</button>
      </div>
      {result && <PreviewDetails result={result} provider={draft.values.provider} />}
    </>
  );
}

export function DraftProblems({ problems }: { problems: string[] }) {
  if (problems.length === 0) return null;
  return <div className="notice warn"><b>Fix before continuing:</b><ul>{problems.map((p) => <li key={p}>{p}</li>)}</ul></div>;
}

export function PreviewDetails({ result, provider }: { result: PreviewResult; provider: string }) {
  const words = useVocabulary(provider);
  const documentFile = useDocumentFile(provider);
  const notes = result.notes ?? [];
  return (
    <div className="stack">
      <span className="label">Target {words.isolation_unit}s</span>
      <div className="tbl-wrap">
        <table>
          <thead><tr><th>Environment</th><th>{capitalized(words.isolation_unit)}</th><th>Regions</th><th>Network</th></tr></thead>
          <tbody>
            {Object.entries(result.targets).map(([environment, target]) => (
              <tr key={environment}><td>{environment}</td><td className="num">{target.account_id}</td><td className="mono">{target.regions.join(" · ")}</td>
                <td className="mono">{Object.entries(target.networks).map(([region, network]) => (
                  <div key={region}>{`${region}: ${network.network_ref}`}</div>))}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
      <span className="label">Tags</span>
      <div className="tags">{Object.entries(result.tags).map(([key, value]) => <span key={key} className="tag">{key}=<b>{value}</b></span>)}</div>
      <span className="label">Policy checks</span>
      {result.lint.length > 0
        ? <ul className="notice crit">{result.lint.map((finding) => <li key={finding}>{finding}</li>)}</ul>
        : <p className="notice ok">No findings: the generated code passes the platform's policy checks.</p>}
      {notes.length > 0 && (
        <>
          <span className="label">What the code cannot do for you</span>
          <ul className="notice warn">{notes.map((note) => <li key={note}>{note}</li>)}</ul>
        </>
      )}
      <span className="label">{documentFile}</span>
      <pre className="code">{result.files[documentFile]}</pre>
    </div>
  );
}
