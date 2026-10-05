import { useEffect, useState } from "react";
import { useApi } from "../../api/ApiContext";
import type { ProjectChange, ProjectReadBack } from "../../api/types";
import { ErrorAlert } from "../../components/Notices";
import { RefusedRepository } from "../../components/RefusedRepository";
import { useLoad } from "../../hooks/useLoad";
import { ProjectDraft } from "../../wizard/ProjectDraft";
import { JobProgress } from "./JobProgress";
import { loadReferenceData, ProjectWizard } from "./ProjectWizard";

const SHORT_SHA = 7;

interface ChangeProjectPageProps {
  projectName: string;
  pollMs?: number;
}

/** Change infrastructure (§21.8): read the project back, edit it in the wizard, open a pull request. */
export function ChangeProjectPage({ projectName, pollMs = 2000 }: ChangeProjectPageProps) {
  const api = useApi();
  const loaded = useLoad(() => Promise.all([api.projectReadBack(projectName), loadReferenceData(api)]));
  const [opened, setOpened] = useState<ProjectChange>();

  return (
    <section className="page">
      <header className="head">
        <div>
          <h1>Change {projectName}</h1>
          <p className="sub">Edit the services, connections, network and environments. The platform opens a pull request on
            the infrastructure repository for review.</p>
        </div>
      </header>
      <ErrorAlert message={loaded.error} />
      {opened && <ChangeProgress projectName={projectName} change={opened} pollMs={pollMs} />}
      {!opened && loaded.data && <Editor readBack={loaded.data[0]} reference={loaded.data[1]} projectName={projectName}
                                         onOpened={setOpened} />}
    </section>
  );
}

function Editor({ readBack, reference, projectName, onOpened }: {
  readBack: ProjectReadBack; reference: Awaited<ReturnType<typeof loadReferenceData>>; projectName: string;
  onOpened: (change: ProjectChange) => void;
}) {
  if (!readBack.verified) {
    return <RefusedRepository title="The project repository can't be loaded" readBack={readBack} />;
  }
  const request = readBack.request!;
  const base = { projectName, baseCommit: readBack.commit_sha!, revision: readBack.design.revision,
    environments: request.environments };
  return (
    <>
      <p className="notice">
        Changing revision {base.revision} (commit {base.baseCommit.slice(0, SHORT_SHA)}). Name, ownership, classification and
        resilience are fixed; environments can only be added.
      </p>
      <ProjectWizard reference={reference} initial={ProjectDraft.fromRequest(request)}
                     mode={{ kind: "change", base, onOpened }} />
    </>
  );
}

function ChangeProgress({ projectName, change, pollMs }: { projectName: string; change: ProjectChange; pollMs: number }) {
  return (
    <>
      <JobProgress jobId={change.job_id!} pollMs={pollMs} />
      <ChangeOutcome projectName={projectName} changeId={change.id} pollMs={pollMs} />
    </>
  );
}

function ChangeOutcome({ projectName, changeId, pollMs }: { projectName: string; changeId: string; pollMs: number }) {
  const api = useApi();
  const [change, setChange] = useState<ProjectChange>();
  const [error, setError] = useState<string>();

  useEffect(() => {
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const poll = async () => {
      try {
        const current = await api.projectChange(projectName, changeId);
        setChange(current);
        if (!stopped && current.state === "queued") timer = setTimeout(poll, pollMs);
      } catch (failure) {
        setError((failure as Error).message);
      }
    };
    poll();
    return () => {
      stopped = true;
      clearTimeout(timer);
    };
  }, [api, projectName, changeId, pollMs]);

  return (
    <>
      <ErrorAlert message={error} />
      {change?.pull_request && (
        <p className="notice ok">Opened for review: <a href={change.pull_request.url} target="_blank" rel="noreferrer">
          Pull request #{change.pull_request.number}</a>. Merging it in GitHub records revision {change.revision}.</p>
      )}
      {change?.state === "failed" && <p className="notice crit">The change failed and was undone; see the steps above.</p>}
    </>
  );
}
