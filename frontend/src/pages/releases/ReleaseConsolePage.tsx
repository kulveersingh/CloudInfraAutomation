import { useState } from "react";
import { useApi } from "../../api/ApiContext";
import type { Identity, PipelineStage, ProjectSummary, Release } from "../../api/types";
import { ErrorAlert } from "../../components/Notices";
import { useLoad } from "../../hooks/useLoad";
import { STATE_LABELS } from "./decisions";
import { FindingsList, ReleaseDetail } from "./ReleaseDetail";

export function ReleaseConsolePage({ identity }: { identity: Identity }) {
  const api = useApi();
  const projects = useLoad(() => api.projects());
  return (
    <section className="page">
      <header className="head">
        <div>
          <h1>Release console</h1>
          <p className="sub">QA/STAGE and PROD change only after the automated gate passes and a reviewer approves. The
            release executor then applies exactly the change set that was reviewed.</p>
        </div>
      </header>
      <ErrorAlert message={projects.error} />
      {projects.data && <ConsoleBody projects={projects.data} identity={identity} />}
    </section>
  );
}

function ConsoleBody({ projects, identity }: { projects: ProjectSummary[]; identity: Identity }) {
  if (projects.length === 0) {
    return <p className="empty">Create a project first; its releases will appear here.</p>;
  }
  return <ProjectConsole projects={projects} identity={identity} />;
}

function ProjectConsole({ projects, identity }: { projects: ProjectSummary[]; identity: Identity }) {
  const api = useApi();
  const [project, setProject] = useState(projects[0].name);
  const [selected, setSelected] = useState<Release>();
  const stages = useLoad(() => api.pipeline(project));
  const inbox = useLoad(() => api.inbox());

  const refresh = (release?: Release) => {
    setSelected(release);
    stages.reload();
    inbox.reload();
  };
  const changeProject = (name: string) => {
    setProject(name);
    setSelected(undefined);
    stages.reload();
  };

  return (
    <>
      <div className="row">
        <label htmlFor="release-project" className="label">Project</label>
        <select id="release-project" value={project} onChange={(event) => changeProject(event.target.value)}>
          {projects.map((item) => <option key={item.name}>{item.name}</option>)}
        </select>
      </div>
      <ErrorAlert message={stages.error ?? inbox.error} />
      {stages.data && <Pipeline stages={stages.data} onOpen={setSelected} />}
      {stages.data && <SimulationForm project={project} stages={stages.data} onSimulated={refresh} />}
      <div className="split">
        <Inbox releases={inbox.data ?? []} onOpen={setSelected} />
        {selected && <ReleaseDetail release={selected} identity={identity} onDecided={refresh} onClose={() => setSelected(undefined)} />}
      </div>
    </>
  );
}

function Pipeline({ stages, onOpen }: { stages: PipelineStage[]; onOpen: (release: Release) => void }) {
  return (
    <div className="pipe">
      {stages.map((stage) => (
        <div key={stage.environment} role="group" aria-label={stage.name} className={`stage ${stage.requires_approval ? "gated" : ""}`}>
          <div className="env">{stage.name}{stage.requires_approval && <span className="pill">approval</span>}</div>
          {stage.release ? <StageRelease stage={stage} release={stage.release} onOpen={onOpen} /> : <span className="muted">No release yet</span>}
        </div>
      ))}
    </div>
  );
}

function StageRelease({ stage, release, onOpen }: { stage: PipelineStage; release: Release; onOpen: (r: Release) => void }) {
  return (
    <>
      <span className={`chip ${release.state}`}>{STATE_LABELS[release.state]}</span>
      <span className="mono">{release.commit_sha}</span>
      <FindingsList findings={release.gate_findings} />
      <button className="btn ghost" aria-label={`Open ${stage.name} release`} onClick={() => onOpen(release)}>Details</button>
    </>
  );
}

interface SimulationFormProps {
  project: string;
  stages: PipelineStage[];
  onSimulated: (release: Release) => void;
}

function SimulationForm({ project, stages, onSimulated }: SimulationFormProps) {
  const api = useApi();
  const [environment, setEnvironment] = useState(stages[0].environment);
  const [highRisk, setHighRisk] = useState(false);
  const [error, setError] = useState<string>();

  const simulate = async () => {
    try {
      setError(undefined);
      onSimulated(await api.simulateRelease(project, environment, highRisk));
    } catch (failure) {
      setError((failure as Error).message);
    }
  };

  return (
    <div className="panel">
      <div className="panel-b">
        <span className="label">Local pipeline simulation</span>
        <div className="row">
          <label htmlFor="simulate-environment">Environment</label>
          <select id="simulate-environment" value={environment} onChange={(event) => setEnvironment(event.target.value)}>
            {stages.map((stage) => <option key={stage.environment} value={stage.environment}>{stage.name}</option>)}
          </select>
          <label className="row">
            <input type="checkbox" checked={highRisk} onChange={(event) => setHighRisk(event.target.checked)} />
            High-risk change
          </label>
          <button className="btn" onClick={simulate}>Simulate pipeline plan</button>
        </div>
        <ErrorAlert message={error} />
      </div>
    </div>
  );
}

function Inbox({ releases, onOpen }: { releases: Release[]; onOpen: (release: Release) => void }) {
  return (
    <div className="panel">
      <div className="panel-h"><h3>Approval inbox</h3><span className="hint">{releases.length} waiting</span></div>
      <div className="panel-b">
        {releases.length === 0 && <p className="empty">Nothing is waiting for you.</p>}
        <ul className="inbox">
          {releases.map((release) => (
            <li key={release.id} className="row">
              <span className={`chip ${release.state}`}>{STATE_LABELS[release.state]}</span>
              <b>{release.project_name}</b> → {release.environment}
              <span className="muted">risk {release.risk} · by {release.requested_by}</span>
              <button className="btn ghost" aria-label={`Open release ${release.id}`} onClick={() => onOpen(release)}>Review</button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
