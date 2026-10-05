import { useState } from "react";
import { useApi } from "../../../api/ApiContext";
import type { ChangeSummary, ProjectChange, ProjectChangePreview } from "../../../api/types";
import { ErrorAlert } from "../../../components/Notices";
import type { ProjectDraft } from "../../../wizard/ProjectDraft";
import { DraftProblems, PreviewDetails } from "./PreviewStep";
import type { ChangeBase } from "./StepProps";

interface ChangePreviewStepProps {
  draft: ProjectDraft;
  base: ChangeBase;
  onOpened: (change: ProjectChange) => void;
}

/** Previews a change against the commit it was loaded at, then opens it as a pull request (§21.8). */
export function ChangePreviewStep({ draft, base, onOpened }: ChangePreviewStepProps) {
  const api = useApi();
  const [result, setResult] = useState<ProjectChangePreview>();
  const [confirmed, setConfirmed] = useState(false);
  const [error, setError] = useState<string>();
  const problems = draft.problems();
  const deletes = result?.summary.removed_services.some((service) => !service.retained) ?? false;
  const body = (confirmRemovals: boolean) => ({ request: draft.toRequest(), base_commit: base.baseCommit,
    confirm_removals: confirmRemovals });

  const run = async (action: () => Promise<void>) => {
    try {
      setError(undefined);
      await action();
    } catch (failure) {
      setError((failure as Error).message);
    }
  };
  const preview = () => run(async () => setResult(await api.previewChange(base.projectName, body(false))));
  const open = () => run(async () => onOpened(await api.createChange(base.projectName, body(confirmed))));

  return (
    <>
      <h2>Preview</h2>
      <DraftProblems problems={problems} />
      <ErrorAlert message={error} />
      {result && <ChangeSummaryView summary={result.summary} />}
      {deletes && (
        <label className="row">
          <input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} />
          I understand the deleted resources and their data are removed
        </label>
      )}
      <div className="row">
        <button className="btn" disabled={problems.length > 0} onClick={preview}>Preview change</button>
        <button className="btn pri" disabled={!result || (deletes && !confirmed)} onClick={open}>Open change request</button>
      </div>
      {result && <PreviewDetails result={result} provider={draft.values.provider} />}
    </>
  );
}

function ChangeSummaryView({ summary }: { summary: ChangeSummary }) {
  const lines: Array<[string, string[]]> = [["Files that change", summary.changed_files], ["Added", summary.added_services],
    ["Changed", summary.changed_services], ["Added environments", summary.added_environments]];
  return (
    <div className="notice">
      {lines.filter(([, values]) => values.length > 0).map(([label, values]) => (
        <p key={label}>{`${label}: ${values.join(", ")}`}</p>
      ))}
      {summary.removed_services.length > 0 && (
        <ul>
          {summary.removed_services.map((service) => (
            <li key={service.id}>{`${service.id} (${service.type}): ${service.removal}`}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
