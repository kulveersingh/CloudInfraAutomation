import { useState } from "react";
import { useApi } from "../../api/ApiContext";
import type { DataStoreInfo, TeardownPreview, TeardownScope } from "../../api/types";
import { ErrorAlert } from "../../components/Notices";
import { useLoad } from "../../hooks/useLoad";

const ROLE_LABELS = { "reviewer": "a reviewer", "platform-admin": "a platform admin" };

interface TeardownRequestPageProps {
  projectName: string;
  scope: TeardownScope;
}

/** Requests a teardown (§21.9): preview what goes and how it is backed up, type the name, then each environment
 * waits for its own approval on the Teardowns page. */
export function TeardownRequestPage({ projectName, scope }: TeardownRequestPageProps) {
  const api = useApi();
  const projects = useLoad(() => api.projects());
  const project = projects.data?.find((item) => item.name === projectName);
  const [chosen, setChosen] = useState<string>();
  const [preview, setPreview] = useState<TeardownPreview>();
  const [confirmation, setConfirmation] = useState("");
  const [requested, setRequested] = useState(false);
  const [error, setError] = useState<string>();
  const environment = chosen ?? project?.environments[0];
  const body = { scope, environments: scope === "environment" && environment ? [environment] : [] };

  const run = async (action: () => Promise<void>) => {
    try {
      setError(undefined);
      await action();
    } catch (failure) {
      setError((failure as Error).message);
    }
  };
  const showPreview = () => run(async () => setPreview(await api.previewTeardown(projectName, body)));
  const request = () => run(async () => {
    await api.requestTeardown(projectName, { ...body, confirmation });
    setRequested(true);
  });
  const ready = preview !== undefined && preview.blockers.length === 0 && confirmation === projectName;

  return (
    <section className="page">
      <header className="head">
        <div>
          <h1>{scope === "project" ? `Decommission ${projectName}` : `Tear down an environment of ${projectName}`}</h1>
          <p className="sub">Data is backed up into a locked vault before anything is deleted, and every environment
            needs its own approval.</p>
        </div>
      </header>
      <ErrorAlert message={projects.error ?? error} />
      {requested
        ? <p className="notice ok">Teardown requested. Each environment needs its own approval on the Teardowns page.</p>
        : (
          <div className="panel"><div className="panel-b stack">
            {scope === "environment" && project && (
              <label className="field">
                <span>Environment to tear down</span>
                <select aria-label="Environment to tear down" value={environment}
                        onChange={(event) => { setChosen(event.target.value); setPreview(undefined); }}>
                  {project.environments.map((item) => <option key={item} value={item}>{item}</option>)}
                </select>
              </label>
            )}
            <div className="row"><button className="btn" onClick={showPreview}>Preview teardown</button></div>
            {preview && <PreviewView preview={preview} />}
            <label className="field">
              <span>Type {projectName} to confirm</span>
              <input aria-label={`Type ${projectName} to confirm`} value={confirmation}
                     onChange={(event) => setConfirmation(event.target.value)} />
            </label>
            <div className="row"><button className="btn pri" disabled={!ready} onClick={request}>Request teardown</button></div>
          </div></div>
        )}
    </section>
  );
}

function PreviewView({ preview }: { preview: TeardownPreview }) {
  return (
    <div className="stack">
      {preview.blockers.length > 0 && (
        <div className="notice warn"><b>Cannot tear down yet:</b><ul>{preview.blockers.map((item) => <li key={item}>{item}</li>)}</ul></div>
      )}
      <p className="notice">Backups go to the locked vault in account {preview.backup_account} and cannot be deleted for
        {" "}{preview.retention_days} days; after that only super users can delete them, manually.</p>
      {preview.environments.map((item) => (
        <div key={item.environment} className="stack">
          <h3>{item.environment} · account {item.account_id} · {item.regions.join(", ")}</h3>
          <span className="hint">Needs approval from {ROLE_LABELS[item.approver_role]}</span>
          <span className="mono">Stacks: {item.stacks.join(", ")}</span>
          <ul>{item.data_stores.map((store) => <li key={`${store.region}-${store.service_id}`}>{describe(store)}</li>)}</ul>
          <ul className="muted">{item.not_backed_up.map((line) => <li key={line}>{line}</li>)}</ul>
        </div>
      ))}
    </div>
  );
}

function describe(store: DataStoreInfo): string {
  const after = store.retained ? "backed up, then deleted" : "backed up, then deleted with the stack";
  return `${store.service_id} (${store.resource_type}) in ${store.region}: ${after}`;
}
