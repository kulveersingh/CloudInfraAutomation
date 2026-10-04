import { useEffect, useState } from "react";
import { useApi } from "../../api/ApiContext";
import type { JobStatus } from "../../api/types";
import { ErrorAlert } from "../../components/Notices";

const FINISHED = new Set(["succeeded", "failed_rolled_back", "failed_needs_attention"]);
const PROGRESS_MESSAGES: Record<string, string> = {
  queued: "Waiting for the worker…",
  running: "Provisioning…",
  succeeded: "Provisioning finished.",
};
const FAILURE_MESSAGES: Record<string, string> = {
  failed_rolled_back: "Provisioning failed and was rolled back:",
  failed_needs_attention: "Provisioning failed and needs attention (undo steps did not finish):",
};

export function JobProgress({ jobId, pollMs }: { jobId: string; pollMs: number }) {
  const api = useApi();
  const [status, setStatus] = useState<JobStatus>();
  const [error, setError] = useState<string>();

  useEffect(() => {
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const schedule = (state: string) => {
      if (!stopped && !FINISHED.has(state)) timer = setTimeout(poll, pollMs);
    };
    const poll = async () => {
      try {
        const current = await api.job(jobId);
        setStatus(current);
        schedule(current.state);
      } catch (failure) {
        setError((failure as Error).message);
      }
    };
    poll();
    return () => {
      stopped = true;
      clearTimeout(timer);
    };
  }, [api, jobId, pollMs]);

  return (
    <div className="panel">
      <div className="panel-b">
        <ErrorAlert message={error} />
        {status ? <JobView status={status} /> : <p className="muted">Starting…</p>}
      </div>
    </div>
  );
}

function JobView({ status }: { status: JobStatus }) {
  const failure = FAILURE_MESSAGES[status.state];
  return (
    <>
      {failure
        ? <div role="alert" className="notice crit">{failure} {status.error}</div>
        : <p className="notice">{PROGRESS_MESSAGES[status.state]}</p>}
      <ol className="steps-list">
        {status.steps.map((step) => (
          <li key={step.sequence}>
            <span className="mono">{step.name}</span> <span className={`chip ${step.state}`}>{step.state}</span>
          </li>
        ))}
      </ol>
    </>
  );
}
