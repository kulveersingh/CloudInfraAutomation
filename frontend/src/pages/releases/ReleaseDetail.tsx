import { useState } from "react";
import { useApi } from "../../api/ApiContext";
import type { Identity, Release } from "../../api/types";
import { ErrorAlert } from "../../components/Notices";
import { DECISIONS, decisionProblem, describeEvidence, STATE_LABELS, type DecisionRequirement } from "./decisions";

interface ReleaseDetailProps {
  release: Release;
  identity: Identity;
  onDecided: (release: Release) => void;
  onClose: () => void;
}

export function ReleaseDetail({ release, identity, onDecided, onClose }: ReleaseDetailProps) {
  const requirement = DECISIONS[release.state];
  return (
    <div className="panel">
      <div className="panel-h">
        <div>
          <h2>Release {release.id}</h2>
          <span className="hint">{release.project_name} → {release.environment} · requested by {release.requested_by} ·
            commit <span className="mono">{release.commit_sha}</span></span>
        </div>
        <span className={`chip ${release.state}`}>{STATE_LABELS[release.state]}</span>
        <button className="btn ghost" onClick={onClose}>Close</button>
      </div>
      <div className="panel-b">
        <span className="label">Change set · overall risk {release.risk}</span>
        <div className="tbl-wrap">
          <table aria-label="Change set">
            <tbody>
              {release.changes.map((change) => (
                <tr key={`${change.action}-${change.logical_id}`} className={`risk-${change.risk}`}>
                  <td><b>{change.action}</b></td>
                  <td className="mono">{change.logical_id}</td>
                  <td className="mono">{change.resource_type}</td>
                  <td><span className={`chip risk-${change.risk}`}>{change.risk}</span>
                    {change.replacement && <span className="tag">replacement</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <span className="label">Evidence</span>
        <p className="mono">{describeEvidence(release)}</p>
        <FindingsList findings={release.gate_findings} />
        {release.execution_detail && <p className="notice ok">{release.execution_detail}</p>}
        <ul className="decisions">
          {release.decisions.map((decision) => (
            <li key={decision.created_at}>{decision.actor} · {decision.kind} · {decision.comment}</li>
          ))}
        </ul>
        {requirement && <DecisionControls release={release} identity={identity} requirement={requirement} onDecided={onDecided} />}
      </div>
    </div>
  );
}

export function FindingsList({ findings }: { findings: string[] }) {
  if (findings.length === 0) return null;
  return <ul className="notice crit">{findings.map((finding) => <li key={finding}>{finding}</li>)}</ul>;
}

interface DecisionControlsProps {
  release: Release;
  identity: Identity;
  requirement: DecisionRequirement;
  onDecided: (release: Release) => void;
}

function DecisionControls({ release, identity, requirement, onDecided }: DecisionControlsProps) {
  const api = useApi();
  const [comment, setComment] = useState("");
  const [error, setError] = useState<string>();
  const problem = decisionProblem(identity, release, requirement);

  const decide = async (action: () => Promise<Release>) => {
    try {
      onDecided(await action());
    } catch (failure) {
      setError((failure as Error).message);
    }
  };

  return (
    <div className="stack">
      <div className="field">
        <label htmlFor="decision-comment">Comment</label>
        <textarea id="decision-comment" rows={2} value={comment} onChange={(event) => setComment(event.target.value)} />
      </div>
      {problem && <div className="notice warn">{problem} Switch “Viewing as” to try another role.</div>}
      <ErrorAlert message={error} />
      <div className="row">
        <button className="btn pri" disabled={problem !== undefined}
                onClick={() => decide(() => requirement.approve(api, release.id, comment))}>
          {requirement.approveLabel}
        </button>
        <button className="btn" disabled={problem !== undefined} onClick={() => decide(() => api.rejectRelease(release.id, comment))}>
          Reject
        </button>
        <span className="hint">Approved changes are applied by the platform release executor.</span>
      </div>
    </div>
  );
}
