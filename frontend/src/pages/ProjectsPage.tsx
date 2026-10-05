import { useState } from "react";
import { useApi } from "../api/ApiContext";
import type { OpenChange, ProjectSummary, ResilienceMode } from "../api/types";
import { ErrorAlert } from "../components/Notices";
import { useLoad } from "../hooks/useLoad";

export const MODE_LABELS: Record<ResilienceMode, string> = {
  single: "Single region",
  dr: "DR · active/standby",
  ha: "HA · active/active",
};

interface ProjectsPageProps {
  onNewProject: () => void;
  onChangeProject: (projectName: string) => void;
}

export function ProjectsPage({ onNewProject, onChangeProject }: ProjectsPageProps) {
  const api = useApi();
  const projects = useLoad(() => api.projects());
  const [error, setError] = useState<string>();
  /** Local stand-ins for a person merging or closing the pull request in GitHub (§21.8 C2). */
  const decide = async (decision: "mergeChange" | "closeChange", project: string, change: OpenChange) => {
    try {
      setError(undefined);
      await api[decision](project, change.id);
      projects.reload();
    } catch (failure) {
      setError((failure as Error).message);
    }
  };
  return (
    <section className="page">
      <header className="head">
        <div>
          <h1>Projects</h1>
          <p className="sub">Every project is one infrastructure repository deployed through your environments.</p>
        </div>
        <button className="btn pri" onClick={onNewProject}>New project</button>
      </header>
      <ErrorAlert message={projects.error ?? error} />
      {projects.data && <ProjectTable projects={projects.data} onChangeProject={onChangeProject} onDecide={decide} />}
    </section>
  );
}

interface ProjectTableProps {
  projects: ProjectSummary[];
  onChangeProject: (projectName: string) => void;
  onDecide: (decision: "mergeChange" | "closeChange", project: string, change: OpenChange) => void;
}

function ProjectTable({ projects, onChangeProject, onDecide }: ProjectTableProps) {
  if (projects.length === 0) {
    return <p className="empty">No projects yet. Create one with New project.</p>;
  }
  return (
    <div className="panel tbl-wrap">
      <table>
        <thead><tr><th>Project</th><th>Portfolio</th><th>Product</th><th>Resilience</th><th>Status</th><th>Revision</th><th>Changes</th></tr></thead>
        <tbody>
          {projects.map((project) => (
            <tr key={project.name}>
              <td><b>{project.name}</b></td>
              <td className="mono">{project.portfolio_id}</td>
              <td className="mono">{project.product_id}</td>
              <td>{MODE_LABELS[project.resilience_mode]}</td>
              <td><span className={`chip ${project.status}`}>{project.status}</span></td>
              <td className="mono">r{project.revision}</td>
              <td>
                {project.open_change
                  ? <OpenChangeCell project={project.name} change={project.open_change} onDecide={onDecide} />
                  : project.status === "active" && (
                    <button className="btn ghost" aria-label={`Change infrastructure for ${project.name}`}
                            onClick={() => onChangeProject(project.name)}>Change infrastructure</button>
                  )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function OpenChangeCell({ project, change, onDecide }: {
  project: string; change: OpenChange; onDecide: ProjectTableProps["onDecide"];
}) {
  if (!change.pull_request) return <span className="muted">Revision {change.revision} · {change.state}</span>;
  const target = `revision ${change.revision} of ${project}`;
  return (
    <div className="row">
      <a href={change.pull_request.url} target="_blank" rel="noreferrer">
        Revision {change.revision} · pull request #{change.pull_request.number}</a>
      <button className="btn ghost" aria-label={`Simulate merge ${target}`} onClick={() => onDecide("mergeChange", project, change)}>
        Simulate merge</button>
      <button className="btn ghost" aria-label={`Close ${target}`} onClick={() => onDecide("closeChange", project, change)}>
        Close</button>
    </div>
  );
}
