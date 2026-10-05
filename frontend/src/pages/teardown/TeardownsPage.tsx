import { useState } from "react";
import { useApi } from "../../api/ApiContext";
import type { EnvironmentDecision, RestoreAction, Teardown, TeardownEnvironment } from "../../api/types";
import { ErrorAlert } from "../../components/Notices";
import { useLoad } from "../../hooks/useLoad";

const RUNNING = new Set(["queued", "running"]);

/** Every teardown, with one approval per environment, the locked backups, and restore (§21.9). */
export function TeardownsPage() {
  const api = useApi();
  const teardowns = useLoad(() => api.teardowns());
  const [error, setError] = useState<string>();
  const act = async (action: () => Promise<unknown>) => {
    try {
      setError(undefined);
      await action();
      teardowns.reload();
    } catch (failure) {
      setError((failure as Error).message);
    }
  };
  return (
    <section className="page">
      <header className="head">
        <div>
          <h1>Teardowns</h1>
          <p className="sub">Approve each environment's teardown, follow the backups, and restore what was torn down.</p>
        </div>
      </header>
      <ErrorAlert message={teardowns.error ?? error} />
      {teardowns.data?.length === 0 && <p className="empty">No teardowns yet.</p>}
      {teardowns.data?.map((teardown) => <TeardownPanel key={teardown.id} teardown={teardown} act={act} />)}
    </section>
  );
}

type Act = (action: () => Promise<unknown>) => void;

function TeardownPanel({ teardown, act }: { teardown: Teardown; act: Act }) {
  const api = useApi();
  const title = `${teardown.project_name} · ${teardown.scope === "project" ? "decommission" : "environment teardown"}`;
  const decide = (environment: string, decision: EnvironmentDecision, comment: string) =>
    act(() => api.decideTeardownEnvironment(teardown.project_name, teardown.id, environment, decision, comment));
  const restore = (action: RestoreAction) => act(() => api.restoreTeardown(teardown.project_name, teardown.id, action, ""));
  return (
    <section className="panel" aria-label={title}>
      <div className="panel-h"><h3>{title}</h3><span className={`chip ${teardown.state}`}>{teardown.state}</span></div>
      <div className="panel-b stack">
        <span className="hint">Requested by {teardown.requested_by}</span>
        {teardown.environments.map((environment) => (
          <EnvironmentRow key={environment.environment} project={teardown.project_name} environment={environment}
                          onDecide={decide} />
        ))}
        <RestoreRow teardown={teardown} onRestore={restore} />
      </div>
    </section>
  );
}

function EnvironmentRow({ project, environment, onDecide }: {
  project: string; environment: TeardownEnvironment;
  onDecide: (environment: string, decision: EnvironmentDecision, comment: string) => void;
}) {
  const [comment, setComment] = useState("");
  const name = environment.environment;
  const target = `${name} of ${project}`;
  return (
    <div className="stack">
      <div className="row">
        <b>{name}</b>
        <span className={`chip ${environment.state}`}>{environment.state}</span>
        {environment.decided_by && <span className="hint">decided by {environment.decided_by}</span>}
      </div>
      {environment.state === "pending_approval" && (
        <div className="row">
          <input aria-label={`Comment for ${target}`} placeholder="Comment" value={comment}
                 onChange={(event) => setComment(event.target.value)} />
          <button className="btn pri" aria-label={`Approve tearing down ${target}`} onClick={() => onDecide(name, "approve", comment)}>
            Approve</button>
          <button className="btn" aria-label={`Reject tearing down ${target}`} onClick={() => onDecide(name, "reject", comment)}>
            Reject</button>
        </div>
      )}
      {environment.state === "failed_needs_attention" && (
        <div className="row">
          <span className="err">{environment.error}</span>
          <button className="btn" aria-label={`Retry ${target}`} onClick={() => onDecide(name, "retry", "")}>Retry</button>
        </div>
      )}
      {environment.recovery_points.map((point) => (
        <div key={point.recovery_point_ref} className="stack">
          <span>{`${point.service_id} · ${point.region} · locked until ${point.locked_until.slice(0, 10)}`}</span>
          <span className="mono">{point.recovery_point_ref}</span>
        </div>
      ))}
    </div>
  );
}

function RestoreRow({ teardown, onRestore }: { teardown: Teardown; onRestore: (action: RestoreAction) => void }) {
  const restore = teardown.restore;
  const tornDown = teardown.environments.some((environment) => environment.state === "completed");
  return (
    <>
      {restore && (
        <span>{`Restore ${restore.state} (requested by ${restore.requested_by}`}
          {restore.decided_by ? `, decided by ${restore.decided_by})` : ")"}</span>
      )}
      {tornDown && (!restore || restore.state === "rejected") && (
        <div className="row"><button className="btn" aria-label={`Request restore of ${teardown.project_name}`}
                                     onClick={() => onRestore("restore")}>Request restore</button></div>
      )}
      {restore?.state === "requested" && (
        <div className="row">
          <button className="btn pri" aria-label={`Approve restore of ${teardown.project_name}`}
                  onClick={() => onRestore("approve-restore")}>Approve restore</button>
          <button className="btn" aria-label={`Reject restore of ${teardown.project_name}`}
                  onClick={() => onRestore("reject-restore")}>Reject restore</button>
        </div>
      )}
      {restore && RUNNING.has(restore.state) && (
        <span className="hint">The restore is running.</span>
      )}
    </>
  );
}
